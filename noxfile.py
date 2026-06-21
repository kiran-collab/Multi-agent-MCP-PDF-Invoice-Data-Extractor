"""Nox sessions: run the test suite across Python versions, plus lint/type checks.

    nox                    # default sessions (tests on all versions, lint, types)
    nox -s tests-3.12      # one version
    nox -s lint typecheck
"""

from __future__ import annotations

import nox

nox.options.sessions = ["tests", "lint", "typecheck"]
nox.options.reuse_existing_virtualenvs = True

PY_VERSIONS = ["3.10", "3.11", "3.12", "3.13"]


@nox.session(python=PY_VERSIONS)
def tests(session: nox.Session) -> None:
    session.install("-e", ".[dev]")
    session.run("pytest", "--cov", "--cov-report=term-missing")


@nox.session(python="3.12")
def lint(session: nox.Session) -> None:
    session.install("ruff")
    session.run("ruff", "check", ".")
    session.run("ruff", "format", "--check", ".")


@nox.session(python="3.12")
def typecheck(session: nox.Session) -> None:
    session.install("-e", ".[dev]")
    session.run("mypy", "evals")
