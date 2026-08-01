# Phase 9 — Seasons, scoring and non-destructive reset

Phase 9 supplies the complete long-term cycle: setup, early, mid, late, scoring and archived.
Every season is created from a versioned template whose goals, duration, phase weights,
starting cash and scoring-category list are copied into the concrete season.

## Phase lifecycle

The season stores an explicit UTC schedule for every phase. Integer basis-point weights sum
to exactly 10,000 and produce deterministic phase boundaries. The minute worker advances
the phase and publishes a durable event only when the calculated phase changes. Repeating
the same scheduler instant changes nothing. A local administrator can shorten the total
schedule, simulate a future instant, explicitly close the season and create the next season
from an enabled template.

The six states are `setup`, `early`, `mid`, `late`, `scoring` and `archived`. Closing is
idempotent: an already archived season returns the original counts without adding scores,
rewards, archive rows or reset entries.

## Immutable scoring

Final evaluation captures the required twelve categories:

- wealthiest player;
- most valuable portfolio;
- entrepreneur value;
- largest company;
- strongest cartel;
- largest public company;
- dividend yield;
- district control;
- diplomacy;
- information network;
- stability;
- crisis recovery.

All scores are non-negative integers with their input metrics stored in an immutable
snapshot. Candidates sort by score descending, then name and UUID for deterministic display.
Equal numeric scores receive the same competition rank (`1, 1, 3`) and an explicit tie
record containing the tie size and display-order rule. The immutable Hall of Fame retains
every rank up to three; ties at ranks one through three remain visible.

Each rank-one owner receives permanent account-level achievement, title and cosmetic
records. A company reward belongs to its founder; cartel rewards belong to its active
members at snapshot time. These records survive every season reset.

## Archive and reset boundary

Before reset, the server writes immutable snapshots of every seasonal company, exchange
listing and holding distribution, city-sector market and active cartel. Companies become
archived, listings become delisted, share classes become non-tradable, open orders release
their reservations, cartels dissolve, active memberships leave and running cartel projects
cancel. Market parameters return to the canonical template.

No account, financial transaction, ledger entry, trade, share-ledger record, scoring
snapshot, Hall-of-Fame entry or reward is deleted. Player seasonal resources return to the
template values through append-only resource entries; cash changes use balanced transfers
against the system account. Non-financial seasonal pressure and stability fields return to
their initial values. The next season receives a new number and cannot alter the archived
records.

## API, UI and verification

Player routes are under `/api/v1/seasons*`, `/api/v1/hall-of-fame` and
`/api/v1/account/rewards/me`. Administrator routes are under `/api/v1/admin/seasons*`.
The rankings UI shows phase, remaining time, goals, every scoring category, explicit ties,
Hall of Fame and permanent rewards. The admin UI covers shortening, simulation, confirmed
close and template-based creation.

Migration `0011_seasons` passes fresh upgrade, downgrade and drift verification. Tests cover
every phase, all final categories, ties, repeated closure, immutable results, archive
boundaries, reward persistence, financial-history preservation, repeated scheduling, RBAC
and creation of the next season. Desktop and mobile Playwright exercise player and admin
flows with Axe.
