# Security Policy

## Supported versions

This project is pre-1.0; only the latest `main` is supported with security fixes.

## Reporting a vulnerability

**Please do not open public issues for security vulnerabilities.**

Report privately via either:

1. **GitHub Security Advisories** — the "Report a vulnerability" button under the
   repository's **Security** tab (preferred), or
2. **Email** — dkiran238@gmail.com with subject `SECURITY: <short summary>`.

Please include: affected component (`app/local_extractor`, `app/mcp_extractor`,
`app/multi_agent_extractor`, or `evals/`), a description, reproduction steps, and
the impact you foresee.

## Disclosure process

- We aim to acknowledge a report within **3 business days**.
- We will work on a fix and coordinate a disclosure timeline with you, targeting
  a fix within **90 days** depending on severity.
- Please give us reasonable time to remediate before any public disclosure.

## Scope notes

- Never commit secrets. `GOOGLE_API_KEY` and `BOX_DEVELOPER_TOKEN` are read from
  the environment; a gitleaks pre-commit hook and CI scans help prevent leaks.
- Dependency CVEs are tracked via Dependabot + `pip-audit`; code-level issues via
  Bandit + CodeQL.
