# SHADOWGRID season 0 balance configuration

This report records the configuration used by the deterministic release simulation.

| Setting | Value |
| --- | --- |
| Starting cash | EUR 80,000.00 |
| Company founding transfer | EUR 20,000.00 |
| Players | 100 |
| Companies | 500 |
| Companies per player | 5 |
| Market instances per industry | 32 |
| Cartels | 10 |
| Seasons | 4 |
| Periods per season | 24 |
| Seed | 20260729 |

Production industry, market and investment values are imported directly from
`shadowgrid.game_config`; this document does not duplicate or override them.

Release gates:

- strategy wealth spread no more than 2,000 bps;
- largest cartel no more than 2,500 bps;
- newcomer/early median wealth at least 8,000 bps;
- exact integer market allocation;
- no simulation ledger imbalance;
- no negative player cash.
