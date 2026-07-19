# SHADOWGRID

> Macht ist unsichtbar. Spuren sind es nicht.

SHADOWGRID is a fictional, server-authoritative seasonal strategy MMO for web, Android and iOS. It combines businesses, districts, specialists, information, diplomacy and organizational stability without teaching actionable real-world crime.

Production web/API: <https://shadowgrid-production-be34.up.railway.app>

## Fast local start on Windows

Prerequisites: Node 22+, pnpm 11+ and Python 3.13+ (Python 3.12 also works for local validation). Docker is optional for the native development route and required for the full service stack.

```powershell
pnpm check:environment
pnpm setup
pnpm dev
```

Open:

- Web: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- API health: <http://localhost:8000/api/v1/health>
- Mailpit with Compose: <http://localhost:8025>
- MinIO console with Compose: <http://localhost:9001>

Generated development account credentials are stored once in `.local/demo-credentials.txt`, which is ignored by Git.

## Docker Compose route

```powershell
pnpm setup
docker compose up --build -d postgres redis mailpit minio api worker web prometheus
docker compose exec api alembic upgrade head
docker compose exec api python -m shadowgrid.seed
```

The web stack is available at <http://localhost:8080>. The Compose services load generated secrets from `.local/development.env`; no credential is committed.

Install Chromium once with `pnpm --filter @shadowgrid/web exec playwright install chromium`, then use `pnpm validate` for the complete local acceptance gate, including generation, formatting, tests, load smoke, security, production builds and browser E2E.

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Master-goal traceability](docs/TRACEABILITY.md)
- [Security threat model](docs/SECURITY_THREAT_MODEL.md)
- [Deployment](docs/DEPLOYMENT.md) and [operations runbook](docs/OPERATIONS_RUNBOOK.md)
- [Backup/restore](docs/BACKUP_RESTORE.md)
- [Testing](docs/TESTING.md) and [accessibility](docs/ACCESSIBILITY.md)
- [Mobile release](docs/MOBILE_RELEASE.md), [privacy](docs/PRIVACY.md) and [localization quality](docs/localization/TRANSLATION_QUALITY.md)

## Safety boundary

Every city, organization, person and company is fictional. Covert operations remain abstract, conflict is non-graphic, and no screen or API contains procedural real-world criminal instructions.
