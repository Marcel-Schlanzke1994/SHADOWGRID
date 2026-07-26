# Multiplayer Load Test Report

Date: 2026-07-19  
Environment: local Windows workspace, SQLite test database, Python test runner.  
Production k6 execution: not run because k6 is not installed in this workspace; the authenticated profile is committed for CI/staging use.

## Executed results

| Check | Result | Duration |
|---|---:|---:|
| Full API unit/integration suite | 24 passed | 274.37 s |
| Load smoke suite | 3 passed | 6.10 s |
| Concurrent one-offer/two-buyer race | 1 settlement, 1 conflict, 0 duplicate trades | included in API suite |
| Parallel deterministic resolution floor | 1,000 inputs × 2 identical passes | included in load suite |

The deterministic floor uses 40 worker threads. Both 1,000-item passes produce identical rolls/outcomes with 1,000 unique operation inputs, demonstrating that parallel scheduling cannot reroll an operation.

The market race sends two simultaneous authenticated acceptance requests for one offer. Observed status codes were HTTP 200 and HTTP 409. Postconditions: one trade row, seller credited once, five intelligence reserved once, and the two buyers' combined balances changed by exactly one purchase.

## Prepared k6 profile

`tests/load/k6-multiplayer.js` defines four concurrent 25-VU scenarios (100 VUs total) for 30 seconds:

- PvP target readers
- Territory observers
- Cartel-war observers
- Communication-channel observers

Thresholds:

- HTTP failure rate < 1%
- HTTP request duration p95 < 750 ms

When `ACCESS_TOKEN` is absent the script safely falls back to health reads, so credentials never need to be placed in source. A staging run uses:

```powershell
$env:API_URL = "https://staging.example/api/v1"
$env:ACCESS_TOKEN = "<short-lived-test-token>"
k6 run tests/load/k6-multiplayer.js
```

## Interpretation

The local results validate deterministic CPU work, transactional race behavior, and test-profile completeness. They do not prove Railway production capacity or PostgreSQL p95 latency. Release acceptance should run the k6 profile against an isolated staging world using PostgreSQL, observe database lock wait/outbox depth, and record p50/p95/p99 plus error distribution. The committed thresholds are the deployment gate.

