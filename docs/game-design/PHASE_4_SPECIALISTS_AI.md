# Phase 4: specialists and local competitors

Phase 4 adds a deterministic specialist labour market and server-controlled local
competitors to the Phase 3 economy. The API and worker remain authoritative: clients show
costs, effects and status, but never calculate payroll, company modifiers or AI actions.

## Specialist market and employment

Each active city receives twelve candidates per UTC day. Candidate IDs, names, roles,
levels, skills and salaries are derived from the world, city, date and slot with SHA-256
and UUIDv5. Repeating a refresh for the same cycle therefore produces the same market
without duplicate rows.

The six supported roles are:

- finance director;
- technology expert;
- market analyst;
- compliance officer;
- logistics expert;
- diplomat.

Hiring requires an owned company, free personnel capacity and enough company cash to cover
the first salary period. The candidate and player profile are locked, the candidate becomes
unavailable, and the command stores an idempotency record and audit entry. Assignment and
release use the same ownership and idempotency boundary. Reassignment has a one-hour
cooldown; release is blocked while an operation is active and ends company effects
immediately.

## Transparent company effects

Only hired or assigned specialists with at least 30 loyalty and 10 energy are active.
Their primary skill and level produce integer modifiers:

| Role | Company effect |
| --- | --- |
| Finance director | operating-cost reduction |
| Technology expert | attractiveness |
| Market analyst | revenue bonus |
| Compliance officer | attractiveness |
| Logistics expert | capacity |
| Diplomat | attractiveness |

Aggregated effects are capped at 5,000 capacity units, 1,500 revenue basis points, 2,000
cost-reduction basis points and 25,000 attractiveness points. The economy report records
the applied specialist modifiers. Revenue bonuses and cost reductions use integer
multiplication and division; no floating-point game value enters settlement.

## Hourly payroll

Payroll runs after the completed economy tick for the same world and UTC-hour period.
`(world_id, period_key)` is unique, so retries return the first completed payroll tick.
Each salary uses the balanced company-expense ledger service:

- a full payment increases loyalty by one and grants ten experience points;
- a partial payment reduces loyalty by five and grants four experience points;
- a missed payment reduces loyalty by ten and grants no experience;
- uncovered salary becomes non-negative company debt and company cash never overdraws.

Idle specialists recover eight energy per period; specialists attached to an active
operation consume ten. Experience drives levels from 1 through 10. The payroll report,
company metric snapshot and financial transaction commit atomically. Payroll reports are
immutable.

SQLite uses a local process lock for refresh and payroll concurrency. PostgreSQL also locks
the city/world row and relies on unique cycle/period constraints, so multiple workers
cannot create candidates or book salaries twice.

## Deterministic local AI

Five seeded local profiles cover the strategies growth, efficiency, innovation,
market-share and stability. The demo seed creates nine named competitor companies and
three historical economy/decision periods reproducibly.

One decision is stored per AI profile and period. A decision either founds a company,
invests in capacity/quality/innovation/compliance, or holds when validation prevents an
action. Its seed depends only on the profile seed, profile ID and period. AI actions call
the same `create_company` and `invest_in_company` application services as players, including
ownership, affordability, idempotency, audit and balanced-ledger validation. A failed
action becomes an explicit skipped decision; it never bypasses a rule or directly edits
cash. Admins can pause or resume each local profile.

## API and web contracts

- `GET /api/v1/specialist-market`
- `POST /api/v1/specialist-market/{candidate_id}/hire`
- `GET /api/v1/specialists`
- `POST /api/v1/specialists/{specialist_id}/assign`
- `POST /api/v1/specialists/{specialist_id}/release`
- `GET /api/v1/specialists/{specialist_id}/payroll-reports`
- `GET /api/v1/companies/{company_id}/specialist-effects`
- `GET /api/v1/economy/competitors`
- `POST /api/v1/admin/specialists/payroll`
- `GET|PATCH /api/v1/admin/ai/players`
- `POST /api/v1/admin/ai/ticks`

The web flow exposes market, hired, loading, empty, error and success states; exact recurring
salary; skills, loyalty, energy and level; company effects; payroll history; local-simulation
labels; and confirmation dialogs for hire and release. Keyboard navigation, mobile layout
and serious/critical Axe findings are covered by Playwright.
