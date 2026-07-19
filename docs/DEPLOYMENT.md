# Deployment

## Current Railway production

The authorized browser/API release is live at <https://shadowgrid-production-be34.up.railway.app>.

The Railway environment contains:

- `SHADOWGRID`: one Docker image containing the React SPA, FastAPI and a supervisor for Uvicorn plus ARQ;
- `ShadowgridPostgres`: the dedicated authoritative PostgreSQL database;
- `Redis`: the dedicated ARQ/cache service with a persistent `/data` volume.

`railway.json` selects `apps/api/Dockerfile`, runs `python -m shadowgrid.predeploy`, checks `/api/v1/ready` and restarts failed processes. The pre-deploy module upgrades Alembic before running the idempotent production bootstrap. The container listens on Railway's injected `PORT`.

Persistent variables include independent application secrets, PostgreSQL/Redis references, the exact HTTPS `WEB_ORIGINS` value and production runtime settings. Bootstrap-admin variables are deliberately one-time values and were removed after the live login verification.

Transactional email supports `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM`, optional `SMTP_USERNAME`/`SMTP_PASSWORD`, `SMTP_STARTTLS` and `SMTP_USE_SSL`. Configure those only through Railway after selecting a provider.

## Local service stack

1. Run `pnpm setup` to create `.local/development.env` and demo credentials.
2. Run `docker compose up --build -d postgres redis mailpit minio api worker web prometheus`.
3. Run `docker compose exec api python -m shadowgrid.predeploy`.
4. Optionally run `docker compose exec api python -m shadowgrid.seed` for a non-production demo.
5. Verify `/api/v1/ready`, the web `/healthz`, Mailpit on port 8025 and Prometheus on port 9090.

Compose runs API and worker separately even though the Railway image's default command supervises both. This preserves scalable local/portable topology while fitting the current single-service Railway release.

## Release order and rollback

1. Take and verify a database backup.
2. Deploy backward-compatible migrations and the idempotent bootstrap.
3. Wait for PostgreSQL readiness, Redis connectivity, ARQ startup and API readiness.
4. Smoke-test web routes, auth, production world data and logout.
5. Release signed mobile builds only through internal/staged tracks.

Application rollback uses the previous immutable Railway deployment/image. Database rollback is allowed only when the migration is explicitly reversible and no new-format data was committed; otherwise deploy a forward fix. Mobile rollback uses store staged-release controls because installed binaries cannot be recalled.
