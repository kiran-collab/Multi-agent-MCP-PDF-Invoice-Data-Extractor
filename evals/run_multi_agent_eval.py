"""
Evaluation runner for multi_agent (A2A multi-agent system).

App3 is evaluated at two levels — pick with --mode:

  component  (default)  Evaluate each specialized agent's real work function:
                          files_agent_server.list_invoices(folder_id)
                          extraction_agent_server.extract_invoice(file_id, name)
                        Requires google-adk importable + Box MCP + Gemini, but
                        NO running servers. Scores file discovery and per-file
                        structured-invoice accuracy.

  e2e                   Drive the whole workflow through the Orchestrator over
                        A2A (A2AClient.send_message_streaming), then score the
                        rendered per-client report text. Requires all three
                        servers running (ports 8001/8002/8000) + Box + Gemini.
                        Set --folder-id to the Box folder under test.

  mock                  Offline: score each case's `mock_predicted` (extraction)
                        and synthesize a report from `expected` to exercise the
                        report scorer. No external calls.

Usage:
    python evals/run_multi_agent_eval.py --mode component
    python evals/run_multi_agent_eval.py --mode e2e --folder-id 0
    python evals/run_multi_agent_eval.py --mode mock

Results -> evals/results/multi_agent_eval_results.json (+ multi_agent_traces.json).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from scorers import aggregate, score_invoice, score_report_text  # noqa: E402
from tracing import TraceLog  # noqa: E402

logger = logging.getLogger("evals.multi_agent")


def _load_dataset() -> list:
    return json.loads((HERE / "golden_dataset.json").read_text())


def _import_multi_agent():
    """Put multi_agent/ on sys.path and import the agent server modules.

    Importing these constructs LlmAgent / to_a2a_app at module load, so it needs
    google-adk installed. Raised errors are surfaced with a clear hint.
    """
    sys.path.insert(0, str(ROOT / "app" / "multi_agent_extractor"))
    try:
        import extraction_agent_server  # type: ignore
        import files_agent_server  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Could not import multi_agent agent servers (needs `google-adk`, `mcp`, and "
            f"`google-genai` installed): {exc}"
        ) from exc
    return files_agent_server, extraction_agent_server


# --- component mode -------------------------------------------------------
async def run_component(dataset: list, traces: TraceLog) -> list:
    files_agent_server, extraction_agent_server = _import_multi_agent()
    results = []
    for i, case in enumerate(dataset):
        name = case["file_name"]
        logger.info("[%d/%d] ExtractionAgent.extract_invoice %s (box_file_id=%s)",
                    i + 1, len(dataset), name, case["box_file_id"])
        tr = traces.new(f"multi_agent-comp-{i:03d}", file_name=name)
        record: dict = {"file_name": name, "expected": case["expected"]}

        raw = await extraction_agent_server.extract_invoice(case["box_file_id"], name)
        try:
            predicted = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("invalid JSON from ExtractionAgent for %s: %s", name, exc)
            tr.step("ExtractionAgent", "extract_invoice", "error", error=f"json: {exc}")
            record.update({"json_valid": False, "scores": None})
            results.append(record)
            continue

        if predicted.get("error"):  # extraction agent's empty-text contract
            tr.step("ExtractionAgent", "extract_invoice", "empty", detail=predicted)
            record.update({"skipped": True, "reason": predicted["error"], "scores": None})
            results.append(record)
            continue

        tr.step("ExtractionAgent", "extract_invoice", "success")
        record["json_valid"] = True
        record["predicted"] = predicted
        record["scores"] = score_invoice(predicted, case["expected"], case.get("source_text"))
        results.append(record)
    return results


async def eval_file_discovery(folder_id: str, expected_names: list, traces: TraceLog) -> dict:
    """Files Agent: does list_invoices return exactly the expected file names?"""
    files_agent_server, _ = _import_multi_agent()
    tr = traces.new("multi_agent-files", folder_id=folder_id)
    raw = await files_agent_server.list_invoices(folder_id)
    found = [f.get("name") for f in json.loads(raw)]
    tr.step("FilesAgent", "list_invoices", "success", output_count=len(found))
    exp, got = set(expected_names), set(found)
    return {
        "expected_files": sorted(exp),
        "found_files": sorted(got),
        "missing": sorted(exp - got),
        "extra": sorted(got - exp),       # non-invoice files wrongly included
        "exact_match": exp == got,
    }


# --- e2e mode -------------------------------------------------------------
async def run_e2e(dataset: list, folder_id: str, traces: TraceLog) -> list:
    sys.path.insert(0, str(ROOT / "app" / "multi_agent_extractor"))
    from a2a.client import A2AClient  # type: ignore

    tr = traces.new("multi_agent-e2e", folder_id=folder_id)
    url = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")
    client = A2AClient(url=url)
    prompt = (
        f"Process all invoices in Box folder {folder_id}. Extract client name, "
        f"total amount, and purchased products from each, then give me a "
        f"per-client summary report."
    )
    tr.step("OrchestratorAgent", "send_message", "success", url=url)
    chunks = []
    async for event in client.send_message_streaming(prompt):
        text = getattr(event, "text", None)
        if text:
            chunks.append(text)
    report_text = "".join(chunks)
    tr.step("OrchestratorAgent", "build_reports", "success", chars=len(report_text))

    expected_invoices = [c["expected"] for c in dataset]
    report_score = score_report_text(report_text, expected_invoices)
    # The orchestrator must consult FilesAgent before ExtractionAgent before reporting.
    report_score["delegation_ok"] = tr.delegation_ok(
        ["OrchestratorAgent"]  # extend if the A2A events expose sub-agent names
    )
    return [{"folder_id": folder_id, "report_text": report_text,
             "report_score": report_score}]


# --- mock mode ------------------------------------------------------------
def run_mock(dataset: list) -> list:
    results = []
    for case in dataset:
        predicted = case.get("mock_predicted")
        if predicted is not None:
            results.append({
                "file_name": case["file_name"],
                "predicted": predicted,
                "expected": case["expected"],
                "json_valid": True,
                "scores": score_invoice(predicted, case["expected"], case.get("source_text")),
            })
    # Synthesize a perfect report from expected to exercise the report scorer.
    expected_invoices = [c["expected"] for c in dataset]
    report_text = "\n".join(
        f"Client Report: {inv['client_name']}\nTotal spend: "
        f"{inv['total_amount']:.2f} {inv['currency']}"
        for inv in expected_invoices
    )
    results.append({
        "report_text": report_text,
        "report_score": score_report_text(report_text, expected_invoices),
    })
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate multi_agent multi-agent system.")
    ap.add_argument("--mode", choices=["component", "e2e", "mock"], default="component")
    ap.add_argument("--folder-id", default=os.getenv("EVAL_FOLDER_ID", "0"))
    ap.add_argument("--log-level", default="INFO",
                    help="Logging level: DEBUG, INFO, WARNING, ERROR (default INFO).")
    args = ap.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
    )

    dataset = _load_dataset()
    traces = TraceLog()
    logger.info("multi_agent eval starting: %d case(s), mode=%s", len(dataset), args.mode)

    if args.mode == "mock":
        results = run_mock(dataset)
    elif args.mode == "e2e":
        results = asyncio.run(run_e2e(dataset, args.folder_id, traces))
    else:
        results = asyncio.run(run_component(dataset, traces))

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "multi_agent_eval_results.json").write_text(json.dumps(results, indent=2))
    if traces.traces:
        traces.save(out_dir / "multi_agent_traces.json")

    invoice_results = [r for r in results if "scores" in r]
    summary = aggregate(invoice_results) if invoice_results else {}
    report = next((r["report_score"] for r in results if "report_score" in r), None)
    print(json.dumps({"app": "multi_agent", "mode": args.mode,
                      "summary": summary, "report_score": report}, indent=2))


if __name__ == "__main__":
    main()
