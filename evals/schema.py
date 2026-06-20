"""
Pydantic models describing the structured-invoice output contract.

These mirror the dataclasses in each app's ``invoice_models.py`` but add real
validation: required fields, type coercion, and clear per-field error reporting.
The eval harness uses them to score *schema validity* — i.e. whether the LLM's
output actually conforms to the contract the extraction prompt promises.

Pydantic v2. ``validate_invoice`` never raises; it returns a structured result
so a single bad case can't abort a whole eval run.
"""

from __future__ import annotations

import logging
from typing import List

from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger("evals.schema")


class LineItemModel(BaseModel):
    """A single purchased product / line on an invoice."""

    model_config = ConfigDict(extra="ignore")

    description: str
    quantity: float = 1.0
    unit_price: float = 0.0
    amount: float = 0.0


class InvoiceModel(BaseModel):
    """Required output contract for a structured invoice.

    The core fields have NO defaults, so a missing key is a validation error —
    that is exactly what the "schema validity" metric is meant to catch.
    """

    model_config = ConfigDict(extra="ignore")

    invoice_id: str
    client_name: str
    invoice_date: str
    currency: str
    total_amount: float
    line_items: List[LineItemModel]


def validate_invoice(data: dict) -> dict:
    """Validate a predicted invoice dict against InvoiceModel.

    Returns a dict with the same shape the stdlib check used, so callers don't
    care which engine ran:
        {"valid": bool, "missing": [...], "wrong_type": [...], "errors": [...]}
    """
    try:
        InvoiceModel.model_validate(data)
        return {"valid": True, "missing": [], "wrong_type": [], "errors": []}
    except ValidationError as exc:
        missing, wrong_type, errors = [], [], []
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"])
            errors.append({"field": field, "type": err["type"], "msg": err["msg"]})
            if err["type"] in ("missing", "missing_argument"):
                missing.append(field)
            else:
                wrong_type.append(field)
        logger.warning("invoice schema invalid: missing=%s wrong_type=%s", missing, wrong_type)
        return {"valid": False, "missing": missing, "wrong_type": wrong_type, "errors": errors}
