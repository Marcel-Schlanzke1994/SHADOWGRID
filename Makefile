.PHONY: setup dev migrate seed test test-e2e lint typecheck security validate reset-local logs stop clean

setup:
	pnpm setup

dev:
	pnpm dev

migrate:
	pnpm migrate

seed:
	pnpm seed

test:
	pnpm test

test-e2e:
	pnpm test:e2e

lint:
	pnpm lint

typecheck:
	pnpm typecheck

security:
	pnpm test:security

validate:
	pnpm validate

reset-local:
	powershell -ExecutionPolicy Bypass -File scripts/project.ps1 reset-local

logs:
	pnpm logs

stop:
	pnpm stop

clean:
	pnpm clean
