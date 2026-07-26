# Cartel War System Report

Status: implemented baseline, 2026-07-19.

## Lifecycle

1. `ultimatum`: an authorized cartel leader records opponent, reason, demand, peace conditions and objective.
2. `preparation`: declaration requires current-password reauthentication; participants and resources can be committed.
3. `active`: joined participants launch bounded war operations and update weighted score categories.
4. `aftermath`: scoring closes while reports and outcome processing remain visible.
5. `ended`: score victory, stalemate, ceasefire, or surrender is persistent.

Production defaults provide a 12-hour preparation period and a six-hour active window; tests compress phase start to exercise the complete loop. Worker phase advancement is idempotent.

## Eligibility and permissions

Organization roles have explicit permissions for proposal, declaration, preparation, resource commitment, report access, ceasefire negotiation, and surrender. Director retains wildcard authority; deputy and dedicated war/diplomacy roles receive narrower powers. Current-password reauthentication is required for declaration and surrender.

Wars cannot target the same cartel, a cartel in another world, an active non-aggression partner, or a cartel sharing an active alliance. Non-parties may see public war/events but cannot enter score or private report views.

## Score model

| Category | Weight |
|---|---:|
| Territorial | 25% |
| Economic | 20% |
| Operations | 20% |
| Intelligence | 15% |
| Participation | 10% |
| Stability | 10% |

Penalties subtract after weighted categories. Each operation contributes a bounded delta (maximum 25), updates the participant contribution, recalculates the cartel score, and writes an event/audit record. Repeated delivery with the same profile/idempotency key returns the original operation and does not score twice.

## Territory relationship

Every fictional district has six abstract control points: economic network, information center, logistics node, social access, digital node, and coordination center. Claims start visible and expire unless supported. Contributions raise claim strength; crossing the threshold moves one control point and records immutable history. Abandonment releases controlled points.

Territory control does not directly delete opponent assets. It is an influence/state input and a war objective, which keeps losses recoverable.

## Diplomacy and ending

Either party with negotiation permission may offer ceasefire terms. Only the opposing cartel may accept; acceptance ends the war atomically with `resolution_type=ceasefire`. Authorized surrender ends the war and records the opposing winner. Events separate public payload from cartel-private payload.

## Validation evidence

The full-loop test covers claim, two support contributions, control transfer, alliance creation/invitation/acceptance, allied-PvP rejection, ultimatum, failed and successful reauthentication, phase activation, both parties joining, idempotent scoring operation, outsider score denial, ceasefire offer/acceptance, and final ended state.

