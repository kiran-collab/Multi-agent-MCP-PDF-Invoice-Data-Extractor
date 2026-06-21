# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CI quality gates (GitHub Actions): ruff lint + format check, mypy on the
  `evals/` core, and pytest with a coverage gate across Python 3.10–3.13.
- Security & supply chain: Dependabot, `pip-audit`, Bandit, and CodeQL workflows;
  `requirements.in` + `make lock` flow for a hashed lockfile.
- Dev ergonomics: `pre-commit` config (ruff, mypy, secrets detection), `.editorconfig`,
  `Makefile`, and `noxfile.py`.
- Governance & docs: `LICENSE` (MIT), `SECURITY.md`, `CONTRIBUTING.md`,
  `CODEOWNERS`, this `CHANGELOG.md`, and issue/PR templates.
- `pyproject.toml` with ruff, mypy, pytest, coverage, and Bandit configuration.

## [0.1.0] — 2026-06-20

### Added
- Three invoice extractors under `app/`: `local_extractor`, `mcp_extractor`, and
  `multi_agent_extractor` (A2A + MCP).
- Evaluation harness under `evals/` with scorers, pydantic schema validation,
  tracing, runners, and reporting.
- Architecture diagrams for all apps and the evaluation pipeline.
