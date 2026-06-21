#!/usr/bin/env python3
"""
Generate the architecture diagrams (SVG) for the three apps.

Pure-stdlib SVG authoring — no third-party deps. Render to PNG with:
    rsvg-convert -z 2 docs/images/app1_local_extractor.svg \
        -o docs/images/app1_local_extractor.png

A consistent colour legend is shared across all three diagrams:
    io     blue    input / output
    app    green   application code
    agent  purple  ADK LlmAgent
    ext    red     Gemini LLM
    mcp    amber   Box MCP tool
"""

from __future__ import annotations

import html
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "images"

PALETTE = {
    "io":    ("#EAF2FF", "#2F6FED", "#0B2A6B"),
    "app":   ("#EAF7EE", "#2E9E5B", "#0B3D1F"),
    "agent": ("#F1ECFB", "#7E57C2", "#3A2A63"),
    "ext":   ("#FDECEC", "#E0524D", "#5C0B0A"),
    "mcp":   ("#FFF6E5", "#E8A317", "#5C3C00"),
}
ARROW = "#5A6472"
CONTAINER = "#AAB2BF"
CONTAINER_LBL = "#5A6472"
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


class Node:
    def __init__(self, x, y, w, h, lines, cls):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.lines = lines if isinstance(lines, list) else [lines]
        self.cls = cls

    @property
    def cx(self): return self.x + self.w / 2
    @property
    def cy(self): return self.y + self.h / 2
    @property
    def left(self): return (self.x, self.cy)
    @property
    def right(self): return (self.x + self.w, self.cy)
    @property
    def top(self): return (self.cx, self.y)
    @property
    def bottom(self): return (self.cx, self.y + self.h)


class SVG:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.body = []

    def _esc(self, s):
        return html.escape(str(s))

    def rect(self, x, y, w, h, fill, stroke, rx=12, sw=1.6, dash=None, shadow=True):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        f = ' filter="url(#ds)"' if shadow else ""
        self.body.append(
            f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" ry="{rx}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}{f}/>'
        )

    def text(self, x, y, s, size=14, color="#111", weight="400", anchor="middle"):
        self.body.append(
            f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
            f'font-weight="{weight}" fill="{color}" text-anchor="{anchor}">{self._esc(s)}</text>'
        )

    def node(self, n: Node):
        fill, stroke, tcolor = PALETTE[n.cls]
        self.rect(n.x, n.y, n.w, n.h, fill, stroke)
        total = len(n.lines)
        line_h = 17
        start = n.cy - (total - 1) * line_h / 2 + 5
        for i, ln in enumerate(n.lines):
            mono = ln.startswith("`") and ln.endswith("`")
            txt = ln.strip("`")
            self.body.append(
                f'<text x="{n.cx}" y="{start + i*line_h}" font-family="{("ui-monospace, Menlo, monospace") if mono else FONT}" '
                f'font-size="{13 if mono else 14}" font-weight="{"600" if i==0 and not mono else "400"}" '
                f'fill="{tcolor}" text-anchor="middle">{self._esc(txt)}</text>'
            )

    def container(self, x, y, w, h, label):
        self.rect(x, y, w, h, "none", CONTAINER, rx=16, sw=1.4, dash="6 5", shadow=False)
        self.body.append(
            f'<text x="{x+14}" y="{y+22}" font-family="{FONT}" font-size="13" '
            f'font-weight="600" fill="{CONTAINER_LBL}" text-anchor="start">{self._esc(label)}</text>'
        )

    def arrow(self, p1, p2, label=None, both=False, mid=None, dash=None):
        x1, y1 = p1
        x2, y2 = p2
        start = ' marker-start="url(#ahs)"' if both else ""
        dd = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{ARROW}" '
            f'stroke-width="1.8" marker-end="url(#ah)"{start}{dd}/>'
        )
        if label:
            mx, my = mid if mid else ((x1 + x2) / 2, (y1 + y2) / 2)
            self._label(mx, my, label)

    def elbow(self, pts, label=None, both=False, lbl_at=None, dash=None):
        d = " ".join(f"{x},{y}" for x, y in pts)
        start = ' marker-start="url(#ahs)"' if both else ""
        dd = f' stroke-dasharray="{dash}"' if dash else ""
        self.body.append(
            f'<polyline points="{d}" fill="none" stroke="{ARROW}" stroke-width="1.8" '
            f'marker-end="url(#ah)"{start}{dd}/>'
        )
        if label:
            mx, my = lbl_at if lbl_at else pts[len(pts) // 2]
            self._label(mx, my, label)

    def _label(self, mx, my, label):
        w = 7.1 * len(label) + 12
        self.body.append(
            f'<rect x="{mx - w/2}" y="{my - 11}" width="{w}" height="19" rx="5" '
            f'fill="#FFFFFF" stroke="#E3E7EE" stroke-width="1"/>'
        )
        self.text(mx, my + 3, label, size=12, color="#3A424E")

    def render(self, trim_top=0):
        h = self.h - trim_top
        defs = (
            '<defs>'
            f'<marker id="ah" markerWidth="11" markerHeight="11" refX="8" refY="3.2" '
            f'orient="auto" markerUnits="userSpaceOnUse"><path d="M0,0 L8,3.2 L0,6.4 Z" fill="{ARROW}"/></marker>'
            f'<marker id="ahs" markerWidth="11" markerHeight="11" refX="0" refY="3.2" '
            f'orient="auto" markerUnits="userSpaceOnUse"><path d="M8,0 L0,3.2 L8,6.4 Z" fill="{ARROW}"/></marker>'
            '<filter id="ds" x="-20%" y="-20%" width="140%" height="140%">'
            '<feDropShadow dx="0" dy="1.5" stdDeviation="1.6" flood-color="#1B2330" flood-opacity="0.16"/>'
            '</filter></defs>'
        )
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{h}" '
            f'viewBox="0 0 {self.w} {h}" font-family="{FONT}">'
            f'<rect width="{self.w}" height="{h}" fill="#FFFFFF"/>'
            f'{defs}<g transform="translate(0,{-trim_top})">{"".join(self.body)}</g></svg>'
        )


def legend(svg: SVG, x, y):
    items = [("io", "Input / Output"), ("app", "Application code"),
             ("agent", "ADK LlmAgent"), ("ext", "Gemini LLM"), ("mcp", "Box MCP tool")]
    svg.text(x, y - 14, "Legend", size=12, color="#6B7480", weight="600", anchor="start")
    cx = x
    for cls, name in items:
        fill, stroke, _ = PALETTE[cls]
        svg.rect(cx, y - 11, 16, 16, fill, stroke, rx=4, sw=1.4, shadow=False)
        svg.text(cx + 22, y + 2, name, size=12, color="#3A424E", anchor="start")
        cx += 30 + 7.4 * len(name) + 26


# --------------------------------------------------------------------------
def app1():
    s = SVG(1180, 320)
    y = 150
    pdf = Node(40, y - 37, 190, 74, ["Local PDF", "folder"], "io")
    read = Node(285, y - 37, 190, 74, ["Read & extract", "text"], "app")
    llm = Node(530, y - 37, 200, 74, ["Gemini LLM", "extract_invoice_fields"], "ext")
    agg = Node(785, y - 37, 175, 74, ["build_client_", "reports"], "app")
    out = Node(1010, y - 37, 130, 74, ["Per-client", "reports"], "io")
    for n in (pdf, read, llm, agg, out):
        s.node(n)
    s.arrow(pdf.right, read.left, "each file")
    s.arrow(read.right, llm.left, "raw text")
    s.arrow(llm.right, agg.left, "Invoice JSON")
    s.arrow(agg.right, out.left, "ClientReport")
    legend(s, 40, 285)
    return "app1_local_extractor.svg", s.render(trim_top=85)


def app2():
    s = SVG(1040, 600)
    user = Node(40, 200, 190, 64, ["python", "mcp_invoice_app.py"], "io")
    drv = Node(320, 160, 210, 150, ["process_box_folder", "", "(pipeline driver)"], "app")
    # Box MCP server (tools stacked), services to the right of the driver
    s.container(690, 110, 290, 190, "Box MCP Server (stdio)")
    t1 = Node(712, 138, 246, 58, ["list_folder"], "mcp")
    t2 = Node(712, 222, 246, 58, ["extract_text"], "mcp")
    llm = Node(690, 330, 246, 64, ["Gemini LLM", "extract_invoice_fields"], "ext")
    agg = Node(320, 390, 210, 64, ["build_client_reports"], "app")
    out = Node(320, 490, 210, 60, ["Per-client reports"], "io")
    for n in (user, drv, t1, t2, llm, agg, out):
        s.node(n)
    s.arrow(user.right, (drv.x, drv.cy))
    # driver is the hub: three request/response spokes to the right
    s.arrow((drv.x + drv.w, 185), t1.left, "1 · folder → files", both=True, mid=(615, 168))
    s.arrow((drv.x + drv.w, 235), t2.left, "2 · file_id → text", both=True, mid=(615, 235))
    s.arrow((drv.x + drv.w, 285), llm.left, "3 · text → Invoice JSON", both=True, mid=(610, 318))
    # driver -> aggregate -> out
    s.arrow(drv.bottom, agg.top)
    s.arrow(agg.bottom, out.top, "reports")
    legend(s, 40, 575)
    return "app2_mcp_extractor.svg", s.render(trim_top=82)


def app3():
    s = SVG(1200, 760)
    user = Node(490, 92, 220, 60, ["a2a_client.py", "(box folder id)"], "io")
    # orchestrator
    s.container(360, 188, 470, 118, "Orchestrator Agent · :8000")
    oc = Node(382, 214, 200, 66, ["coordinate", "workflow"], "agent")
    br = Node(608, 214, 200, 66, ["build_reports", "(tool)"], "app")
    out = Node(900, 218, 230, 58, ["Per-client reports"], "io")
    # files agent
    s.container(110, 410, 300, 110, "Files Agent · :8001")
    li = Node(132, 436, 256, 60, ["list_invoices (tool)"], "app")
    # extraction agent
    s.container(792, 410, 300, 110, "Extraction Agent · :8002")
    ei = Node(814, 436, 256, 60, ["extract_invoice (tool)"], "app")
    # box mcp
    s.container(360, 600, 360, 120, "Box MCP Server")
    m1 = Node(382, 626, 150, 70, ["list_folder"], "mcp")
    m2 = Node(548, 626, 150, 70, ["extract_text"], "mcp")
    llm = Node(900, 612, 220, 70, ["Gemini LLM"], "ext")
    for n in (user, oc, br, out, li, ei, m1, m2, llm):
        s.node(n)
    # 1: user -> orchestrator
    s.arrow(user.bottom, (oc.cx, oc.y), "1 · A2A request", mid=(540, 175))
    # 2: orch <-> files agent
    s.elbow([(oc.x, oc.cy + 16), (270, oc.cy + 16), (270, li.y)], "2 · A2A list files", both=True,
            lbl_at=(225, 360))
    # 3: files agent <-> mcp list_folder
    s.elbow([(li.cx, li.y + li.h), (li.cx, 570), (m1.cx, 570), m1.top], "3 · folder → files", both=True,
            lbl_at=(300, 556))
    # 5: orch <-> extraction agent
    s.elbow([(br.x + br.w, br.cy - 16), (930, br.cy - 16), (930, ei.y)], "5 · A2A extract (per file)", both=True,
            lbl_at=(905, 360))
    # 6: extraction agent <-> mcp extract_text
    s.elbow([(ei.cx, ei.y + ei.h), (ei.cx, 575), (m2.cx, 575), m2.top], "6 · file_id → text", both=True,
            lbl_at=(700, 560))
    # 7: extraction agent <-> llm
    s.elbow([(ei.x + ei.w, ei.cy), (llm.cx, ei.cy), (llm.cx, llm.y)], "7 · text → Invoice JSON", both=True,
            lbl_at=(1010, 540))
    # 8: orch internal oc -> build_reports
    s.arrow(oc.right, br.left, "8 · aggregate")
    # 9: build_reports -> out
    s.arrow(br.right, out.left, "9 · reports")
    legend(s, 40, 735)
    return "app3_multi_agent_extractor.svg", s.render(trim_top=64)


def eval_pipeline():
    s = SVG(1240, 660)
    gd = Node(40, 200, 180, 74, ["golden_dataset", ".json"], "io")
    run = Node(280, 198, 210, 78, ["Eval runner", "run_*_eval.py"], "app")
    # app under test
    s.container(548, 178, 232, 120, "App under test")
    sut = Node(568, 208, 192, 64, ["app pipeline", "Box MCP + Gemini"], "app")
    score = Node(842, 198, 180, 78, ["scorers.py", "metrics"], "app")
    results = Node(1042, 200, 178, 74, ["results/", "*_eval_results.json"], "io")
    # validation feeding the scorer
    schema = Node(842, 360, 180, 64, ["schema.py", "pydantic validation"], "app")
    # tracing branch
    trace = Node(280, 360, 210, 60, ["tracing.py"], "app")
    traces = Node(280, 470, 210, 64, ["results/", "*_traces.json"], "io")
    # reporting tail
    report = Node(1012, 360, 208, 60, ["report_eval_results.py"], "app")
    table = Node(1012, 470, 208, 64, ["metric summary", "table"], "io")
    for n in (gd, run, sut, score, results, schema, trace, traces, report, table):
        s.node(n)

    s.arrow(gd.right, run.left, "cases")
    s.arrow(run.right, sut.left, "invoke · predicted", both=True, mid=(519, 168))
    s.arrow((sut.x + sut.w, sut.cy), score.left, "predicted + expected", both=False, mid=(812, 168))
    s.arrow(score.right, results.left, "scores")
    # --mock dashed bypass over the top
    s.elbow([(run.cx, run.y), (run.cx, 150), (score.cx, 150), (score.cx, score.y)],
            "--mock · mock_predicted (offline)", dash="6 5", lbl_at=(640, 150))
    # validation up into scorer
    s.arrow(schema.top, (score.cx, score.y + score.h), "schema validity", both=True)
    # tracing branch
    s.arrow(run.bottom, trace.top, "steps")
    s.arrow(trace.bottom, traces.top)
    # reporting tail
    s.arrow(results.bottom, report.top)
    s.arrow(report.bottom, table.top, "render")
    legend(s, 40, 625)
    return "eval_pipeline.svg", s.render(trim_top=122)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for fn in (app1, app2, app3, eval_pipeline):
        name, svg = fn()
        (OUT / name).write_text(svg)
        print("wrote", OUT / name)


if __name__ == "__main__":
    main()
