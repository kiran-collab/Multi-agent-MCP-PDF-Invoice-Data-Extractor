"""
Render a human-readable summary from saved eval result files.

Reads evals/results/app2_eval_results.json and app3_eval_results.json (whichever
exist) and prints a per-metric table plus per-case overall scores.

Usage:
    python evals/report_eval_results.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from scorers import aggregate  # noqa: E402

RESULTS = HERE / "results"

METRIC_LABELS = {
    "overall": "overall",
    "invoice_id_acc": "invoice id accuracy",
    "client_name_acc": "client name accuracy",
    "date_acc": "invoice date accuracy",
    "currency_acc": "currency accuracy",
    "total_amount_acc": "total amount (tol) accuracy",
    "line_item_recall": "line item recall",
    "schema_valid_rate": "schema validity",
    "hallucination_rate": "hallucination rate",
}


def _fmt(v) -> str:
    return "  n/a" if v is None else f"{v:5.2f}"


def _report_one(path: Path) -> None:
    results = json.loads(path.read_text())
    invoice_results = [r for r in results if "scores" in r]
    summary = aggregate(invoice_results)

    print(f"\n=== {path.name} ===")
    print(f"cases: {summary.get('cases', 0)}   scored: {summary.get('scored', 0)}")
    print("-" * 44)
    for key, label in METRIC_LABELS.items():
        if key in summary:
            print(f"  {label:<28} {_fmt(summary[key])}")

    # Per-case overall, surfacing skips and failures.
    print("  per-case:")
    for r in results:
        if r.get("skipped"):
            print(f"    - {r.get('file_name','?'):<22} SKIPPED ({r.get('reason')})")
        elif r.get("json_valid") is False:
            print(f"    - {r.get('file_name','?'):<22} INVALID JSON")
        elif isinstance(r.get("scores"), dict):
            print(f"    - {r.get('file_name','?'):<22} overall={r['scores']['overall']:.2f}")

    # Report-level score (app3).
    rep = next((r["report_score"] for r in results if "report_score" in r), None)
    if rep:
        print("  report correctness:")
        print(f"    client name recall   {_fmt(rep['client_name_recall'])}")
        print(f"    client total recall  {_fmt(rep['client_total_recall'])}")


def main() -> None:
    found = False
    for name in ("app2_eval_results.json", "app3_eval_results.json"):
        path = RESULTS / name
        if path.exists():
            _report_one(path)
            found = True
    if not found:
        print("No result files found. Run run_app2_eval.py / run_app3_eval.py first.")


if __name__ == "__main__":
    main()
