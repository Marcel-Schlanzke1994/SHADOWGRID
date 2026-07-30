# Phase 10A — Commercial contracts and tenders

Phase 10A adds server-authoritative supply and service contracts. A company publishes a
transparent tender with an integer-cent maximum price, duration, required capacity and
minimum reputation/compliance. Another company submits a binding price bid. Only the issuer
may award the tender, and the provider's available capacity must cover the reservation at
award time.

## Tender and award lifecycle

Tenders move from `open` to exactly one terminal state: `awarded`, `expired` or `cancelled`.
Bids store the price and the exact transparent integer score breakdown used when submitted.
The score combines price advantage, company reputation, compliance and quality with any
applicable versioned world-event modifier. The issuer can inspect every bid and choose the
winner; the server does not silently auto-award.

Awarding locks the tender, bid and involved companies, revalidates the submission deadline
and capacity, marks competing bids as lost, and creates one active contract. Idempotency
records make tender creation, bidding and award safe to retry. Contract commercial terms
and every settlement are immutable after creation.

## Settlement, breach and reputation

The worker settles each due period from the issuer company account to the provider company
account through one balanced double-entry transaction. A unique contract/period constraint
makes repeated worker runs harmless. Completing every period releases capacity and grants
the configured reputation reward once.

If the issuer cannot fund a due period, no account overdraw or partial hidden transfer is
created. The contract receives the abstract `payment_default` breach state, the failed
settlement is retained without a transaction, and configured reputation/investigation
effects are applied. This is an economic game status, not procedural wrongdoing guidance.
Tender expiry, settlement, completion and breach publish durable realtime records and audit
entries.

## Season boundary and verification

Season close snapshots active contracts before cancelling them, which releases derived
capacity reservations. Open tenders are cancelled with their timestamp. Awarded tenders,
all bids, contract settlements, ledger transactions and audit history remain intact.

Migration `0012_contracts` covers foreign keys, uniqueness and non-negative/check
constraints. Backend tests cover ownership/RBAC, idempotency, immutable terms, scoring,
capacity binding, balanced multi-period settlement, completion, abstract default, expiry,
repeated scheduling and season reset. The contract page covers loading/empty/error/success,
creation, bidding, issuer review, confirmed award, progress and breach states. Desktop and
mobile Playwright exercise the full flow with Axe.
