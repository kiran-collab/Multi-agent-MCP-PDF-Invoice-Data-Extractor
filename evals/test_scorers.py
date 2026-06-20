"""
Offline unit tests for scorers.py — pure stdlib, no external services.

Run with pytest:        python -m pytest evals/test_scorers.py -q
Or standalone:          python evals/test_scorers.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from scorers import (  # noqa: E402
    check_schema,
    hallucination_check,
    is_valid_json,
    score_invoice,
    score_line_items,
    score_report_text,
)

PERFECT = {
    "invoice_id": "INV-001",
    "client_name": "Acme Corp",
    "invoice_date": "2026-05-10",
    "currency": "USD",
    "total_amount": 1250.50,
    "line_items": [
        {"description": "Cloud hosting", "quantity": 1, "unit_price": 1250.50, "amount": 1250.50}
    ],
}


def test_json_validity():
    assert is_valid_json('{"a": 1}')
    assert not is_valid_json("{not json")


def test_schema():
    assert check_schema(PERFECT)["valid"]
    bad = {"invoice_id": "x", "total_amount": "oops"}  # wrong type + missing keys
    res = check_schema(bad)
    assert not res["valid"]
    assert "total_amount" in res["wrong_type"]
    assert "client_name" in res["missing"]


def test_pydantic_schema_module():
    from schema import validate_invoice  # noqa: PLC0415

    assert validate_invoice(PERFECT)["valid"]
    # "1250.50" as a string still validates (pydantic coerces to float).
    ok = validate_invoice(dict(PERFECT, total_amount="1250.50"))
    assert ok["valid"]
    bad = validate_invoice({"invoice_id": "x"})
    assert not bad["valid"]
    assert "client_name" in bad["missing"]
    assert bad["errors"]  # structured per-field errors present


def test_perfect_match_scores_one():
    s = score_invoice(PERFECT, PERFECT)
    assert s["overall"] == 1.0
    assert all(s["fields"].values())
    assert s["total_amount_match"]
    assert s["line_items"]["recall"] == 1.0


def test_case_insensitive_client_and_tolerance():
    pred = dict(PERFECT, client_name="ACME CORP", total_amount=1250.505)
    s = score_invoice(pred, PERFECT)
    assert s["fields"]["client_name"]      # case-insensitive
    assert s["total_amount_match"]         # within 0.01 tolerance


def test_wrong_total_and_missing_item():
    pred = dict(PERFECT, total_amount=999.0, line_items=[])
    s = score_invoice(pred, PERFECT)
    assert not s["total_amount_match"]
    assert s["line_items"]["recall"] == 0.0
    assert s["overall"] < 1.0


def test_line_item_recall_partial():
    expected = [{"description": "A", "amount": 10}, {"description": "B", "amount": 20}]
    predicted = [{"description": "A", "amount": 10}]
    r = score_line_items(predicted, expected)
    assert r["recall"] == 0.5
    assert r["precision"] == 1.0
    assert not r["count_match"]


def test_hallucination_detects_ungrounded_value():
    source = "Acme Corp invoice INV-001 date 2026-05-10 Cloud hosting total 1250.50"
    grounded = hallucination_check(PERFECT, source)
    assert grounded["rate"] == 0.0
    invented = dict(PERFECT, client_name="Globex Industries")
    bad = hallucination_check(invented, source)
    assert bad["rate"] > 0.0


def test_report_scoring():
    invoices = [
        {"client_name": "Acme Corp", "total_amount": 1250.50},
        {"client_name": "Globex LLC", "total_amount": 2500.00},
    ]
    good = "Client Report: Acme Corp total 1250.50\nClient Report: Globex LLC total 2500.00"
    s = score_report_text(good, invoices)
    assert s["client_name_recall"] == 1.0
    assert s["client_total_recall"] == 1.0
    empty = score_report_text("nothing here", invoices)
    assert empty["overall"] == 0.0


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"\n{len(fns)} tests passed.")


if __name__ == "__main__":
    _run_all()
