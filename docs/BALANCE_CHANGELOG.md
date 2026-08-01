# SHADOWGRID balance changelog

## 0.1.0-rc.2 simulation baseline

- Added a deterministic 4-season balance gate for
  100 players, 500 companies and
  10 cartels.
- Preserved all production monetary and quantity values as integers.
- No production balance constant was changed: current release configuration passes the
  2,000 bps strategy-spread, 2,500 bps cartel-dominance and 8,000 bps newcomer-fairness
  gates.
- Historical season snapshots remain untouched; simulation results are written only to
  `.project/balance-simulation-results.json`.
