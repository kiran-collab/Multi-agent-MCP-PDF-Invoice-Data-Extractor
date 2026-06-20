"""
Scoring functions for invoice-extraction evaluation.

Pure-stdlib, dependency-free, and side-effect-free: everything here operates on
plain dicts / strings so it can be unit-tested offline without Box, Gemini, or a
running agent. The eval runners call the real app pipelines to produce
``predicted``, then hand it here for scoring.

Metrics implemented (see evals/README.md for the rationale of each):
  - json validity            is_valid_json
  - schema validity          check_schema
  - field exact match        score_invoice -> fields.*
  - numeric tolerance        score_invoice -> total_amount_match
  - line item recall/prec.   score_invoice -> line_items.*
  - hallucination rate       hallucination_check (needs source text)
  - report correctness       score_report_text (app3 end-to-end)
"""

from __future__ import annotations

import json
import logging
import re
from math import isclose
from typing import Any, Dict, List, Optional

logger = logging.getLogger("evals.scorers")

# Schema validation is done with pydantic when available (see schema.py); we keep
# a stdlib fallback so the scorers still run in a minimal environment.
try:
    from schema import validate_invoice as _validate_invoice
    _HAVE_PYDANTIC = True
except Exception:  # pragma: no cover - exercised only without pydantic
    _validate_invoice = None
    _HAVE_PYDANTIC = False
    logger.warning("pydantic schema unavailable; falling back to stdlib type checks")

# Required output contract for a structured invoice (key -> acceptable types).
REQUIRED_FIELDS: Dict[str, Any] = {
    "invoice_id": str,
    "client_name": str,
    "invoice_date": str,
    "currency": str,
    "total_amount": (int, float),
    "line_items": list,
}

# Money fields are compared with a small absolute tolerance, not ==.
NUMERIC_TOLERANCE = 0.01


# --- low-level helpers ----------------------------------------------------
def _norm_str(value: Any) -> str:
    return str(value if value is not None else "").strip().lower()


def _to_float(value: Any) -> float:
    try:
        return float(value if value not in (None, "") else 0)
    except (TypeError, ValueError):
        return 0.0


def _num_close(a: Any, b: Any, tol: float = NUMERIC_TOLERANCE) -> bool:
    return isclose(_to_float(a), _to_float(b), abs_tol=tol)


# --- structural checks ----------------------------------------------------
def is_valid_json(raw: str) -> bool:
    """True if ``raw`` parses as JSON. Mirrors the json.loads in llm_extraction."""
    try:
        json.loads(raw)
        return True
    except (TypeError, ValueError):
        return False


def check_schema(predicted: dict) -> dict:
    """Verify the required keys are present with the right types.

    Uses pydantic (schema.InvoiceModel) when available for real validation and
    coercion; otherwise falls back to a coarse stdlib type check.
    """
    if _HAVE_PYDANTIC:
        return _validate_invoice(predicted)

    missing: List[str] = []
    wrong_type: List[str] = []
    for key, expected_type in REQUIRED_FIELDS.items():
        if key not in predicted:
            missing.append(key)
        elif not isinstance(predicted[key], expected_type):
            wrong_type.append(key)
    return {
        "missing": missing,
        "wrong_type": wrong_type,
        "valid": not missing and not wrong_type,
        "errors": [],
    }


# --- line items -----------------------------------------------------------
def _items_match(pred: dict, exp: dict, tol: float) -> bool:
    """Heuristic single line-item match: description aligns, or amount does."""
    desc_p, desc_e = _norm_str(pred.get("description")), _norm_str(exp.get("description"))
    desc_ok = bool(desc_e) and (desc_p == desc_e or desc_e in desc_p or desc_p in desc_e)
    amount_ok = _num_close(pred.get("amount"), exp.get("amount"), tol)
    if desc_e:
        # When we have an expected description, require it to line up; amount is
        # a strong corroborator but a clear description match is enough.
        return desc_ok or (desc_ok and amount_ok)
    # No description to compare on -> fall back to the amount.
    return amount_ok


def score_line_items(
    predicted_items: List[dict], expected_items: List[dict], tol: float = NUMERIC_TOLERANCE
) -> dict:
    """Greedy one-to-one match; returns recall, precision, and count match."""
    predicted_items = predicted_items or []
    expected_items = expected_items or []
    remaining = list(predicted_items)
    matched = 0
    for exp in expected_items:
        for i, pred in enumerate(remaining):
            if _items_match(pred, exp, tol):
                matched += 1
                remaining.pop(i)
                break
    n_exp, n_pred = len(expected_items), len(predicted_items)
    return {
        "expected": n_exp,
        "predicted": n_pred,
        "matched": matched,
        "recall": (matched / n_exp) if n_exp else 1.0,
        "precision": (matched / n_pred) if n_pred else (1.0 if n_exp == 0 else 0.0),
        "count_match": n_exp == n_pred,
    }


# --- hallucination --------------------------------------------------------
def _grounded(value: Any, haystack: str) -> bool:
    """Is a scalar value present in the (normalized) source text?"""
    v = _norm_str(value)
    if not v:
        return True  # empty/zero is never a hallucination
    if v in haystack:
        return True
    # Numbers: also try common surface forms (thousands separators, no trailing .0).
    f = _to_float(value)
    if f:
        for form in {f"{f:.2f}", f"{f:g}", f"{f:,.2f}", str(int(f)) if f == int(f) else ""}:
            if form and form.lower() in haystack:
                return True
    return False


def hallucination_check(predicted: dict, source_text: str) -> dict:
    """Heuristic: fraction of predicted scalar values not found in the source.

    The extraction prompt says "Do not invent data", so any value the model
    emits should be traceable to the invoice text. This is a heuristic (a value
    can legitimately be reformatted), so treat the rate as a signal, not a gate.
    """
    haystack = _norm_str(source_text)
    values: List[Any] = [
        predicted.get("invoice_id"),
        predicted.get("client_name"),
        predicted.get("invoice_date"),
        predicted.get("total_amount"),
    ]
    for li in predicted.get("line_items", []) or []:
        values += [li.get("description"), li.get("amount")]

    checked = [v for v in values if _norm_str(v)]  # skip empties/zeros
    unsupported = [v for v in checked if not _grounded(v, haystack)]
    return {
        "checked": len(checked),
        "unsupported": len(unsupported),
        "unsupported_values": unsupported,
        "rate": (len(unsupported) / len(checked)) if checked else 0.0,
    }


# --- top-level invoice score ---------------------------------------------
def score_invoice(
    predicted: dict, expected: dict, source_text: Optional[str] = None
) -> dict:
    """Score one predicted invoice against its golden expected value.

    Returns a structured dict of per-metric results plus a single ``overall``
    scalar in [0, 1] (the mean of the headline signals).
    """
    fields = {
        "invoice_id": predicted.get("invoice_id") == expected.get("invoice_id"),
        "client_name": _norm_str(predicted.get("client_name"))
        == _norm_str(expected.get("client_name")),
        "invoice_date": _norm_str(predicted.get("invoice_date"))
        == _norm_str(expected.get("invoice_date")),
        "currency": _norm_str(predicted.get("currency")) == _norm_str(expected.get("currency")),
    }
    total_match = _num_close(predicted.get("total_amount"), expected.get("total_amount"))
    items = score_line_items(predicted.get("line_items", []), expected.get("line_items", []))
    schema = check_schema(predicted)

    result: dict = {
        "fields": fields,
        "total_amount_match": total_match,
        "line_items": items,
        "schema_valid": schema["valid"],
        "schema": schema,
    }

    headline = list(fields.values()) + [total_match, items["recall"], schema["valid"]]
    if source_text is not None:
        hall = hallucination_check(predicted, source_text)
        result["hallucination"] = hall
        headline.append(1.0 - hall["rate"])
        if hall["rate"] > 0:
            logger.warning("ungrounded values for %s: %s",
                           predicted.get("invoice_id") or "?", hall["unsupported_values"])

    result["overall"] = sum(float(x) for x in headline) / len(headline)
    if not schema["valid"]:
        logger.info("schema invalid for %s: missing=%s wrong_type=%s",
                    predicted.get("invoice_id") or "?", schema["missing"], schema["wrong_type"])
    logger.debug("scored %s -> overall=%.3f", predicted.get("invoice_id") or "?", result["overall"])
    return result


# --- report-level score (app3 end-to-end) ---------------------------------
_NUM_RE = re.compile(r"[-+]?\d[\d,]*\.?\d*")


def score_report_text(report_text: str, expected_invoices: List[dict]) -> dict:
    """Check a rendered per-client report against the expected invoices.

    The orchestrator returns human-readable report text (not JSON), so we verify
    business-level correctness: each client is named and their summed spend
    appears in the report.
    """
    haystack = _norm_str(report_text)
    numbers = {n.replace(",", "") for n in _NUM_RE.findall(report_text or "")}

    by_client: Dict[str, float] = {}
    for inv in expected_invoices:
        name = inv.get("client_name", "Unknown") or "Unknown"
        by_client[name] = by_client.get(name, 0.0) + _to_float(inv.get("total_amount"))

    clients_found, totals_found = 0, 0
    per_client = []
    for name, total in by_client.items():
        name_ok = _norm_str(name) in haystack
        total_ok = any(_num_close(total, n) for n in numbers)
        clients_found += int(name_ok)
        totals_found += int(total_ok)
        per_client.append({"client": name, "name_found": name_ok, "total_found": total_ok})

    n = len(by_client) or 1
    return {
        "clients_expected": len(by_client),
        "client_name_recall": clients_found / n,
        "client_total_recall": totals_found / n,
        "per_client": per_client,
        "overall": (clients_found + totals_found) / (2 * n),
    }


# --- aggregation ----------------------------------------------------------
def aggregate(results: List[dict]) -> dict:
    """Roll up a list of per-case result records into summary metrics."""
    scored = [r for r in results if isinstance(r.get("scores"), dict)]
    if not scored:
        return {"cases": len(results), "scored": 0}

    def _mean(fn):
        vals = [fn(r["scores"]) for r in scored if fn(r["scores"]) is not None]
        return round(sum(vals) / len(vals), 4) if vals else None

    return {
        "cases": len(results),
        "scored": len(scored),
        "overall": _mean(lambda s: s.get("overall")),
        "invoice_id_acc": _mean(lambda s: float(s["fields"]["invoice_id"]) if "fields" in s else None),
        "client_name_acc": _mean(lambda s: float(s["fields"]["client_name"]) if "fields" in s else None),
        "date_acc": _mean(lambda s: float(s["fields"]["invoice_date"]) if "fields" in s else None),
        "currency_acc": _mean(lambda s: float(s["fields"]["currency"]) if "fields" in s else None),
        "total_amount_acc": _mean(lambda s: float(s["total_amount_match"]) if "total_amount_match" in s else None),
        "line_item_recall": _mean(lambda s: s["line_items"]["recall"] if "line_items" in s else None),
        "schema_valid_rate": _mean(lambda s: float(s["schema_valid"]) if "schema_valid" in s else None),
        "hallucination_rate": _mean(lambda s: s["hallucination"]["rate"] if "hallucination" in s else None),
    }
