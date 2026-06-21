# Contributing

Thanks for contributing! This repo holds three self-contained invoice extractors
under `app/` and a shared evaluation harness under `evals/`.

## Setup

```bash
# dev toolchain (ruff, mypy, pytest, bandit, pip-audit, pre-commit, nox)
pip install -e ".[dev]"
pre-commit install        # run checks automatically on commit

# to actually RUN an app, install that app's runtime deps too:
pip install -r app/<name>/requirements.txt
```

> The project is intentionally not an importable package — each `app/<name>/`
> folder is self-contained and runs as scripts. `pip install -e ".[dev]"` only
> installs the tooling + shared deps (pydantic).

## Day-to-day (one command each)

```bash
make fmt           # auto-format + apply lint fixes
make lint          # ruff check
make typecheck     # mypy evals
make test          # pytest
make cov           # pytest + coverage gate
make security      # bandit + pip-audit
make check         # everything CI runs (lint + format-check + typecheck + test)
```

`make help` lists all targets. `nox` runs the tests across Python 3.10–3.13.

## Quality gates (enforced in CI)

A PR must pass: **ruff** (lint + format), **mypy** (on `evals/`), **pytest** with
the **coverage gate**, plus the security scans (**Bandit**, **pip-audit**,
**CodeQL**). Run `make check` before pushing to catch issues locally.

> First-time note: run `make fmt` once to normalize formatting — the initial
> code was hand-formatted and may need a single ruff-format pass.

## Pull requests

1. Branch off `main`.
2. Keep changes focused; add/adjust tests in `evals/test_scorers.py` for the
   deterministic core.
3. Update `CHANGELOG.md` (Unreleased section) and any affected README.
4. Ensure `make check` passes. Open the PR using the template; CODEOWNERS will be
   requested for review automatically.

## Commit messages

Short imperative subject lines (e.g. "Add coverage gate to CI"). Group related
changes into a single commit where reasonable.
