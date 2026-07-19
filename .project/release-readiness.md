# Release readiness

| Area | Status | Evidence |
| --- | --- | --- |
| Local build | Passed | Web production bundle and 13-route Expo export completed |
| Tests | Passed | 13 API, 6 web, 3 mobile, 6 E2E and load-smoke checks passed |
| Security | Passed | no secret pattern, Python vulnerability, Bandit issue or pnpm advisory remains |
| Data setup | Passed | Alembic upgrade and idempotent Vesper seed completed |
| Localization/accessibility | Passed | 198-key EN/DE parity, pseudo-locales, RTL E2E and axe checks |
| Containers | Ready, runtime unverified locally | Dockerfiles/Compose parse cleanly; Docker is absent on this host and CI builds both images |
| Web production | Ready for RUN 2 | deployment intentionally not performed during local RUN 1 |
| Android | Source/config ready | signed AAB/APK requires EAS account, Android SDK and signing credentials |
| iOS | Source/config ready | signed IPA requires Apple/EAS credentials and provider environment |

RUN 1 is complete. External release requires explicit RUN 2 authorization, real provider secrets, container smoke tests in a Docker-capable environment and staged mobile signing/submission.
