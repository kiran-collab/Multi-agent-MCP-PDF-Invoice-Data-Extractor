# App 1 — Local Invoice App

A simple, single-process app that processes **PDF invoices from a local folder**.
It extracts **client name, total amount, and purchased products** from each
invoice and writes a **per-client summary report**.

This is the starting point — no MCP and no agents, just plain function calls.
(Later versions move file access to the Box MCP server and split the work
across cooperating agents.)

This folder is fully self-contained.

---

## Files

```
local_extractor/
├── local_invoice_app.py    # Entry point: local PDF folder -> reports
├── invoice_models.py       # Invoice / LineItem / ClientReport + aggregation
├── llm_extraction.py       # LLM field-extraction (prompt + JSON parsing)
└── requirements.txt
```

## How it works

1. **Discover** — find every `*.pdf` in the given folder.
2. **Extract text** — pull raw text from each PDF locally (`pypdf`).
3. **Parse fields** — an LLM turns the text into structured invoice data
   (client, total, line items) via `llm_extraction.py`.
4. **Report** — `invoice_models.py` groups invoices by client and writes a
   per-client report.

## Setup

```bash
pip install -r requirements.txt

export GOOGLE_API_KEY="..."                 # LLM (Gemini via google-genai)
export INVOICE_LLM_MODEL="gemini-2.5-flash"  # optional override
```

## Run

```bash
python local_invoice_app.py /path/to/invoices
```

Prints results to the console and writes `reports/report_<Client>.txt` for each
client found.

## Notes

- `extract_text_from_pdf` handles text-based PDFs only. For scanned/image PDFs,
  add an OCR step.
- The LLM is prompted to return strict JSON; `llm_extraction.py` strips code
  fences and parses it. Add validation/retries for production use.
- Generative output is non-deterministic; the same invoice may parse slightly
  differently across runs.
