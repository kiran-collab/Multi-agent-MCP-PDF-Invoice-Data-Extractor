"""
Stage 3 — Extraction Agent.

Specialized agent responsible for TEXT EXTRACTION + FIELD PARSING: given a Box
file ID, it extracts the file's text via the Box MCP server and then parses the
structured invoice fields with the LLM. Exposed as an A2A server.

Responsibilities:
    * Extract text from a Box file (via Box MCP).
    * Parse structured fields (client, total, products...) from that text.
    * Return the structured invoice as JSON.

It does NOT decide which files to process (Files Agent) or build the final
reports (Reporting / Orchestrator).
"""

import json
import os

from google.adk.agents.llm_agent import LlmAgent

from box_mcp_client import extract_text
from llm_extraction import extract_invoice_fields

from google.adk.a2a import to_a2a_app  # type: ignore


async def extract_invoice(file_id: str, file_name: str = "") -> str:
    """Extract structured invoice fields from a single Box file.

    Args:
        file_id: The Box file ID to process.
        file_name: Optional original file name (for traceability).
    Returns:
        JSON string of the structured invoice.
    """
    text = await extract_text(file_id)
    if not text.strip():
        return json.dumps({"error": "no text extracted", "source_file": file_name})
    # extract_invoice_fields is a sync LLM call; run it off the event loop.
    import asyncio

    invoice = await asyncio.to_thread(extract_invoice_fields, text, file_name)
    return json.dumps(invoice.to_dict())


extraction_agent = LlmAgent(
    name="ExtractionAgent",
    model=os.getenv("INVOICE_LLM_MODEL", "gemini-2.5-flash"),
    instruction=(
        "You are the Extraction Agent. Given a Box file ID, call extract_invoice "
        "to obtain the structured invoice fields and return them as JSON. "
        "Process exactly the file you are given; do not invent data."
    ),
    tools=[extract_invoice],
)

a2a_app = to_a2a_app(extraction_agent)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        a2a_app, host="0.0.0.0", port=int(os.getenv("EXTRACTION_AGENT_PORT", "8002"))
    )
