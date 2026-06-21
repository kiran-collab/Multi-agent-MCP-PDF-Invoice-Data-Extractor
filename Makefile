.DEFAULT_GOAL := help
.PHONY: help install install-apps lint fmt format-check typecheck test cov \
        security bandit audit precommit lock pin-actions diagrams \
        run-local run-mcp clean check

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install:  ## Install the dev toolchain (ruff, mypy, pytest, bandit, ...)
	pip install -e ".[dev]"
	pre-commit install

install-apps:  ## Install every app's runtime requirements
	pip install -r app/local_extractor/requirements.txt \
		-r app/mcp_extractor/requirements.txt \
		-r app/multi_agent_extractor/requirements.txt \
		-r evals/requirements.txt

lint:  ## Lint with ruff
	ruff check .

fmt:  ## Auto-format with ruff (and apply lint fixes)
	ruff format .
	ruff check --fix .

format-check:  ## Verify formatting without writing (CI gate)
	ruff format --check .

typecheck:  ## Static type-check the deterministic core
	mypy evals

test:  ## Run the test suite
	pytest

cov:  ## Run tests with the coverage gate
	pytest --cov --cov-report=term-missing

bandit:  ## Python SAST
	bandit -r app evals -c pyproject.toml

audit:  ## Scan dependencies for known CVEs
	pip-audit -r app/local_extractor/requirements.txt \
		-r app/mcp_extractor/requirements.txt \
		-r app/multi_agent_extractor/requirements.txt \
		-r evals/requirements.txt

security: bandit audit  ## Run all security scans

precommit:  ## Run all pre-commit hooks on the whole tree
	pre-commit run --all-files

lock:  ## Generate a hashed lockfile from requirements.in (needs network)
	pip-compile --generate-hashes --output-file requirements.lock requirements.in

pin-actions:  ## Pin GitHub Actions to commit SHAs (needs network; install pinact)
	pinact run

diagrams:  ## Regenerate architecture diagrams (SVG -> PNG)
	python3 docs/diagrams/generate_diagrams.py
	cd docs/images && for f in *.svg; do rsvg-convert -z 2 "$$f" -o "$${f%.svg}.png"; done

run-local:  ## Run app 1 over a local PDF folder: make run-local DIR=./invoices
	cd app/local_extractor && python local_invoice_app.py $(DIR)

run-mcp:  ## Run app 2 over a Box folder: make run-mcp FOLDER=0
	cd app/mcp_extractor && python mcp_invoice_app.py $(FOLDER)

check: lint format-check typecheck test  ## Run all CI gates locally

clean:  ## Remove caches and build artifacts
	rm -rf .ruff_cache .mypy_cache .pytest_cache .coverage coverage.xml \
		htmlcov build dist *.egg-info .nox
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
