# SHADOWGRID

> Macht ist unsichtbar. Spuren sind es nicht.

SHADOWGRID is a fictional, server-authoritative seasonal strategy MMO for web, Android and iOS. It combines businesses, districts, specialists, information, diplomacy and organizational stability without teaching actionable real-world crime.

Production web/API: <https://shadowgrid-production-be34.up.railway.app>

## Fast local start on Windows

Prerequisites: Node 22+, pnpm 11+ and Python 3.13+. Docker is optional for the
zero-dependency SQLite route and required for the PostgreSQL/Redis service topology.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup-local.ps1
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
```

Open:

- Web: <http://localhost:5173>
- API documentation: <http://localhost:8000/docs>
- API health: <http://localhost:8000/api/v1/health>
- Mailpit with Compose: <http://localhost:8025>
- MinIO console with Compose: <http://localhost:9001>

The scripts start API, worker and web, then verify health, readiness and data invariants.
Generated development account credentials are stored once in
`.local/demo-credentials.txt`, which is ignored by Git and never printed.

## WSL2 and Docker Compose

Run the repository from the WSL2 Linux filesystem:

```bash
bash scripts/setup-local.sh
bash scripts/start-local.sh
```

The bootstrap is idempotent: it creates the local virtual environment and ignored
development secrets, installs pinned dependencies, applies migrations and loads the
deterministic seed. Open:

- Web: <http://localhost:3000>
- API documentation: <http://localhost:8000/docs>
- API health: <http://localhost:8000/api/v1/health>
- Mailpit: <http://localhost:8025>

The equivalent explicit Docker Compose route is:

```powershell
pnpm setup
docker compose up --build -d postgres redis mailpit minio api worker web prometheus
docker compose exec api alembic upgrade head
docker compose exec api python -m shadowgrid.seed
```

The Compose services load generated secrets from `.local/development.env`; no credential is committed.

See [LOCAL_QUICKSTART.md](LOCAL_QUICKSTART.md) for mode selection, safe reset, verification
and troubleshooting.

Install Chromium once with `pnpm --filter @shadowgrid/web exec playwright install chromium`, then use `pnpm validate` for the complete local acceptance gate, including generation, formatting, tests, load smoke, security, production builds and browser E2E.

## Documentation

- [Game specification](docs/game-design/SHADOWGRID_SPEC.md)
- [Local quickstart](LOCAL_QUICKSTART.md)
- [Architecture](docs/architecture/ARCHITECTURE.md)
- [Implementation roadmap](SHADOWGRID_CODEX_MASTER_ROADMAP.md)
- [Master-goal traceability](docs/TRACEABILITY.md)
- [Security threat model](docs/SECURITY_THREAT_MODEL.md)
- [Deployment](docs/DEPLOYMENT.md) and [operations runbook](docs/OPERATIONS_RUNBOOK.md)
- [Backup/restore](docs/BACKUP_RESTORE.md)
- [Testing](docs/TESTING.md) and [accessibility](docs/ACCESSIBILITY.md)
- [Mobile release](docs/MOBILE_RELEASE.md), [privacy](docs/PRIVACY.md) and [localization quality](docs/localization/TRANSLATION_QUALITY.md)
- [Multiplayer architecture](MULTIPLAYER_ARCHITECTURE_REPORT.md), [PvP balance](PVP_BALANCE_REPORT.md), [cartel wars](CARTEL_WAR_SYSTEM_REPORT.md), [multiplayer security](MULTIPLAYER_SECURITY_REPORT.md) and [load results](MULTIPLAYER_LOAD_TEST_REPORT.md)

## Safety boundary

Every city, organization, person and company is fictional. Covert operations remain abstract, conflict is non-graphic, and no screen or API contains procedural real-world criminal instructions.
