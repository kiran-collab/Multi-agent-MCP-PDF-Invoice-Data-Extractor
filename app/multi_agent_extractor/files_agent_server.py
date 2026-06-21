"""
Stage 3 — Files Agent.

Specialized agent responsible for DISCOVERY only: given a Box folder, it lists
the invoice files inside it using the Box MCP server. It exposes one tool,
`list_invoices`, and is served as an A2A server so the orchestrator can call it.

Responsibilities:
    * List files in a Box folder (via Box MCP).
    * Return a clean list of {id, name} invoice candidates.

It does NOT extract text or parse fields — that's the Extraction Agent's job.
This separation is the whole point of the multi-agent design: each agent has a
narrow, well-defined capability.
"""

import json
import os

from google.adk.agents.llm_agent import LlmAgent

from box_mcp_client import list_folder_files

# A2A serving helpers from the ADK. Exact import paths can vary by ADK version;
# adjust to match your installed google-adk.
from google.adk.a2a import to_a2a_app  # type: ignore


async def list_invoices(folder_id: str) -> str:
    """List invoice files in a Box folder.

    Args:
        folder_id: The Box folder ID to scan.
    Returns:
        JSON string: list of {"id": ..., "name": ...} objects.
    """
    files = await list_folder_files(folder_id)
    return json.dumps(files)


files_agent = LlmAgent(
    name="FilesAgent",
    model=os.getenv("INVOICE_LLM_MODEL", "gemini-2.5-flash"),
    instruction=(
        "You are the Files Agent. Your only job is to list invoice files in a "
        "Box folder when asked. Call the list_invoices tool with the folder ID "
        "and return the resulting list. Do not parse or summarize the files."
    ),
    tools=[list_invoices],
)

# A2A server application (run with uvicorn or the ADK CLI).
a2a_app = to_a2a_app(files_agent)

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(a2a_app, host="0.0.0.0", port=int(os.getenv("FILES_AGENT_PORT", "8001")))
