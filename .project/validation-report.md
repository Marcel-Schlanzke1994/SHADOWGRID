# Validation report

Status: **RUN 1 LOCAL FINAL passed** on 2026-07-19. Every result below completed with exit code 0 unless an environment limitation is stated explicitly.

| Gate | Result |
| --- | --- |
| `pnpm migrate` / `pnpm seed` | Alembic at head; deterministic Vesper seed completed and credentials written only to ignored `.local/` |
| `pnpm api:generate` | current FastAPI OpenAPI exported and TypeScript declarations regenerated |
| `pnpm format:check` | Prettier and Ruff format clean |
| `pnpm lint` | ESLint at zero warnings; Ruff clean |
| `pnpm typecheck` | all TypeScript workspaces clean; strict mypy clean across 15 Python source files |
| `pnpm test` | API 13/13 at 68.61% coverage (65% gate); web 6/6 at 99.12% measured statements; mobile 3/3 at 100% measured theme scope |
| `pnpm test:e2e` | 6/6 Playwright checks: critical flow, axe and RTL on Chromium desktop and mobile viewports |
| `pnpm test:load` | 100 concurrent simulated readers completed; k6 HTTP profile included for deployed environments |
| `pnpm i18n:validate` | 198 canonical English keys with complete reviewed German parity |
| production builds | Vite transformed 140 modules; Expo exported 13 static routes without i18n initialization warnings |
| security | secret scan, Bandit and pip-audit clean; `pnpm audit --audit-level low` reports no known vulnerabilities |
| configuration | 22 JSON, 5 YAML and 1 TOML files parsed successfully; Expo dependency check reports up to date |

Docker/Docker Compose, Java and ADB are not installed on this host. Consequently, container execution and signed native artifacts were not falsely claimed. Dockerfiles, Compose overlays, health checks, CI image builds, EAS configuration and provider runbooks are present for the RUN 2 environment.
