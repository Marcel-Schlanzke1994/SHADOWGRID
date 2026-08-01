# Security final report

Status: `repository_complete_with_external_ci_gate`
Assessment date: 2026-07-30
Scope: local release candidate on `codex/finalize-shadowgrid`

## Release gate result

There are no open reachable Critical or High findings in the reviewed application and
lockfiles. No Medium deviation is accepted. The final Phase 13 run repeats every command
below and records the immutable commit and exit codes in `FINAL_RELEASE_EVIDENCE.md`.

| Control | Evidence | Result |
| --- | --- | --- |
| Secret patterns | `pnpm test:security` masked path-only scanner | passed |
| Python static security | Bandit over API and worker | passed |
| Python dependencies | `pip-audit` against `apps/api/requirements.txt` | 0 known vulnerabilities |
| JavaScript dependencies | `pnpm audit --audit-level high` | passed with the reviewed React Router exception below |
| Authentication/session rotation | `apps/api/tests/test_auth.py` | automated |
| IDOR and ownership | permissions, multiplayer, gameplay and domain suites | automated |
| Shared rate limits | `apps/api/tests/test_rate_limits.py` and exchange/intelligence suites | automated |
| Input limits | HTTP and WebSocket limit tests in the release suite | automated |
| CORS and deployment configuration | `apps/api/tests/test_config.py` | automated |
| Metrics exposure | production/staging Bearer protection and tests | automated |
| Backup path and restore | release-script, local-backup and isolated restore-drill evidence | automated |
| Ledger/share invariants | ledger, exchange, season and `pnpm data:verify` suites | automated |

The deterministic balance simulator uses `random.Random` only to produce reproducible
non-security scenarios. Its two calls carry narrow Bandit `B311` suppressions and the
module carries the matching Ruff exclusion; no authentication, token, outcome-security or
cryptographic path imports the simulator.

## React Router advisory disposition

The `GHSA-qwww-vcr4-c8h2` audit entry concerns React Router RSC server actions. SHADOWGRID
uses `BrowserRouter` in a Vite browser bundle and a FastAPI REST authority. It installs no
React Router framework server, RSC runtime or server-action endpoint. The advisory is
therefore unreachable in this architecture and remains the one documented audit ignore.

Owner: Security/Architecture. Risk: dormant dependency code only. Expiry: remove the
exception before any React Router framework, RSC or server-action adoption, or immediately
when an upstream package release removes the advisory without regression.

## Privacy and log security

HTTP logs contain request ID, method, route template, status and duration only. Automated
tests reject passwords, raw tokens, verification links and direct account identifiers in
auth logs. Account deletion revokes sessions, consumes one-time tokens, redacts queued mail,
revokes invitations and pseudonymizes direct account fields without deleting immutable
financial or audit history. Analytics remain disabled by default.

## External CI gate

GitHub Dependency Review requires a pull-request base/head graph and cannot run against an
unpublished local branch. The workflow is retained as a mandatory PR check. Because
`FINALIZE_ALLOW_GIT_PUSH` is false, this is explicitly `blocked_external`, not reported as
locally executed. The operator command is:

```text
git push -u origin codex/finalize-shadowgrid
```

Then open a pull request and require the configured dependency-review check before merge.
