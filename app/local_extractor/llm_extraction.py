"""
Shared LLM extraction logic.

`extract_invoice_fields` takes raw invoice text and asks an LLM to return the
structured fields as JSON. All three stages reuse this so the extraction prompt
lives in exactly one place.

This uses Google's Gemini via the google-genai client, but the function is
deliberately thin: swap `_call_llm` for any provider you like.
"""

import json
import os
from typing import Optional

from invoice_models import Invoice

# --- LLM client -----------------------------------------------------------
# Configure once. Replace with your own provider/credentials as needed.
try:
    from google import genai
    from google.genai import types

    _client: Optional["genai.Client"] = genai.Client(
        api_key=os.getenv("GOOGLE_API_KEY")
    )
except Exception:  # keep import-time failures from breaking the stages
    _client = None
    types = None


EXTRACTION_PROMPT = """\
You are an invoice parser. Read the invoice text below and return ONLY a JSON
object (no markdown, no prose) with exactly these keys:

{{
  "invoice_id": string,
  "client_name": string,
  "invoice_date": string (YYYY-MM-DD if possible),
  "currency": string (ISO code, e.g. USD),
  "total_amount": number,
  "line_items": [
    {{"description": string, "quantity": number,
      "unit_price": number, "amount": number}}
  ]
}}

If a field is missing, use an empty string for text, 0 for numbers, and an
empty list for line_items. Do not invent data.

Invoice text:
---
{invoice_text}
---
"""

MODEL = os.getenv("INVOICE_LLM_MODEL", "gemini-2.5-flash")


def _call_llm(prompt: str) -> str:
    """Send a prompt to the LLM and return the raw text response."""
    if _client is None:
        raise RuntimeError(
            "LLM client not configured. Set GOOGLE_API_KEY and install google-genai."
        )
    response = _client.models.generate_content(model=MODEL, contents=prompt)
    return response.text


def _strip_code_fences(text: str) -> str:
    """Remove ```json ... ``` fences the model sometimes adds."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]  # drop the opening fence line
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def extract_invoice_fields(invoice_text: str, source_file: str = "") -> Invoice:
    """Extract structured invoice fields from raw text using the LLM."""
    prompt = EXTRACTION_PROMPT.format(invoice_text=invoice_text[:8000])
    raw = _call_llm(prompt)
    data = json.loads(_strip_code_fences(raw))
    return Invoice.from_dict(data, source_file=source_file)
