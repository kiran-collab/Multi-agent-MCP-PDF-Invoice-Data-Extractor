"""
Stage 2 — Box MCP client wrapper.

Instead of listing files and extracting text ourselves (Stage 1), we delegate
those tasks to the Box MCP server. This module is a thin async client that:

    1. Spins up / connects to the Box MCP server.
    2. Discovers the tools it exposes.
    3. Calls the relevant tools (list folder items, extract text).

The Model Context Protocol standardizes how tools/resources are exposed to an
app, so we no longer write custom Box API or PDF-parsing code — the server
provides those capabilities as callable tools.

Notes:
    * Box publishes an MCP server; the exact command/URL and tool names depend
      on the server version. The tool names below ("list_folder",
      "extract_text") are placeholders — discover real names at runtime via
      `list_tools()` and adjust.
    * Auth: set BOX_DEVELOPER_TOKEN (or whatever the server expects) in the env.
"""

import os
from contextlib import asynccontextmanager
from typing import Any, Dict, List

# Official MCP Python SDK
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# How to launch the Box MCP server. Adjust command/args/env to match the
# server you have installed (could also be an HTTP/SSE transport).
BOX_MCP_PARAMS = StdioServerParameters(
    command=os.getenv("BOX_MCP_COMMAND", "box-mcp-server"),
    args=os.getenv("BOX_MCP_ARGS", "").split() if os.getenv("BOX_MCP_ARGS") else [],
    env={
        "BOX_DEVELOPER_TOKEN": os.getenv("BOX_DEVELOPER_TOKEN", ""),
        **os.environ,
    },
)


@asynccontextmanager
async def box_session():
    """Open an MCP client session against the Box MCP server."""
    async with stdio_client(BOX_MCP_PARAMS) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            yield session


async def discover_tools() -> List[str]:
    """List the tools the Box MCP server exposes (names only)."""
    async with box_session() as session:
        tools = await session.list_tools()
        return [t.name for t in tools.tools]


def _first_text(result: Any) -> str:
    """Pull text content out of an MCP tool result."""
    parts = getattr(result, "content", []) or []
    texts = [getattr(p, "text", "") for p in parts if getattr(p, "text", "")]
    return "\n".join(texts)


async def list_folder_files(folder_id: str) -> List[Dict[str, str]]:
    """List items in a Box folder via the MCP server.

    Returns a list of {"id": ..., "name": ...} dicts for invoice files.
    Replace the tool name / argument keys with the real ones from
    discover_tools().
    """
    async with box_session() as session:
        result = await session.call_tool(
            "list_folder", arguments={"folder_id": folder_id}
        )
        text = _first_text(result)
        import json

        try:
            items = json.loads(text)
        except json.JSONDecodeError:
            items = []
        # Keep only PDFs (or whatever invoice formats you support)
        return [
            {"id": it["id"], "name": it["name"]}
            for it in items
            if str(it.get("name", "")).lower().endswith((".pdf", ".docx", ".png", ".jpg"))
        ]


async def extract_text(file_id: str) -> str:
    """Extract text from a Box file via the MCP server (no local download)."""
    async with box_session() as session:
        result = await session.call_tool(
            "extract_text", arguments={"file_id": file_id}
        )
        return _first_text(result)
