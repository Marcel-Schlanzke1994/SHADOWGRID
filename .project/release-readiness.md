# Release readiness

| Area | Status | Evidence |
| --- | --- | --- |
| Local build | Passed | Web production bundle and 13-route Expo export completed |
| Tests | Passed | 20 API, 6 web, 3 mobile, 6 browser E2E and load-smoke checks passed |
| Security | Passed | secret scan, Bandit, pip-audit and pnpm audit report no known issue |
| Containers | Passed in CI | GitHub Actions builds API/web images and runs migration, bootstrap, Redis, ARQ, API and SPA smoke checks |
| Production data | Live | dedicated Railway PostgreSQL migrated; one Vesper world with 8 districts and 12 events bootstrapped idempotently |
| Production cache/worker | Live | dedicated Railway Redis 8.2.1; ARQ cron worker healthy in the supervised service |
| Web/API production | Live | <https://shadowgrid-production-be34.up.railway.app> returns HTTPS web, PWA, health and readiness responses |
| Initial administration | Passed | ignored local credential handoff verified against live auth; one-time Railway bootstrap variables removed afterward |
| Localization/accessibility | Passed | 198-key EN/DE parity, pseudo-locales, RTL E2E and axe checks |
| Transactional email | Provider input required | SMTP TLS/auth is implemented; host, sender and credentials must come from a real mail provider |
| Android | Source/config ready | signed AAB/APK requires EAS/Google signing credentials and device checks |
| iOS | Source/config ready | signed IPA requires Apple/EAS credentials and provider environment |

RUN 2 is complete for the explicitly authorized GitHub-to-Railway browser/API release. Signed store artifacts and real outbound email remain provider-account operations; neither is falsely claimed as configured.
