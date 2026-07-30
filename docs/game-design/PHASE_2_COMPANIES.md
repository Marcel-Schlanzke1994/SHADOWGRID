# Phase 2: companies and investments

Phase 2 introduces the first complete economic loop: a player can found a private company,
inspect its account and metrics, and make traceable investments.

## Founding

- Supported industries are gastronomy, logistics and technology.
- A company name is normalized with Unicode NFKC, whitespace folding and case folding. It
  is unique within a world/season.
- The founding price is configured by `COMPANY_FOUNDING_COST_CENTS`; the default is
  2,000,000 cents (€20,000.00).
- The player's cash balance and financial account are locked. The founding amount moves
  atomically from the player account to a new company account.
- The founder receives exactly 10,000 ownership basis points (100.00%).
- The command, transfer, ownership, initial metric snapshot and audit record commit in one
  database transaction.

`POST /api/v1/companies` requires an `Idempotency-Key`. Repeating a successful command
returns the original company and does not transfer money or create ownership twice.

## Double-entry invariant

Financial transfers use `accounts`, `ledger_transactions` and
`account_ledger_entries`. Every transfer contains one negative source entry and one
positive target entry of the same integer-cent amount. The application verifies that the
sum of entries is zero before commit. Player and company accounts may not become negative;
the system counter-account is allowed to carry the signed offset for grants and sinks.

The existing resource ledger remains as a compatibility read model. Cash mutations now
synchronize that balance with the double-entry account in the same transaction.

## Investments

Investment effects are data-driven in `COMPANY_INVESTMENTS`:

| Investment | Cost | Effect |
| --- | ---: | ---: |
| Capacity | €5,000.00 | +500 capacity points |
| Quality | €7,500.00 | +400 quality points |
| Innovation | €10,000.00 | +600 innovation basis points |
| Compliance | €8,000.00 | +500 compliance basis points |

Metrics are capped at 10,000. An investment transfers cash from the owning player's
account to the company account, changes only the configured metric, increments the company
version and appends an immutable investment and metric snapshot. Server-side ownership is
checked under a row lock; a non-owner receives `company.not_owner`.

## Contracts and UI states

- `GET /api/v1/companies/config`
- `GET /api/v1/companies`
- `POST /api/v1/companies`
- `GET /api/v1/companies/{company_id}`
- `POST /api/v1/companies/{company_id}/investments`
- `GET /api/v1/companies/{company_id}/ownership`

The web client reads all costs from the server configuration endpoint. Founding and
investments require an accessible confirmation dialog that displays the exact cost before
submission. Loading, empty, error and success states are visible, and successful mutations
invalidate both the list and detail queries.
