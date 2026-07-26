.PHONY: setup dev migrate seed test test-e2e lint typecheck security validate reset-local logs stop clean \
	assets-manifest assets-style-proof assets-generate-next assets-generate-batch \
	assets-generate-city assets-generate-all assets-resume assets-validate \
	assets-optimize assets-contact-sheets assets-integration-test assets-report \
	assets-geodata

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

assets-report:
	pnpm assets:report

assets-geodata:
	pnpm assets:geodata
