# Deployment

No external deployment is performed by RUN 1. These instructions provide a deployment-ready handoff.

## Local service stack

1. Run `pnpm setup` to create `.local/development.env` and demo credentials.
2. Run `docker compose up --build -d postgres redis mailpit minio api worker web prometheus`.
3. Run `docker compose exec api alembic upgrade head`.
4. Optionally run `docker compose exec api python -m shadowgrid.seed` for a non-production demo.
5. Verify `/api/v1/ready`, the web `/healthz`, Mailpit on port 8025 and Prometheus on port 9090.

## Production compose

Use `docker compose -f docker-compose.yml -f docker-compose.production.yml up -d api worker web`. Supply managed PostgreSQL/Redis URLs, strong independent secrets, production web origin and SMTP values through the platform secret store. Do not enable local database/cache profiles in production. Run Alembic as a one-shot release task before switching traffic.

## Railway template

`railway.json` configures the API image and readiness path; `deploy/railway.env.example` lists variables. Create separate API and worker services from the same repository, plus managed PostgreSQL and Redis. The worker start command is `python -m arq apps.worker.worker.WorkerSettings` with working directory `/app`. Deploy the web Dockerfile as a third service and set the API service's `WEB_ORIGINS` to its HTTPS origin.

## Release order and rollback

1. Take and verify a database backup.
2. Deploy backward-compatible migrations.
3. Deploy API and worker; wait for readiness.
4. Deploy web, then release signed mobile builds through staged tracks.
5. Observe error rate, latency, queue lag and ledger reconciliation.

Application rollback uses the previous immutable image. Database rollback is allowed only when the migration is explicitly reversible and no new-format data was committed; otherwise deploy a forward fix. Mobile rollback uses store staged-release controls because installed binaries cannot be recalled.
