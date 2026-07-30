.PHONY: help bootstrap setup local-setup local-start local-stop local-verify up down restart dev migrate migration seed seed-demo test test-e2e test-lifecycle test-balance \
	test-season-runbook test-smoke-script operations-verify restore-drill mobile-release-verify test-email-release test-release-materials release-materials release-final-run store-validate-captures store-prepare-static store-ingest-static store-ingest-captures store-report store-gate \
	e2e lint typecheck security secret-scan validate review-ready verify-release reset-local logs stop ps clean \
	shell-backend shell-db shell-redis backend-lint backend-format backend-typecheck backend-test \
	frontend-lint frontend-format frontend-typecheck frontend-test backup-local restore-local \
	assets-manifest assets-style-proof assets-generate-next assets-generate-batch \
	assets-generate-city assets-generate-all assets-resume assets-validate \
	assets-optimize assets-contact-sheets assets-integration-test assets-gate assets-report \
	assets-geodata

help:
	@echo "SHADOWGRID development targets"
	@echo "  bootstrap/up/down       prepare and run the complete local stack"
	@echo "  local-*                 automatic Compose/SQLite setup and lifecycle"
	@echo "  migrate/migration       apply or create an Alembic migration"
	@echo "  seed/seed-demo          load deterministic local data"
	@echo "  backend-* / frontend-*  focused quality gates"
	@echo "  test/e2e/test-lifecycle  automated validation gates"
	@echo "  backup-local/restore-local BACKUP=<dump>  database operations"

bootstrap:
	bash scripts/bootstrap.sh

setup:
	pnpm setup

local-setup:
	bash scripts/setup-local.sh

local-start:
	bash scripts/start-local.sh

local-stop:
	bash scripts/stop-local.sh

local-verify:
	bash scripts/verify-local.sh

up:
	docker compose up --build -d

down:
	docker compose down

restart: down up

dev:
	pnpm dev

migrate:
	pnpm migrate

migration:
	node scripts/run-python.mjs --cwd apps/api -m alembic revision --autogenerate -m "$(or $(MESSAGE),manual)"

seed:
	pnpm seed

seed-demo:
	pnpm seed

test:
	pnpm test

test-e2e:
	pnpm test:e2e

test-lifecycle:
	pnpm test:lifecycle

test-balance:
	pnpm test:balance

test-season-runbook:
	pnpm test:season-runbook

test-smoke-script:
	pnpm test:smoke-script

operations-verify:
	pnpm ops:verify

restore-drill:
	pnpm ops:restore-drill

mobile-release-verify:
	pnpm mobile:release:verify

test-email-release:
	pnpm test:email-release

test-release-materials:
	pnpm test:release-materials

release-materials:
	pnpm release:materials

release-final-run:
	pnpm release:final-run

store-validate-captures:
	pnpm store:validate-captures

store-prepare-static:
	pnpm store:prepare-static

store-ingest-static:
	pnpm store:ingest-static

store-ingest-captures:
	pnpm store:ingest-captures

store-report:
	pnpm store:report

store-gate:
	pnpm store:gate

e2e:
	pnpm test:e2e

lint:
	pnpm lint

typecheck:
	pnpm typecheck

security:
	pnpm test:security

secret-scan:
	pnpm scan:secrets

validate:
	pnpm validate

review-ready: lint typecheck test
	git diff --check
	git status --short

verify-release:
	pnpm validate

reset-local:
	bash scripts/reset-local.sh auto "$(CONFIRM)"

logs:
	pnpm logs

stop:
	pnpm stop

ps:
	docker compose ps

clean:
	pnpm clean

shell-backend:
	docker compose exec api sh

shell-db:
	docker compose exec postgres psql --username shadowgrid --dbname shadowgrid

shell-redis:
	docker compose exec redis redis-cli

backend-lint:
	node scripts/run-python.mjs -m ruff check apps/api apps/worker

backend-format:
	node scripts/run-python.mjs -m ruff format apps/api apps/worker

backend-typecheck:
	node scripts/run-python.mjs -m mypy apps/api/shadowgrid apps/worker

backend-test:
	node scripts/run-python.mjs --cwd apps/api -m pytest tests -q --cov=shadowgrid --cov-report=term --cov-fail-under=65

frontend-lint:
	pnpm --filter @shadowgrid/web lint

frontend-format:
	pnpm --filter @shadowgrid/web exec prettier --write src

frontend-typecheck:
	pnpm --filter @shadowgrid/web typecheck

frontend-test:
	pnpm --filter @shadowgrid/web test

backup-local:
	powershell -ExecutionPolicy Bypass -File scripts/backup.ps1

restore-local:
	powershell -ExecutionPolicy Bypass -File scripts/restore.ps1 -Backup "$(BACKUP)" -ConfirmRestore RESTORE

assets-manifest:
	pnpm assets:manifest

assets-style-proof:
	pnpm assets:style-proof

assets-generate-next:
	pnpm assets:next

assets-generate-batch:
	pnpm assets:batch --batch=$(BATCH)

assets-generate-city:
	pnpm assets:city --city=$(CITY)

assets-generate-all:
	pnpm assets:all

assets-resume:
	pnpm assets:resume

assets-validate:
	pnpm assets:validate

assets-optimize:
	pnpm assets:optimize

assets-contact-sheets:
	pnpm assets:contact-sheets

assets-integration-test:
	pnpm assets:integration-test

assets-gate:
	pnpm assets:gate

assets-report:
	pnpm assets:report

assets-geodata:
	pnpm assets:geodata
