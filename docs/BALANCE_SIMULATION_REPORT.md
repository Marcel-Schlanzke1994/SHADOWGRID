# SHADOWGRID balance simulation report

Status: passed

## Scope

- Deterministic seed: `20260729`
- Players: 100
- Companies: 500
- Competing cartels: 10
- Complete seasons: 4
- Periods per season: 24
- Strategies: balanced, expansion, quality, finance, cartel

## Season outcomes

| Season | Active companies | Public companies | Median wealth | Gini bps | Market HHI | Largest cartel bps | New/early wealth bps |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 500 | 358 | EUR 2,440,842.31 | 2310 | 64 | 1156 | 11486 |
| 1 | 500 | 388 | EUR 2,550,808.22 | 2079 | 60 | 1267 | 10183 |
| 2 | 500 | 378 | EUR 2,576,114.32 | 1886 | 49 | 1142 | 11460 |
| 3 | 500 | 391 | EUR 2,580,080.27 | 2006 | 57 | 1391 | 10321 |

## Lifecycle medians

- First company: period 1
- First profit: period 1
- First specialist: period 3
- First IPO: period 10
- Meaningful decisions per player in latest season: 19
- Latest-season exchange trades: 28979

## Strategy comparison

| Strategy | Mean of seasonal median wealth |
| --- | --- |
| balanced | EUR 2,527,796.27 |
| cartel | EUR 2,427,632.48 |
| expansion | EUR 2,681,174.48 |
| finance | EUR 2,713,796.26 |
| quality | EUR 2,605,622.68 |

The multi-season strongest-to-weakest spread is 1178 bps. The
highest mean strategy is `finance`; it
passes the 2,000 bps dominance
gate.

## Investment utility

| Investment | Observed return proxy bps |
| --- | --- |
| capacity | 291448 |
| compliance | 184151 |
| innovation | 151818 |
| quality | 204246 |

Every investment is exercised by at least one strategy and retains a positive return
proxy. Costs and quantities remain integer cents/units.

## Risk and recovery

- Top-ten wealth share: 1932 bps
- Property concentration among top ten: 1041 bps
- Bottom-quartile comeback gain: 6553 bps
- Insolvency: 660 bps
- Contract defaults: 1 bps
- Loan defaults: 0 bps
- Bond defaults: 0 bps
- Ledger-model imbalance: 0 cents

## Exploit gate

Critical findings: none.
No strategy exceeds the configured dominance gate, no cartel controls more than a
quarter of simulated influence, and new-player median wealth remains at least 80% of the
early cohort.
