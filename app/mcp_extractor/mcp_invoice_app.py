"""
Stage 2 — MCP-compliant invoice app.

Same end goal as Stage 1 (structured invoices + per-client reports), but file
discovery and text extraction now happen through the Box MCP server instead of
local code. The app processes files directly in Box — no manual downloads.

Pipeline:
    1. Ask the Box MCP server to list files in a Box folder.
    2. Ask the Box MCP server to extract text from each file.
    3. Use the LLM to extract structured fields (unchanged from Stage 1).
    4. Aggregate per-client reports.

Run:
    BOX_DEVELOPER_TOKEN=... python mcp_invoice_app.py <box_folder_id>
"""

import asyncio
import sys
from pathlib import Path
from typing import List

from invoice_models import Invoice, build_client_reports
from llm_extraction import extract_invoice_fields
from box_mcp_client import (
    discover_tools,
    list_folder_files,
    extract_text,
)


async def process_box_folder(folder_id: str) -> List[Invoice]:
    """Process every invoice in a Box folder using MCP tools."""
    # Optional: confirm what the server actually offers.
    tools = await discover_tools()
    print(f"Box MCP tools available: {tools}\n")

    invoices: List[Invoice] = []
    files = await list_folder_files(folder_id)
    print(f"Found {len(files)} candidate files in folder {folder_id}\n")

    for f in files:
        print(f"Processing {f['name']} (id={f['id']}) ...")
        text = await extract_text(f["id"])
        if not text.strip():
            print(f"  ! no text returned for {f['name']}, skipping")
            continue
        # Extraction itself stays a plain (sync) LLM call.
        invoice = await asyncio.to_thread(
            extract_invoice_fields, text, f["name"]
        )
        print(f"  -> {invoice.client_name}: {invoice.total_amount} {invoice.currency}")
        invoices.append(invoice)
    return invoices


async def main(folder_id: str, out_dir: str = "reports"):
    invoices = await process_box_folder(folder_id)
    reports = build_client_reports(invoices)

    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    for report in reports:
        text = report.render()
        print("\n" + text)
        (out / f"report_{report.client_name.replace(' ', '_')}.txt").write_text(text)


if __name__ == "__main__":
    folder_id = sys.argv[1] if len(sys.argv) > 1 else "0"  # "0" = Box root
    asyncio.run(main(folder_id))
