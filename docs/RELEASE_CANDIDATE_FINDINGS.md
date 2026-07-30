# Phase 12 release-candidate findings

Initial review: 2026-07-28. Scope: roadmap phases 0–11, architecture, authorization,
input boundaries, rate limits, schema invariants, concurrency, release automation, load
evidence and backup/restore. Findings are recorded before remediation as required by the
Phase 12 roadmap.

## Remediation status

Review updated 2026-07-28 after implementation and focused verification.

| Finding | Status | Resolution evidence |
| --- | --- | --- |
| H-01 | Resolved | Transactional `rate_limit_buckets`, atomic SQLite/PostgreSQL increments, hashed identities, expiry cleanup and boundary/reset tests |
| H-02 | Resolved | Database-backed 100-player/500-company/10,000-order release-scale test exercises the economy tick, indexed order-book read and real ledger-backed match |
| M-01 | Resolved | Streaming HTTP byte counter and 16 KiB pre-parse WebSocket handshake ceiling with regressions |
| M-02 | Resolved | Separator-aware backup containment, guarded service restart and script tests |
| M-03 | Resolved | Production/staging HTTPS-origin validator rejects wildcard, localhost and malformed origins |
| M-04 | Resolved | Persisted, verified seed version/random-seed contract |
| M-05 | Resolved | Workspace override pins `tar` 7.5.21; audit, mobile tests and build are release gates |
| M-06 | Resolved | Playwright is capped at two workers with a 15-second assertion window; the full matrix passes with 54 scenarios and 4 intentional mobile-only zoom skips |
| L-01 | Accepted | Deployment must network-restrict `/metrics`; the Prometheus scrape contract remains unauthenticated |
| L-02 | Resolved | The complete React runtime ecosystem is emitted in one framework chunk without a build cycle |
| L-03 | Resolved | Exact accessible link names plus scroll-before-activate make the mobile drawer deterministic |

No Critical or unresolved High finding remains. The initial findings below are retained as
the audit trail rather than rewritten after remediation.

## Critical

No reproducible critical finding was identified.

## High

### H-01 — Authentication and exchange rate limits are process-local

`api.py` stores login and exchange-order attempts in Python dictionaries. A restart clears
them, and each production worker has an independent counter. This permits a caller to
multiply the configured limit across workers and does not meet the production rate-limit
contract.

Required remediation: use a shared transactional store with atomic bucket increments,
bounded retention and regression tests for the limit boundary and reset window.

### H-02 — Roadmap-scale load gates do not exercise the application

The existing Python load tests only sum an in-memory dictionary and hash strings.
`k6.js` calls health, while the multiplayer profile covers four read paths. None creates
100 players, 500 companies or 10,000 open orders, and neither authoritative economy ticks
nor order matching is measured. The current files therefore cannot substantiate the Phase
12 release target.

Required remediation: add a deterministic database-backed scale fixture and measure the
real tick and order-book/matching services with explicit, documented local thresholds.

## Medium

### M-01 — HTTP and WebSocket input limits are incomplete

The HTTP middleware rejects a declared `Content-Length` above 1 MiB, but a body without
that header is not counted while streaming. The WebSocket handshake validates the parsed
schema but does not bound the incoming text before JSON decoding. Both paths can allocate
substantially more memory than the documented request limit.

Required remediation: enforce a receive-stream byte ceiling for HTTP and an explicit
pre-parse WebSocket message ceiling, with regression tests.

### M-02 — Restore path containment check accepts sibling prefixes

`restore.ps1` checks `StartsWith($backupRoot)`. A resolved path such as
`backups-untrusted\file.dump` shares that string prefix while residing outside the backup
directory. The script also restarts API and worker only after a successful restore, so a
failed restore leaves them stopped.

Required remediation: compare against the backup root plus a directory separator and
restart stopped services in a guarded `finally` path. Add a non-destructive script test.

### M-03 — Production CORS configuration accepts unsafe values

`WEB_ORIGINS` has no production validator. An accidental wildcard can be combined with
credentialed CORS, and a production deployment can silently retain the localhost default.

Required remediation: reject wildcard, empty and localhost origins in production/staging,
while preserving explicit local development defaults. Add configuration regression tests.

### M-04 — Demo seed has no persisted version marker

The seed is idempotent but neither its version nor its deterministic configuration is
recorded in the database. Operators cannot distinguish an old seed contract from the
current release candidate after restore or migration.

Required remediation: persist the configured seed version and random seed, reject reuse of
a version with different deterministic inputs and verify it in the release integrity gate.

### M-05 — Expo CLI resolves vulnerable `tar` 7.5.20

The dependency audit reports GHSA-r292-9mhp-454m, a moderate uncontrolled-recursion denial
of service in crafted archive member selection. Expo CLI pulls the affected transitive
version; 7.5.21 contains the patch.

Required remediation: override the transitive package to 7.5.21, refresh the lockfile and
rerun the JavaScript audit and mobile tests/build.

### M-06 — Default Playwright worker count overloads the local release stack

On the reviewed 10-logical-worker Windows host, Playwright launches ten browser workers
against one Vite and one Uvicorn development server. Unrelated desktop and mobile flows
then hit identical 1.3–1.5 minute timeouts, while lighter tests in the same run pass. The
individual phase flows pass when isolated, so this is a reproducible gate-orchestration
failure rather than eight independent feature failures.

Required remediation: set a deterministic two-worker ceiling for the full local/CI suite
and rerun all 58 scenarios from a clean server pair.

## Low

### L-01 — Metrics are unauthenticated at the application boundary

`/metrics` exposes aggregate route names, status codes and timings to every caller that can
reach the API. Compose currently publishes the API port directly. This is useful for local
Prometheus but should be network-restricted in deployed environments.

Disposition: document the network-boundary requirement. Authentication is not added in
this phase because it would break the existing Prometheus scrape contract.

### L-02 — Web production build reports a circular manual chunk

The broad `id.includes("react")` rule puts React consumers and providers into different
manual chunks, producing a `vendor -> react -> vendor` cycle. The build succeeds, but
evaluation order is harder to reason about and the warning obscures later build findings.

Required remediation: classify the complete React runtime ecosystem into one framework
chunk while leaving unrelated dependencies to the vendor chunk.

### L-03 — Critical-flow mobile navigation uses ambiguous and off-screen locators

After the roadmap navigation expanded, Playwright's non-exact `Operations` locator also
matches `Rival operations`, and the Settings link can correctly exist below the mobile
drawer viewport. The product navigation remains labelled and scrollable, but the release
test fails strict mode or asserts viewport presence before scrolling.

Required remediation: use exact accessible names and scroll the selected drawer link into
view before activating it.

## Confirmed controls

- Authorization dependencies separate authenticated user, selected profile and admin
  access; reviewed mutation services perform ownership checks.
- Refresh sessions are hashed, rotated under a row lock and checked on every REST and
  WebSocket authentication path.
- Errors return stable envelopes without stack traces; structured server logs include
  request IDs but not authorization headers or secret values.
- Demo seeding rejects staging and production regardless of `LOCAL_DEMO_MODE`.
- File-upload endpoints are absent.
- Financial mutations use balanced account-ledger services, while share and ownership
  records carry database constraints and domain regression tests.
- CORS methods and headers are explicit, security headers are present, API pagination and
  realtime-feed limits are bounded, and canonical realtime audiences are server-derived.
