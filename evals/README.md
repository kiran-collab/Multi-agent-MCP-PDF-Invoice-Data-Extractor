# Evaluation pipeline

A lightweight, dependency-light evaluation harness for the invoice extractors in
this repo. It validates **invoice-extraction quality** (app2 + app3) and
**multi-agent workflow reliability** (app3), using a golden dataset of expected
outputs.

```
evals/
├── golden_dataset.json       # expected outputs (+ source_text, mock_predicted)
├── scorers.py                # pure-stdlib metric functions (offline-testable)
├── tracing.py                # trace-based agent logging (+ optional Langfuse)
├── run_app2_eval.py          # app2 runner (real / --mock)
├── run_app3_eval.py          # app3 runner (component / e2e / mock)
├── report_eval_results.py    # render saved results as a metric table
├── test_scorers.py           # offline unit tests for the scorers
└── results/                  # generated *_eval_results.json + *_traces.json
```

## Metrics

| metric | what it checks | function |
| --- | --- | --- |
| json validity | LLM output parses as JSON (`extract_invoice_fields` does `json.loads`) | `is_valid_json` |
| schema validity | required fields present with right types | `check_schema` |
| field exact match | invoice id, client name, date, currency | `score_invoice → fields` |
| numeric tolerance | total amount compared with `abs_tol=0.01` | `score_invoice → total_amount_match` |
| line item recall / precision | all purchased products extracted, none invented | `score_line_items` |
| hallucination rate | predicted scalars grounded in the source text ("Do not invent data") | `hallucination_check` |
| empty-text handling | empty MCP text is skipped (app2) / returns error JSON (app3) | runner logic |
| file discovery | Files Agent returns exactly the expected invoice files | `eval_file_discovery` |
| delegation correctness | orchestrator runs Files → Extraction → reporting in order | `Trace.delegation_ok` |
| report correctness | per-client report names + summed totals | `score_report_text` |

`score_invoice` also returns a single `overall` ∈ [0, 1] (mean of the headline
signals); `aggregate` rolls per-case results into dataset-level averages.

## Quick start (offline — no Box / Gemini needed)

```bash
python evals/test_scorers.py            # unit-test the metrics
python evals/run_app2_eval.py --mock    # score mock_predicted from the dataset
python evals/run_app3_eval.py --mode mock
python evals/report_eval_results.py     # pretty metric table
```

The `--mock` paths score the `mock_predicted` values baked into
`golden_dataset.json`, so you can verify the harness without any external
service. They exercise every metric and the report scorer end to end.

## Real runs

Real runs call the actual app pipelines, so they need that app's dependencies
(`pip install -r appN/requirements.txt`), a `GOOGLE_API_KEY`, a Box MCP server
with `BOX_DEVELOPER_TOKEN`, and **real `box_file_id` values** filled into
`golden_dataset.json` (replace the `REPLACE_WITH_REAL_BOX_FILE_ID` placeholders).

**app2** — runs `box_mcp_client.extract_text` → `llm_extraction.extract_invoice_fields`:

```bash
python evals/run_app2_eval.py
```

**app3** — two levels:

```bash
# component: call each agent's work function directly (needs google-adk + Box + Gemini,
# but NO running servers)
python evals/run_app3_eval.py --mode component

# e2e: drive the orchestrator over A2A (needs all three servers running:
#   python app3/files_agent_server.py        # 8001
#   python app3/extraction_agent_server.py   # 8002
#   python app3/orchestrator_agent_server.py # 8000
# ), then score the rendered per-client report text
python evals/run_app3_eval.py --mode e2e --folder-id <box_folder_id>
```

## Tracing

`tracing.py` records each agent/tool step in a JSON shape suited to trace-based
agent evaluation, written to `results/appN_traces.json`. If `langfuse` is
installed and `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` are set,
`Trace.export_langfuse()` also pushes traces to Langfuse; otherwise it is a
no-op, so the harness stays fully offline by default.

## Extending

- Add cases to `golden_dataset.json` (real `box_file_id` for live runs;
  `source_text` enables hallucination scoring; `mock_predicted` enables `--mock`).
- For CI / pytest-style LLM assertions, wrap `score_invoice` thresholds in
  `test_*` functions, or layer in DeepEval. Langfuse is the recommended
  open-source backend if you want dashboards and production trace scoring.
