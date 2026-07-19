# Validation report

Status: **RUN 2 RAILWAY LIVE passed** on 2026-07-19. Every result below completed with exit code 0 unless an external provider limitation is stated explicitly.

| Gate | Result |
| --- | --- |
| migration/bootstrap | Alembic ran against dedicated managed PostgreSQL; the idempotent release module created the Vesper world, 8 districts, 12 events and the initial admin |
| `pnpm api:generate` | current FastAPI OpenAPI exported and TypeScript declarations regenerated during RUN 1 |
| `pnpm format:check` | Prettier and Ruff format clean |
| `pnpm lint` | ESLint at zero warnings; Ruff clean |
| `pnpm typecheck` | all TypeScript workspaces clean; strict mypy clean across 18 Python source files |
| `pnpm test` | API 20/20 above the 65% coverage gate; web 6/6 at 99.12% measured statements; mobile 3/3 at 100% measured theme scope |
| `pnpm test:e2e` | 6/6 Playwright checks: critical flow, axe and RTL on Chromium desktop and mobile viewports |
| `pnpm test:load` | 100 concurrent simulated readers completed; k6 HTTP profile retained for deployed-environment tests |
| `pnpm i18n:validate` | 198 canonical English keys with complete reviewed German parity |
| production builds | Vite transformed 140 modules; Expo exported 13 static routes |
| security | secret scan, Bandit, pip-audit and `pnpm audit` report no known vulnerability |
| GitHub containers | main workflow built both images; combined image passed migration, bootstrap, Redis, worker, readiness and SPA checks |
| Railway runtime | deployment `33804230-4298-40e1-b60f-73ada209bc51` succeeded from commit `ecf0404`; PostgreSQL, Redis, ARQ and Uvicorn startup markers present |
| public HTTPS | `/`, `/city`, manifest, service worker, health and readiness returned 200 with expected content types; CSP, referrer and MIME-sniffing headers present |
| live auth/data | ignored local admin credentials logged in successfully; verified admin/moderator roles, production world lookup and logout passed |
| secret lifecycle | bootstrap email/password removed atomically from Railway after account creation; a clean redeploy and repeat login passed |

Docker/Docker Compose, Java and ADB are not installed on the local Windows host. Container execution was therefore verified in GitHub Actions and Railway rather than claimed locally. Signed native artifacts and outbound SMTP delivery still require their respective provider accounts.
