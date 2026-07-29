# SHADOWGRID player lifecycle final report

Date: 2026-07-29
Status: passed

## Reproducible gate

Run the complete gate:

```powershell
pnpm test:lifecycle
```

Focused variants:

```powershell
pnpm test:lifecycle -- --api-only
pnpm test:lifecycle -- --e2e-only
node scripts/verify-lifecycle.mjs --list
```

The ordered source of truth is `scripts/lifecycle-plan.json`. The runner rejects missing
or unordered steps and deduplicates shared scenarios before execution.

## Personas

The plan contains the entrepreneur, investor, cartel leader, cartel member,
intelligence strategist, administrator and local AI player.

## Required lifecycle

| Steps | Capability | Automated evidence |
| --- | --- | --- |
| 1–3 | Registration, token verification, rotating session, Cologne onboarding | Auth and onboarding API tests; auth and critical-flow Playwright |
| 4–8 | Company, investment, specialists, economy, payroll and local AI | Company, economy and specialist/AI API suites; responsive UI flows |
| 9–12 | IPO, buy/sell orders, partial fill, cancellation and dividend | Exchange API suite with fixed supply assertions; exchange UI flow |
| 13–16 | Cartel, membership, treasury four-eyes rule, project and control | Cartel API suite with authorization/concurrency/ledger assertions; cartel UI flow |
| 17–20 | Intelligence, report trading, abstract strategy and world events | Intelligence and event API suites; corresponding accessible UI flows |
| 21–24 | Contracts, loans, bonds and real estate | Domain suites with exact balanced settlements; four responsive UI flows |
| 25 | Reconnect and notification reconciliation | WebSocket cursor and durable notification tests; REST reconciliation UI flow |
| 26–30 | Season phases, close, Hall of Fame, rewards, next season and immutable history | Season API suite and player/admin season UI flows |

## Results

| Gate | Result | Duration |
| --- | --- | --- |
| API lifecycle | 33 passed, 0 failed | 548.53 seconds |
| Playwright lifecycle | 40 passed, 0 failed, 2 expected skips | 8.4 minutes |
| Desktop project | Chromium | passed |
| Mobile project | Pixel 7 viewport | passed |
| Axe critical/serious | 0 | passed |

The two skipped cases are the mobile project instances of the desktop-only 200% browser
zoom assertion. Mobile reflow, navigation, touch layout and Axe checks execute in their
own cases.

## Integrity checkpoints

The selected financial scenarios assert balanced immutable ledger transfers,
idempotency, ownership and retry behavior. Exchange scenarios additionally assert that
the sum of all holdings remains equal to the fixed share-class supply after IPO, fills,
cancellation, concurrency and dividends. Season closure preserves ledger, trade,
archive, Hall of Fame and reward history while resetting only season-scoped resources.
