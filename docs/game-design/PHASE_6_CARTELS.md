# Phase 6 — Cartels and district influence

This document fixes the version-1 rules implemented for roadmap phase 6. The broader
functional source remains `SHADOWGRID_SPEC.md`.

## Membership and governance

- `Organization` is the existing persistence name; the versioned public contract calls the
  aggregate a cartel and uses `/api/v1/cartels`.
- A partial unique database index permits exactly one active cartel membership per player.
  Left and removed memberships remain as historical rows.
- New cartels receive one `leader`. The assignable phase-6 roles are `finance_lead`,
  `diplomat`, `strategist`, `intelligence_officer` and `member`. Older role names remain
  readable so existing PvP/alliance records are not rewritten.
- Joining requires an unexpired invitation for the authenticated account in the same world.
  Creation, invitations, joining, leaving, role changes, leadership transfer and dissolution
  require idempotency keys.
- Leadership transfer locks the world and both membership rows, then demotes the old leader
  and promotes the new leader in one transaction.
- Dissolution is a soft state change. It requires exactly one active member, an empty treasury,
  no active project and no pending expense. Financial, contribution and audit history is never
  deleted.

## Treasury and approvals

- Every cartel owns a EUR `Account` in the balanced financial ledger. Existing decimal
  treasury values are migrated through explicit balanced opening transactions.
- A deposit transfers integer cents from the member's synchronized player account to the
  cartel account. The same idempotency key cannot debit twice.
- Leaders, deputies and finance leads may request expenses up to the configured single-spend
  limit. Requests above the approval threshold remain pending.
- Approval-required expenses must be approved by a different authorized member. Approval
  transfers funds from the locked cartel account to the system account and writes two balanced
  ledger entries atomically.
- Expense request contracts and financial ledger rows are immutable. Resolution changes only
  approval/status fields.

Default local balancing values:

| Rule | Value |
| --- | ---: |
| Cartel creation cost | €10,000.00 |
| Approval threshold | €2,500.00 |
| Single-spend limit | €25,000.00 |

## Projects and district control

The first project templates are logistics hub, technology center, media campaign, compliance
network and trade center. A project has a district, contribution window, fixed cash/influence/
intelligence requirements and an influence reward.

- Cash contributions use integer cents and a balanced player-to-system transaction.
- Influence and intelligence contributions use the append-only resource ledger.
- The project row is locked before every contribution. A contribution cannot exceed the
  remaining requirement and is unique by player/idempotency key.
- Reaching every requirement completes the project exactly once and awards integer cartel
  influence for the configured category.
- Cartel/district/category influence is non-negative and unique. The relevant control point is
  recalculated from authoritative totals in the same transaction.
- A district/control point is controlled when the leading cartel has at least 100 points and a
  lead of at least 20 points. It is contested when the threshold is met without that margin;
  otherwise it is neutral. Both values are configurable.

## Seasonal ranking

The current cartel ranking is deterministic and scoped to the authenticated world/season:

`treasury cents / 10,000 + active members × 100 + completed projects × 250 + influence × 10`

The API returns all components so clients never need to derive hidden game state.

## Verification

- Migration `0008_cartels` supports fresh upgrade, full downgrade/re-upgrade and zero drift.
- `test_cartels.py` covers authorization, active-membership uniqueness, invitation and mutation
  idempotency, transactional leadership transfer, balanced deposits/expenses, independent
  approval, concurrent project contributions, immutable contracts and control invariants.
- `cartel-flow.spec.ts` covers the leader treasury/project/approval flow and rejects serious or
  critical Axe findings.
