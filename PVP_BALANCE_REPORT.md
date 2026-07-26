# PvP Balance Report

Status: initial multiplayer balance baseline, 2026-07-19.

## Operation ladder

| Operation | Minutes | Cash | Influence | Base power | Max district effect |
|---|---:|---:|---:|---:|---:|
| Intelligence probe | 10 | 2,500 | 1 | 24 | 2 |
| Market pressure | 20 | 5,000 | 2 | 30 | 3 |
| Influence campaign | 30 | 7,500 | 3 | 36 | 5 |
| Abstract disruption | 40 | 10,000 | 3 | 40 | 4 |
| Strategic confrontation | 60 | 15,000 | 5 | 44 | 5 |

The progression raises commitment and visibility without allowing a single operation to erase a player or cartel position. Effects are limited influence changes in one fictional district; no direct account, business, or organization deletion exists.

## Preview and hidden information

Target search exposes only codename, cartel, public reputation bands, approximate strength, known presence, treaty/protection status, and recommendation. Exact balances, defensive commitments, exact probability, seed, and roll remain server-only.

The preview combines operation baseline, relative strength band, current protection, alliance/treaty relation, cooldown, repetition multiplier, and operation slots. It returns a qualitative band rather than an exact success probability.

## Repetition and anti-grief

- Each repeat against the same target in 24 hours adds 50% to cost.
- Each repeat reduces reward to a floor of 25%.
- Three launches against the same target in 24 hours reach the daily target limit.
- Resolution adds a two-hour direct-target cooldown.
- New-player and recovery protection block offensive launch.
- Starting an offensive action ends the attacker's ordinary new-player protection.
- Active non-aggression treaties and shared alliances block attacks.
- Operation slots cap simultaneous offensive work.

These controls combine escalating cost, falling benefit, hard frequency ceilings, and protected recovery rather than relying on a single cooldown.

## Defense and support

Eight abstract defense choices provide bounded defense power. The defender sees the deadline and can submit once. Same-cartel players may contribute bounded cash/influence to the appropriate side. All contributions are ledger-backed and idempotent.

## Resolution and reports

Resolution is server-side and deterministic from operation ID plus the protected seed secret. Attacker/defender strength, risk posture, defense choice, and bounded support affect the threshold. The threshold is clamped to prevent certainty.

The attacker and defender receive different report rows:

- Attacker: limited outcome band, district, and only `unknown_countermeasures` for defense.
- Defender: own defense action, own effect points, and the defensive perspective.

Report access is owner-only. The integration test proves that the attacker cannot fetch the defender report and that attacker details do not leak the defense action.

## Initial tuning signals

Monitor operation selection share, preview-to-launch rate, defense response rate, success by relative strength band, repeat-target attempts, cooldown rejection rate, effect per active player, and support concentration by cartel. Rebalance through configuration values only after a full season sample; do not tune from individual losses.

## Test evidence

The PvP integration flow verifies target visibility, preview, duplicate launch, independent login session access, defense, resolution, distinct private reports, report denial, cooldown, exactly-once ledger entries, audit events, and realtime hints.

