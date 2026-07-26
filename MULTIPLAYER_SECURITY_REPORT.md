# Multiplayer Security Report

Status: implementation review and local test evidence, 2026-07-19.

## Security properties

- Server authority: no client-provided result, balance, probability, score, ownership, or phase is trusted.
- Tenant scope: authenticated user → active profile → world/city/cartel/alliance/war membership is resolved on the server.
- Least privilege: cartel roles map to explicit permission strings; private war rooms and reports require party membership.
- Critical reauthentication: war declaration and surrender verify the current password hash.
- Exactly-once economy: ledger uniqueness, idempotency keys, transactions, and row locks protect resource movement.
- Auditability: launch, defense, territory, war, alliance, moderation and settlement actions create audit/event records.

## Threats and controls

| Threat | Control |
|---|---|
| Replay/double submission | Scoped idempotency and unique constraints |
| Concurrent purchase/double settlement | Offer row lock, one-trade constraint, atomic rollback |
| Cross-player report access | Report owner check; returns 404 |
| Cross-war private access | Party membership plus role permission |
| New-player farming | Protection, recovery lock, target cap, cooldown, rising cost/falling reward |
| Alliance betrayal through direct launch | Shared-alliance and treaty launch blocks |
| Exact strength/defense reconnaissance | Public bands and perspective-specific reports |
| Chat spam | Per-profile minute limit and risk event |
| Harassment/doxxing/real threats | Held moderation state, placeholder storage, automatic report; original matched text is not retained |
| Block evasion in direct messages | Bidirectional block check before persistence |
| Market laundering/outliers | City reference bounds, protected-player tighter bounds, daily transfer limit and risk events |
| WebSocket token leakage | Token is sent in the authenticated first frame, never in URL/query string |

## Realtime privacy

Realtime events are stored with `world_id` and optional `profile_id`. The WebSocket authenticates both refresh session and profile/world before polling. It receives only world broadcasts or events targeted to that profile. Events are short-lived hints; sensitive state remains behind REST authorization.

## Communication safety boundary

The product does not retain the original body when automated real-threat/personal-address markers match. The persisted chat/direct-message body becomes a neutral moderation placeholder and the item is hidden from normal message lists. Manual reports retain only the reporter's bounded description and identifiers.

All gameplay remains fictional and non-procedural. No API or report provides real-world criminal instructions, real targets, or operational harm guidance.

## Verified cases

- Protected target cannot be launched against.
- Blocked profiles cannot exchange direct messages.
- Held message is absent from the visible channel and creates a risk-90 moderation report.
- Attacker cannot read defender PvP report.
- Outsider cannot read war score/private access.
- Wrong current password cannot declare war.
- Shared alliance blocks PvP.
- Two simultaneous buyers settle one offer exactly once.

## Operational follow-up

Production monitoring should alert on high 409/429 rates, repeated idempotency conflicts, moderation risk ≥90, abnormal reciprocal market volume, phase-transition failures, and realtime outbox backlog. Secrets must remain in Railway variables; they are never committed or included in reports.

