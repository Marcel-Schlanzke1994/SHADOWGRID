# SHADOWGRID roadmap gap analysis

Reviewed on 2026-07-26 against `SHADOWGRID_CODEX_MASTER_ROADMAP.md`,
`docs/game-design/SHADOWGRID_SPEC.md`, `AGENTS.md`, the Alembic migrations and the
generated OpenAPI source.

## Resolution of source conflicts

The roadmap's Flask/Celery/Socket.IO stack conflicts with the existing canonical
FastAPI/ARQ architecture. The technical stack remains FastAPI/ARQ; the roadmap's domain,
integrity, security and user-flow requirements remain binding. This avoids a framework
rewrite while preserving the modular monolith and authoritative database transaction
boundary.

## Current phase status

| Phase | Status | Evidence and next gap |
| --- | --- | --- |
| 0 Foundation | Aligned | Monorepo, Compose, PostgreSQL, Redis, worker, health/readiness, CI, local secret generation and tests exist. GNU Make and WSL bootstrap compatibility were added. |
| 1 Auth/onboarding | Aligned | Argon2id, access/rotating refresh tokens, verification, rate limits, Cologne plus five start districts, one-time idempotent city selection, exact configurable €80,000 grant and roadmap API contracts are covered by integration and browser tests. |
| 2 Companies | Aligned | Private companies, per-season unique names, business accounts, balanced founding/investment transfers, exact 10,000-bps ownership, metric history, idempotency, row locks, ownership checks, confirmation UI, migration and tests are implemented. |
| 3 Economy/ledger | Aligned | Integer-cent double entry, per-city industry markets, capacity-constrained deterministic allocation with rest-demand redistribution, atomic/idempotent hourly ticks, immutable reports, time series and dashboard charts are implemented. |
| 4 Specialists/AI | Aligned | A deterministic six-role city market, owned-company employment, capped economy effects, balanced hourly payroll, energy/loyalty/level progression, immutable reports, five pausable rule-based AI profiles and nine seeded competitor companies are implemented. |
| 5 Exchange | Aligned | Configurable IPO qualification, immutable common-share supply, issuer holdings, reserved price-time matching, atomic full/partial trades, cancellation/expiry, price snapshots, portfolios, shareholder views and idempotent snapshot dividends are implemented with concurrency and browser tests. |
| 6 Cartels/influence | Aligned | One-active-membership enforcement, invitation workflow, canonical roles, transactional leadership, balanced cartel accounts, independent large-expense approval, five project templates, concurrent idempotent contributions, district influence/control and seasonal cartel ranking are implemented. |
| 7 Intelligence/PvP | Aligned | Public/analyzed/covert reports, hidden accuracy states, stored deterministic outcomes, protection/cartel/specialist modifiers, detection pressure, cooldowns/rate limits, immutable report-copy trading and five expiring abstract strategic effects are implemented. |
| 8 Events/admin | Aligned | Five versioned definitions, read-only previews, immutable concrete instances, deterministic bounded overlap, idempotent lifecycle processing, economy/payroll report modifiers, admin RBAC/audit and durable realtime notifications are implemented. |
| 9 Seasons | Aligned | Six deterministic phases, versioned goals/templates, twelve immutable score categories, explicit ties, idempotent close, Hall of Fame, permanent account rewards, seasonal archives and ledger-backed non-destructive reset are implemented. |
| 10 Extended markets | Aligned | Commercial contracts, company loans, bonds and district-indexed real estate are implemented with immutable terms/history, ledger-backed money/ownership, retry-safe schedulers, abstract defaults, season boundaries and responsive browser coverage. |
| 11 Realtime/UX | Aligned | Protocol-v1 WebSocket and REST feeds share server-derived world/city/cartel/player audience filters, durable reconnect cursors and canonical validated events. Immutable unread/read notifications, query reconciliation and responsive accessible browser coverage are complete. |
| 12 Hardening | Aligned | Shared rate limits, bounded inputs, strict production CORS, persisted seed identity, database invariant checks, real roadmap-scale load coverage, verified backup/restore, dependency hardening and deterministic full-stack browser orchestration are implemented. No Critical or unresolved High release finding remains. |

## Implementation order

All roadmap phases are aligned. Phase 12 re-reviewed architecture and security, added
database-backed release-scale evidence, proved clean migration/seed and backup/restore,
closed every High and Medium release finding, and records the final release workflow in
the release notes.
