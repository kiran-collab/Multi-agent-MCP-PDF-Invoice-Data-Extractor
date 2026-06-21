"""
Stage 1 — Simple local invoice-processing app.

This is the starting point: a single-process LLM app that works on PDF
invoices you've already downloaded to a local folder.

Pipeline:
    1. Discover PDF files in a local folder.
    2. Extract raw text from each PDF (local text extraction).
    3. Use an LLM to pull structured fields (client, total, products...).
    4. Aggregate per-client reports and write them out.

No MCP and no agents yet — everything is plain function calls. Later stages
replace local file/text handling with the Box MCP server, and then split the
work across cooperating agents.

Run:
    python local_invoice_app.py /path/to/invoices
"""

import sys
from pathlib import Path
from typing import List

from invoice_models import Invoice, build_client_reports
from llm_extraction import extract_invoice_fields


# --- Step 1: discover files ----------------------------------------------
def list_invoice_files(folder: str) -> List[Path]:
    """Return all PDF files in a local folder."""
    return sorted(Path(folder).glob("*.pdf"))


# --- Step 2: local text extraction ---------------------------------------
def extract_text_from_pdf(path: Path) -> str:
    """Extract raw text from a local PDF.

    Uses pypdf; for scanned/image PDFs you'd add OCR here.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


# --- Step 3 + 4: process and report --------------------------------------
def process_folder(folder: str) -> List[Invoice]:
    """Process every invoice in a folder into structured Invoice objects."""
    invoices: List[Invoice] = []
    for pdf in list_invoice_files(folder):
        print(f"Processing {pdf.name} ...")
        text = extract_text_from_pdf(pdf)
        if not text.strip():
            print(f"  ! no text extracted from {pdf.name}, skipping")
            continue
        invoice = extract_invoice_fields(text, source_file=pdf.name)
        print(f"  -> {invoice.client_name}: {invoice.total_amount} {invoice.currency}")
        invoices.append(invoice)
    return invoices


def main(folder: str, out_dir: str = "reports"):
    invoices = process_folder(folder)
    reports = build_client_reports(invoices)

    out = Path(out_dir)
    out.mkdir(exist_ok=True)
    for report in reports:
        text = report.render()
        print("\n" + text)
        fname = out / f"report_{report.client_name.replace(' ', '_')}.txt"
        fname.write_text(text)
        print(f"\nSaved report -> {fname}")


if __name__ == "__main__":
    folder = sys.argv[1] if len(sys.argv) > 1 else "invoices"
    main(folder)
