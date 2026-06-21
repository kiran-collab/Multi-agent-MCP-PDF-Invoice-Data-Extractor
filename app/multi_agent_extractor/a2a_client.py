"""
Stage 3 — A2A Client.

Entry point a user runs. It sends a natural-language request to the
Orchestrator's A2A endpoint and prints the streamed response. The orchestrator
does the rest (delegating to FilesAgent and ExtractionAgent).

Run order (each in its own terminal):
    python files_agent_server.py          # port 8001
    python extraction_agent_server.py     # port 8002
    python orchestrator_agent_server.py   # port 8000
    python a2a_client.py <box_folder_id>
"""

import asyncio
import os
import sys

# A2A client SDK. Import paths depend on the a2a-sdk version you install.
from a2a.client import A2AClient  # type: ignore


ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL", "http://localhost:8000")


async def run(folder_id: str):
    client = A2AClient(url=ORCHESTRATOR_URL)

    prompt = (
        f"Process all invoices in Box folder {folder_id}. "
        f"Extract client name, total amount, and purchased products from each, "
        f"then give me a per-client summary report."
    )

    print(f"-> Sending request to orchestrator at {ORCHESTRATOR_URL}\n")
    async for event in client.send_message_streaming(prompt):
        # Print whatever text the orchestrator streams back.
        text = getattr(event, "text", None)
        if text:
            print(text, end="", flush=True)
    print()


if __name__ == "__main__":
    folder_id = sys.argv[1] if len(sys.argv) > 1 else "0"
    asyncio.run(run(folder_id))
