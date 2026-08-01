# SHADOWGRID final external gates

Repository and local completion do not grant authority over production, third-party
accounts, legal approval, signing credentials or physical-device evidence. Every action
below remains blocked until its named input and explicit release flag exist.

| Gate | Current state | Required external input | Authorization / execution |
| --- | --- | --- | --- |
| Production deployment | blocked_external | Approved target, backup, on-call owner and change window | Set `FINALIZE_ALLOW_PRODUCTION_DEPLOY=true`, then follow `DEPLOYMENT.md` |
| Git push | blocked_external | Approved remote and branch-protection workflow | Set `FINALIZE_ALLOW_GIT_PUSH=true`; `git push -u origin codex/finalize-shadowgrid` |
| Git tag | blocked_external | Release-owner approval after immutable evidence review | Set `FINALIZE_ALLOW_GIT_TAG=true`; `git tag -a v0.1.0-rc.2 -m "SHADOWGRID 0.1.0-rc.2"` |
| Store signing/submission | blocked_external | EAS project, Apple/Google accounts, signing credentials, legal copy and device acceptance | Set `FINALIZE_ALLOW_STORE_SUBMISSION=true`; use the commands in `MOBILE_RELEASE_READINESS.md` |
| Transactional SMTP | blocked_external | Approved provider, verified sender/domain, credentials and monitoring | Set `FINALIZE_ALLOW_EMAIL_PROVIDER_ACTIVATION=true`; follow `SMTP_PROVIDER_OPERATOR_GATE.md` |
| Docker/PostgreSQL/Redis proof | blocked_external on this host | Docker Desktop or equivalent runtime | `docker compose up --build -d`; run readiness, worker and PostgreSQL restore checks |
| Privacy/legal approval | blocked_external | Named legal owner, retention owner, processor contracts and support identity | Complete `PRIVACY_LAUNCH_CHECKLIST.md`, `DATA_RETENTION_MATRIX.md` and `PROCESSOR_REGISTER_TEMPLATE.md` |
| GitHub Dependency Review | blocked_external | Pushed branch and pull-request context | Run the repository Dependency Review workflow on the resulting pull request |
| Physical accessibility | blocked_external | Signed builds, real Android/iOS devices and human TalkBack/VoiceOver review | Record every item in `ACCESSIBILITY_FINAL_REPORT.md` and `MOBILE_RELEASE_READINESS.md` |
| Alert-provider binding | blocked_external | Production telemetry provider and on-call routing owner | Import `monitoring/alert-definitions.json`, bind real data sources and test each route |
| Global localization | blocked_external | Qualified translators, independent native reviewers, linguistic QA, legal/store/support owners and physical-device evidence for all 36 locales | Complete every locale `review.json`/`coverage.json`, run `pnpm i18n:screenshots`, then `pnpm i18n:release` |

## Production sequence

Only after the production flag and all prerequisite owners are present:

```powershell
pnpm release:final-run
powershell -ExecutionPolicy Bypass -File scripts/backup.ps1
# Perform the reviewed platform deployment from docs/DEPLOYMENT.md.
pnpm smoke:production
pnpm data:verify
```

Rollback is required if readiness, authentication, safe world read, non-destructive player
action, logout, worker health or post-deploy invariants fail. Do not edit ledger, ownership,
share or audit rows manually.

## Mobile sequence

From a real organization-owned EAS account:

```text
npx eas-cli init
npx eas-cli build --profile preview --platform android
npx eas-cli build --profile preview --platform ios
```

After physical-device, legal and store-asset approval and only with the store flag:

```text
npx eas-cli build --profile production --platform android
npx eas-cli build --profile production --platform ios
npx eas-cli submit --profile production --platform android
npx eas-cli submit --profile production --platform ios
```

Submit to internal testing first and use staged rollout. Never create or commit signing
keys, provider tokens or SMTP credentials in this repository.

## Optional paid asset generation

`FINALIZE_ALLOW_PAID_ASSET_GENERATION` is false. It is not required for local/repository
completion because the reviewed project-owned procedural library is the production
fallback. Turning the flag on later authorizes provider cost only; it does not bypass
manifest order, budget, safety, originality, license or visual-review gates.
