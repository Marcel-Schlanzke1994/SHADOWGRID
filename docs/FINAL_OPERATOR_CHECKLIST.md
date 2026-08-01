# SHADOWGRID final operator checklist

## Local start

On the reviewed Windows target:

```powershell
pnpm setup
powershell -ExecutionPolicy Bypass -File scripts/start-local.ps1
powershell -ExecutionPolicy Bypass -File scripts/verify-local.ps1
```

Open `http://127.0.0.1:5173`. Stop the owned local processes with:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/stop-local.ps1
```

Linux/WSL operators use the equivalent `scripts/setup-local.sh`,
`scripts/start-local.sh`, `scripts/verify-local.sh` and `scripts/stop-local.sh` commands.
Compose remains the PostgreSQL/Redis production-parity path when Docker is installed.

## Candidate verification

- Confirm the candidate is committed and `git status --short` is empty.
- Run `pnpm release:final-run`; never use `--no-verify` or disable a failing gate.
- Review the generated `docs/release-evidence/final-release-*/FINAL_RELEASE_RUN.json`.
- Confirm every recorded step has exit code 0 and a SHA-256 log hash.
- Confirm `pnpm i18n:release` reports 36/36 approved packages with no fallback, source clone, incomplete role or missing evidence.
- Confirm the asset gate reports 896/896 approved, zero pending/review/rejected/failed.
- Confirm store readiness reports 30/30 approved and 20 real application captures.
- Confirm the balance report has no critical exploit or ledger imbalance.
- Confirm backup/restore has identical source/restored SHA-256 and post-restore invariants.
- Run `git diff --check` and the final review before promotion.

## Production prerequisites

- A current verified backup exists and its hash is recorded.
- All Alembic migrations are reviewed as backward compatible for the deployment window.
- API and worker readiness, PostgreSQL, Redis and ledger alerts are bound to real providers.
- `METRICS_TOKEN` is at least 32 random characters and `/metrics` is network restricted.
- `WEB_ORIGINS`, public web URLs and the mobile production API are explicit HTTPS values.
- Local demo mode is disabled by production configuration.
- SMTP sender/domain, processor register, retention policy, support identity and incident
  owner have named approvals.
- Rollback owner, on-call recipient and maintenance communication are scheduled.

## Post-deploy smoke

Only with `FINALIZE_ALLOW_PRODUCTION_DEPLOY=true`:

```powershell
pnpm smoke:production
pnpm data:verify
```

The smoke must prove liveness, readiness, tracing, authentication, current user, world list,
safe world read and logout without printing tokens. Inspect both API and worker structured
logs by request ID. Roll back on any required failure.

## Store release

- Verify the 20 source screenshots and ten static marketing entries in
  `STORE_ASSET_READINESS.md`.
- Approve store copy and the required screenshot set for every public locale; the global
  build cannot ship a partial language set.
- Complete physical-device login, session restore, deep-link, offline, dark-mode, maximum
  text-size, TalkBack/VoiceOver, touch-target and tablet checks.
- Build signed AAB/IPA only from the real EAS organization account.
- Submit to internal tracks, then staged rollout; monitor crashes, auth and API health.

## Forbidden operator shortcuts

- Do not paste credentials into commands, tickets, screenshots, reports or Git.
- Do not hand-edit money, shares, property, ownership, ledger, trade or audit rows.
- Do not mark physical accessibility, legal approval, provider delivery or store acceptance
  complete without external evidence.
- Do not push, tag, deploy, send provider email or submit stores without the corresponding
  `FINALIZE_ALLOW_*` flag.
