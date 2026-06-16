"""
Evaluation runner for app2 (MCP-based invoice processing).

It exercises the real app2 pipeline per golden case:

    box_mcp_client.extract_text(box_file_id)        # MCP text extraction
    llm_extraction.extract_invoice_fields(text, …)  # Gemini -> structured Invoice

then scores the structured output against the golden expected value, capturing:
json validity, schema validity, field accuracy, numeric tolerance, line-item
recall, hallucination rate, and empty-text handling.

Usage:
    # Real run — requires GOOGLE_API_KEY, a Box MCP server, BOX_DEVELOPER_TOKEN,
    # and real box_file_id values in golden_dataset.json:
    python evals/run_app2_eval.py

    # Offline smoke test — no Box / Gemini; scores each case's `mock_predicted`
    # to verify the scorers + reporting wiring end to end:
    python evals/run_app2_eval.py --mock

Results are written to evals/results/app2_eval_results.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))  # so `import scorers` / `import tracing` work

from scorers import aggregate, score_invoice  # noqa: E402
from tracing import TraceLog  # noqa: E402


def _load_dataset() -> list:
    return json.loads((HERE / "golden_dataset.json").read_text())


def _import_app2():
    """Put app2/ on sys.path and import its modules (bare imports inside them)."""
    sys.path.insert(0, str(ROOT / "app2"))
    import box_mcp_client  # type: ignore
    import llm_extraction  # type: ignore

    return box_mcp_client, llm_extraction


async def run_real(dataset: list, traces: TraceLog) -> list:
    box_mcp_client, llm_extraction = _import_app2()
    results = []
    for i, case in enumerate(dataset):
        name = case["file_name"]
        tr = traces.new(f"app2-{i:03d}", file_name=name)
        record: dict = {"file_name": name, "expected": case["expected"]}

        text = await box_mcp_client.extract_text(case["box_file_id"])
        if not text.strip():
            # Empty-text handling: app2 skips these; record it as a handled skip.
            tr.step("BoxMCP", "extract_text", "empty", chars=0)
            record.update({"skipped": True, "reason": "empty_text", "scores": None})
            results.append(record)
            continue
        tr.step("BoxMCP", "extract_text", "success", chars=len(text))

        try:
            invoice = await asyncio.to_thread(
                llm_extraction.extract_invoice_fields, text, name
            )
            predicted = invoice.to_dict()
            tr.step("LLM", "extract_invoice_fields", "success")
            record["json_valid"] = True
        except json.JSONDecodeError as exc:
            # Malformed LLM JSON breaks extract_invoice_fields' json.loads.
            tr.step("LLM", "extract_invoice_fields", "error", error=f"json: {exc}")
            record.update({"json_valid": False, "scores": None})
            results.append(record)
            continue

        record["predicted"] = predicted
        record["scores"] = score_invoice(predicted, case["expected"], case.get("source_text"))
        results.append(record)
    return results


def run_mock(dataset: list) -> list:
    """Offline: score each case's pre-baked `mock_predicted` (no external calls)."""
    results = []
    for case in dataset:
        predicted = case.get("mock_predicted")
        if predicted is None:
            results.append({"file_name": case["file_name"], "skipped": True,
                            "reason": "no_mock_predicted", "scores": None})
            continue
        results.append({
            "file_name": case["file_name"],
            "predicted": predicted,
            "expected": case["expected"],
            "json_valid": True,
            "scores": score_invoice(predicted, case["expected"], case.get("source_text")),
        })
    return results


def main() -> None:
    ap = argparse.ArgumentParser(description="Evaluate app2 invoice extraction.")
    ap.add_argument("--mock", action="store_true",
                    help="Offline: score mock_predicted instead of calling Box/Gemini.")
    args = ap.parse_args()

    dataset = _load_dataset()
    traces = TraceLog()

    if args.mock:
        results = run_mock(dataset)
    else:
        results = asyncio.run(run_real(dataset, traces))

    out_dir = HERE / "results"
    out_dir.mkdir(exist_ok=True)
    (out_dir / "app2_eval_results.json").write_text(json.dumps(results, indent=2))
    if traces.traces:
        traces.save(out_dir / "app2_traces.json")

    summary = aggregate(results)
    print(json.dumps({"app": "app2", "mode": "mock" if args.mock else "real",
                      "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
