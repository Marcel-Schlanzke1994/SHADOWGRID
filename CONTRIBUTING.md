# Contributing

Read `AGENTS.md` before changing code. Create a focused branch, add or update tests and run:

```powershell
pnpm lint
pnpm typecheck
pnpm test
pnpm validate
```

Schema changes require an Alembic migration. Resource changes require ledger entries and idempotency coverage. Visible text requires localization keys. UI changes require keyboard and responsive checks.
