# Phase 7 — Intelligence and abstract strategic pressure

Phase 7 makes information uncertain, time-bound and tradable while keeping every
conflict mechanic fictional and non-procedural. The server resolves all outcomes and stores
the exact deterministic rolls for audit.

## Information reports

Reports use the information types `public`, `analyzed` and `covert`. Each immutable report
snapshot stores its target, category, statement, confidence in basis points, observation
time, abstract source category and expiry. The hidden accuracy state is one of `correct`,
`incomplete`, `outdated` or `intentionally_misleading`; normal players see confidence and
age, not the hidden truth state. An administrator can inspect the stored truth state and
operation rolls.

Creating an operation requires a known profile ID and an owned, active specialist with an
eligible role and sufficient energy. Cash and intelligence costs are deducted before the
roll is resolved in the same database transaction. Specialist competence, target
protection, active reliability effects and the attacker's cartel role affect the bounded
success and detection chances. The HMAC-derived seed and rolls are persisted with the
outcome. Duplicate keys return the original operation without charging twice.

Detection increases investigation pressure and sends the target a generic notification.
The notification never identifies the actor or exposes the private operation record.
Database-backed per-minute limits and target/category cooldowns prevent spam.

## Report market

An unexpired, tradable report can have one open offer. Purchasing an offer debits the buyer
and credits the seller through the synchronized balanced cash ledger. The buyer receives a
new immutable report row containing the original observation snapshot, confidence and
expiry. Purchased copies link to the source report ID but are not re-tradable in version 1.

## Strategic actions

The supported actions are deliberately abstract:

- delay a known cartel project;
- temporarily weaken public reputation;
- temporarily increase a known company's operating costs;
- temporarily reduce a profile's information reliability;
- temporarily burden a known specialist.

The action service validates that the target asset belongs to the selected target profile.
It reserves costs before resolution, stores deterministic rolls and creates a bounded,
expiring `StrategicEffect` only for success or partial success. Economy ticks include active
company cost effects in immutable report modifiers. Cartel project deadline validation,
PvP target reputation and later intelligence operations consume their corresponding active
effects. No action contains or simulates real hacking, sabotage, violence or evasion
methods.

## API and verification

Canonical endpoints are under `/api/v1/intelligence/*`, `/api/v1/strategic-actions*` and
administrator-only `/api/v1/admin/intelligence/*`. The React page covers loading, empty,
error and success states, explicit financial purchase confirmation, keyboard-labelled forms
and uncertainty indicators.

Migration `0009_intelligence_pvp` is reversible and drift-free. Backend tests cover success,
partial success, failure, detection, misleading and expired reports, duplicate execution,
cooldowns, insufficient resources, ownership, immutable copies, trade settlement and
strategic effects. Desktop and mobile Playwright exercise the end-to-end flow with Axe.
