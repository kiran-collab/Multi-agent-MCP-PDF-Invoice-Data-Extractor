"""
Stage 3 — Orchestrator Agent.

The coordinator. It owns the overall workflow and delegates to the two
specialized sub-agents over A2A:

    FilesAgent       -> list invoice files in a Box folder
    ExtractionAgent  -> extract structured fields from each file

The orchestrator then aggregates the per-client reports itself (the "reporting"
capability). It is also served as an A2A server, so an external A2A client can
send it the user's request.

Flow it runs:
    1. Ask FilesAgent for the list of invoices in the folder.
    2. For each file, ask ExtractionAgent for the structured invoice.
    3. Aggregate everything into per-client reports and return them.

Sub-agents are reached through RemoteA2aAgent connections, which let one ADK
agent call another running agent via its A2A endpoint.
"""

import json
import os

from google.adk.agents.llm_agent import LlmAgent
from google.adk.a2a import RemoteA2aAgent, to_a2a_app  # type: ignore

from invoice_models import Invoice, build_client_reports


# --- Remote handles to the sub-agents (A2A clients) -----------------------
files_agent = RemoteA2aAgent(
    name="FilesAgent",
    url=os.getenv("FILES_AGENT_URL", "http://localhost:8001"),
)

extraction_agent = RemoteA2aAgent(
    name="ExtractionAgent",
    url=os.getenv("EXTRACTION_AGENT_URL", "http://localhost:8002"),
)


# --- Local reporting tool -------------------------------------------------
def build_reports(invoices_json: str) -> str:
    """Aggregate a JSON list of invoices into per-client text reports.

    Args:
        invoices_json: JSON string — a list of structured invoice objects.
    Returns:
        A single string containing all per-client reports.
    """
    raw = json.loads(invoices_json)
    invoices = [Invoice.from_dict(d, d.get("source_file", "")) for d in raw]
    reports = build_client_reports(invoices)
    return "\n\n".join(r.render() for r in reports)


# --- Orchestrator ---------------------------------------------------------
orchestrator = LlmAgent(
    name="InvoiceOrchestrator",
    model=os.getenv("INVOICE_LLM_MODEL", "gemini-2.5-flash"),
    instruction=(
        "You coordinate invoice processing. When given a Box folder ID:\n"
        "1. Ask the FilesAgent to list the invoice files in that folder.\n"
        "2. For EACH file returned, ask the ExtractionAgent to extract the "
        "   structured invoice (pass the file's id and name).\n"
        "3. Collect all the extracted invoice JSON objects into a JSON array "
        "   and call build_reports with it.\n"
        "4. Return the final per-client reports to the user.\n"
        "Be systematic and make sure every file is processed exactly once."
    ),
    sub_agents=[files_agent, extraction_agent],
    tools=[build_reports],
)

# Serve the orchestrator itself over A2A so an external client can call it.
a2a_app = to_a2a_app(orchestrator)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        a2a_app, host="0.0.0.0", port=int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    )
