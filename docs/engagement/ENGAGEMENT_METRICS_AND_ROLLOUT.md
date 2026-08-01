# Engagement metrics and staged rollout

Status: implemented, disabled by default

This document defines the privacy and release gate for phase H of
`SHADOWGRID – Engagement Masterplan.md`. It does not authorize production analytics.

## Collection boundary

SHADOWGRID installs no analytics SDK and sends no engagement data to a third party. An
administrator may explicitly generate one immutable daily aggregate through
`POST /api/v1/engagement/admin/metrics/daily`. The persisted row contains counts and
basis-point rates for return milestones, goal completion, decision diversity, season and
social participation, return paths, natural session endings, story progress and collection
completion.

The table deliberately has no player, user, device or advertising identifier and no chat
or notification content. Satisfaction and fairness may enter only as already aggregated
values with a response count. Values are suppressed below five responses. The legal
retention duration remains a launch gate in `docs/DATA_RETENTION_MATRIX.md`.

## Wellbeing thresholds

A rollout evaluation fails when any of the following is true:

- very-long-session growth exceeds 1,000 basis points;
- push-disable growth exceeds 500 basis points;
- any goal-obligation report exists;
- fear-motivated returns exceed 5,000 basis points;
- any cartel absence-pressure report exists;
- post-session exhaustion exceeds 5,000 basis points.

Passing self-reported labels cannot override these signals. Economic simulation, zero
ledger imbalance, non-negative balances, technical stability, accessibility evidence and
voluntary-return evidence must all pass in the same evaluation.

## Rollout order

The server enforces this exact sequence per feature:

1. internal cohort (`0` basis points);
2. 5 percent (`500` basis points);
3. 20 percent (`2,000` basis points);
4. 50 percent (`5,000` basis points);
5. full activation (`10,000` basis points).

A stage cannot be skipped. Every advancement references the latest passing immutable
guardrail evaluation. Failed or insufficient evidence blocks advancement.
