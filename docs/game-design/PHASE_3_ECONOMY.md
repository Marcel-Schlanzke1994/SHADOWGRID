# Phase 3: authoritative economy simulation

Phase 3 turns company metrics into deterministic economic results. The server processes one
period per world and UTC hour. A successful period is uniquely identified by
`(world_id, period_key)` and cannot be booked twice.

## Markets and demand

Every active city has one market for each supported company industry. A market stores
integer values for:

- demand units;
- revenue cents per allocated unit;
- variable cost cents per allocated unit;
- fixed operating cost cents per company.

The default Cologne markets are data-driven through `ECONOMY_MARKETS`. They are created
idempotently by world bootstrap and also repaired on demand before a tick.

## Attractiveness and allocation

Company attractiveness is calculated entirely with integers:

```text
1,000
+ quality × 4
+ reputation × 2
+ compliance
+ innovation × 2
+ district economic activity × 50
+ district prosperity × 25
− risk × 2
− investigation pressure × 3
```

The result is clamped to at least one point. Each input and each signed modifier is copied
to the immutable company report.

Demand is distributed proportionally by attractiveness using integer division and a
deterministic largest-remainder tie-breaker based on company UUID. No allocation may exceed
company capacity. If a company reaches its capacity, remaining demand is redistributed
among the other companies in further passes. Therefore:

- equal inputs produce a fair allocation;
- better quality increases allocation while demand is contested;
- allocated units never exceed demand or capacity;
- the sum of market shares never exceeds 10,000 basis points.

## Revenue, costs, profit and value

For each company and tick:

```text
revenue = allocated units × unit revenue
cost = fixed cost + allocated units × variable unit cost
profit = revenue − cost
```

A positive result transfers integer cents from the world system account to the company
account. A negative result transfers available company cash to the system account. If the
loss exceeds available cash, the account stops at zero and the uncovered amount becomes
company debt. Every cash movement is a balanced double-entry transaction.

Enterprise value version 1 is:

```text
capacity × 4,000
+ quality × 1,000
+ innovation × 500
+ max(profit, 0) × 6
+ company cash
− company debt
```

The result is clamped to the non-negative signed 64-bit range.

## Transaction and concurrency boundary

The world row is locked before the tick record is created. Markets, allocations, financial
transfers, company state, metric snapshots and reports commit in one database transaction.
A process lock serializes the SQLite/local path; the PostgreSQL world row lock and unique
period constraint protect multi-process deployments. Any calculation or settlement failure
rolls back the complete period.

`MarketEconomyReport` and `CompanyEconomyReport` records are append-only. The latter
contains inputs, modifiers, allocation, revenue, cost, profit, cash/debt changes and the
before/after enterprise value.

## Scheduling, contracts and UI

ARQ schedules the authoritative economy tick hourly at minute 0, second 30. The existing
legacy-business settlement remains separate during the compatibility migration.

- `GET /api/v1/economy/status`
- `GET /api/v1/economy/markets`
- `GET /api/v1/economy/markets/{market_id}/reports`
- `GET /api/v1/companies/{company_id}/economy-reports`
- `POST /api/v1/admin/economy/ticks`

The admin endpoint supports a timezone-aware current or historical period and rejects future
periods. The company dashboard shows the last completed tick, the next scheduled tick,
loading/empty/error/success states, an accessible revenue/cost/profit time series and exact
report rows. All timestamps are localized by the client; the database and API use UTC.
