# Phase 12 — Release hardening

Phase 12 turns the phase-0–11 implementation into a reproducible release candidate. It
adds no new player economy. Its domain is evidence: shared abuse controls, persisted seed
identity, executable database invariants, realistic capacity tests and recoverable
operations.

## Security and input boundaries

Login and exchange-order attempts use database-backed fixed-window buckets keyed by a
one-way identity digest. Atomic increments are shared by all API workers and survive
restart; successful login clears its bucket. HTTP bodies are limited by counted received
bytes even without `Content-Length`, and the WebSocket handshake is rejected before JSON
parsing above 16 KiB. Production/staging CORS accepts only explicit HTTPS origins and
rejects wildcard, localhost, path, query and credential-bearing values.

## Data and deterministic bootstrap

Migration `0017_release_hardening` adds rate-limit buckets and seed-run records. The seed
stores both its version and deterministic random seed, remains idempotent for the same
contract and refuses to reuse a version with different inputs.

The read-only release verifier checks:

- every account transaction has at least two entries and sums to zero;
- account balances equal their latest ledger projection and remain non-negative with valid
  reservations;
- private-company ownership equals exactly 10,000 basis points;
- every listed company has exactly its immutable fixed share supply;
- economy allocation/report shares stay within their integer limits;
- SQLite foreign keys remain valid on the local target.

## Capacity and recovery

The release-scale test creates 100 players, 500 companies and 10,000 open orders in a real
database. It measures the authoritative economy tick, indexed order-book retrieval and a
real atomic match that transfers ledger-backed cash and shares. It is deterministic and
keeps explicit ceilings appropriate to the supported local workstation.

Production backup remains a verified PostgreSQL custom dump. With Docker unavailable, the
local SQLite fallback uses the SQLite backup API, integrity checks and SHA-256. Restore
accepts only verified sources resolved under `backups/`, creates a pre-restore safety copy
for SQLite, replaces atomically and restarts stopped Compose services through a guarded
path.

## Release acceptance

No Critical or unresolved High finding may remain. Migration upgrade/downgrade/drift,
repeat seed, invariant verification, dependency audits, unit/integration tests, load,
mobile export, web production build and the complete desktop/mobile Playwright matrix are
mandatory. The executable workflow is `pnpm validate`, exposed as `make verify-release`
when GNU Make is available.
