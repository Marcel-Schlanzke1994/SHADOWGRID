# SHADOWGRID engagement implementation

Status: verified on 2026-08-01

This document is the implementation and acceptance map for
`docs/SHADOWGRID – Engagement Masterplan.md`. The game-design specification,
architecture document, migrations and API schemas remain authoritative as defined by
`AGENTS.md`.

## Safety interpretation

Two sentences in the supplied masterplan omit a negation and conflict with every
surrounding requirement. SHADOWGRID therefore treats the following as prohibited:

- optimizing for uninterrupted play, fear of missing out, guilt, paid random rewards,
  opaque prices, automatic follow-on rounds, punishment for pauses or manipulated losses;
- doctrines granting hidden profit bonuses, matchmaking advantages, exclusive mandatory
  mechanics or irreversible choices.

This is the smallest interpretation consistent with the masterplan's stated autonomy,
fairness and wellbeing goals.

## Architectural boundaries

- Gameplay domains publish immutable, idempotent engagement events inside their existing
  database transaction.
- Engagement projections may unlock goals, mastery, narrative, identity and summaries.
- Engagement code never writes cash, ownership, securities or economic outcomes.
- Reward types are knowledge, chronicle, mastery or cosmetic identity. Any future economic
  reward requires a separate ledger-backed game-design decision.
- The command center returns at most one urgent, one strategic and one discoverable entry.
- Pauses never reset progress, expose an inactivity badge or penalize a cartel.
- Analytics remain disabled by default. Only aggregate daily metrics may be enabled after
  the privacy gate described in `docs/PRIVACY.md` and `docs/DATA_RETENTION_MATRIX.md`.

## Delivery matrix

| Masterplan phase | Repository delivery                                                                                                                                                                                               | Verification                                                                         |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| A – foundation   | Personal goal windows and choices, open plans, server-owned sessions and summaries, return briefings, notification preferences, command-center priorities and guardrails                                          | Domain/API tests, migration cycle, web/mobile flows and accessibility checks         |
| B – competence   | Changeable doctrines, adaptive help, eleven mastery tracks, diverse evidence and explainable outcome reports                                                                                                      | Idempotency, no-repeat farming and doctrine-neutral economy tests                    |
| C – social       | Existing ledger-safe cartel projects plus milestones, functional roles, asynchronous proposals, consensual mentoring and private pause state                                                                      | Ownership/role/concurrency tests and no-recruitment-reward tests                     |
| D – narrative    | Company/world chronicles, recurring actors, event dossiers, deterministic clues, archived stories and consequences                                                                                                | Immutable history and guaranteed-discovery tests                                     |
| E – identity     | Titles, emblems, HQ cosmetics, profile identity, collection points and duplicate conversion                                                                                                                       | Account persistence and no-pay-to-win tests                                          |
| F – seasons      | Six-part dramatic presentation over the canonical six technical phases, flexible season goals, parallel rankings and cosmetic legacy                                                                              | Season transition/archive/regression tests                                           |
| G – return       | Doctrine-aware recommendations, adjustable information density, catch-up goals and pause-safe re-entry                                                                                                            | Simulated 7/14/30-day return tests                                                   |
| H – rollout      | Internal/5/20/50/100-percent rollout states gated by economic, technical, accessibility, voluntary-return and explicit wellbeing evidence; immutable privacy-safe daily aggregates with five-response suppression | Admin authorization, aggregate-schema, threshold and failing-guardrail rollout tests |

## Definition of done

Migrations, deterministic seeds, OpenAPI/client types, English and German catalogues, web
and mobile states, lifecycle handling, privacy/retention records and balance evidence are
implemented. Verification evidence:

- migrations `0018` through `0023` passed fresh upgrade, downgrade and re-upgrade cycles;
- the local database is at `0023_engagement_event_semantics`;
- the final full repository gate passed with 150 backend, 12 web, 9 mobile and 4 i18n tests;
- the final combined engagement regression passed all 21 tests, including concurrent
  initialization and semantic event idempotency;
- repository lint, strict type checks, formatting, secret and security scans passed;
- the Playwright accessibility matrix passed in mobile and Chromium projects, including
  `/engagement` and `/legacy`.
