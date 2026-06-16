"""
Lightweight, dependency-free execution tracing for agent evaluation.

Modern agent evaluation is trace-based, not just final-answer-based: you want a
record of which agent did what, in what order, and whether each step succeeded.
This module records that record in the shape described in the eval spec:

    {
      "trace_id": "...",
      "folder_id": "0",
      "steps": [
        {"agent": "FilesAgent", "tool": "list_invoices", "status": "success", ...},
        ...
      ]
    }

It has zero third-party dependencies. If ``langfuse`` is installed and
LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are set, ``Trace.export_langfuse()``
will additionally push the trace to Langfuse; otherwise it is a no-op. This lets
the same harness run fully offline or feed a production tracing backend.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class Trace:
    """Collects ordered steps for a single evaluation run."""

    def __init__(self, trace_id: str, **context: Any):
        self.trace_id = trace_id
        self.context = context
        self.steps: List[Dict[str, Any]] = []

    def step(self, agent: str, tool: str, status: str = "success", **extra: Any) -> None:
        """Record one agent/tool step. ``status`` is success | error | empty."""
        entry = {"agent": agent, "tool": tool, "status": status}
        entry.update(extra)
        self.steps.append(entry)

    def to_dict(self) -> Dict[str, Any]:
        return {"trace_id": self.trace_id, **self.context, "steps": self.steps}

    def delegation_ok(self, expected_order: List[str]) -> bool:
        """True if the recorded agents appear in the expected relative order.

        Used to score the orchestrator: e.g. FilesAgent must run before
        ExtractionAgent before the reporting step.
        """
        seen = [s["agent"] for s in self.steps]
        idx = -1
        for agent in expected_order:
            if agent not in seen[idx + 1 :]:
                return False
            idx = seen.index(agent, idx + 1)
        return True

    def export_langfuse(self) -> bool:
        """Best-effort push to Langfuse. Returns True if exported, else False."""
        if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
            return False
        try:
            from langfuse import Langfuse  # type: ignore
        except Exception:
            return False
        client = Langfuse()
        t = client.trace(name="invoice-eval", id=self.trace_id, metadata=self.context)
        for s in self.steps:
            t.span(name=f"{s['agent']}.{s['tool']}", metadata=s)
        client.flush()
        return True


class TraceLog:
    """A collection of traces, persistable to a JSON file."""

    def __init__(self) -> None:
        self.traces: List[Trace] = []

    def new(self, trace_id: str, **context: Any) -> Trace:
        t = Trace(trace_id, **context)
        self.traces.append(t)
        return t

    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(
            json.dumps([t.to_dict() for t in self.traces], indent=2)
        )
