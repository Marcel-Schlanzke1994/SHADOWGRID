# Testing strategy

- Python: 13 API/domain tests cover authentication rotation/replay, authorization, IDOR protection, gameplay, exactly-once purchases and property-generated ledger reconciliation. The gate requires 65% branch-aware coverage of runtime modules; seed is validated by an actual idempotent seed run.
- Web: Vitest covers reusable accessible UI and locale formatting. Playwright covers the real login/dashboard/city/business/operation path and runs axe against critical pages.
- Mobile: Jest validates high-contrast theme tokens and minimum 44-point controls with a hard coverage threshold.
- Load: the Python smoke load and `k6.js` exercise health, login and state reads without mutating unrelated users.
- Security: Ruff, strict mypy, ESLint, Bandit, pip-audit, pnpm audit and masked secret-pattern scanning.

Run `pnpm validate` for the local release gate. CI repeats deterministic install, generation, localization, formatting, lint, types, tests, builds and dependency audits. Playwright is separate because it starts application processes and requires a browser binary.
