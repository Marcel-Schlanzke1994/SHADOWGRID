# Phase 10B — Company loans

Phase 10B adds fixed-rate company loans without bypassing the existing financial ledger.
An owner submits an application with principal, term, business purpose and an abstract
collateral score. The server captures the company's current enterprise value, existing
outstanding principal, reputation, compliance, risk and investigation pressure in an
immutable underwriting snapshot.

## Offer and acceptance

Underwriting computes an integer-basis-point rate within configured hard bounds. Available
credit is limited by company value, the global principal ceiling and active outstanding
principal. An ineligible request receives a stable abstract rejection reason; no money or
loan is created. Eligible requests receive an expiring offer with fixed total repayment and
scheduled installment.

Only an owner may accept an offer. Acceptance revalidates ownership and available lending
capacity, locks the company and world, then transfers principal from the system lender to
the company account through one balanced transaction. The company debt read model increases
by principal in the same transaction. Application inputs, quote terms and accepted loan
terms are immutable, while their lifecycle states remain explicit.

## Installments and default

Principal and total interest are divided deterministically across all periods. Remainder
cents are assigned to the earliest periods, so every successful payment sums exactly to
the contractual principal and interest. Each contract/period pair is unique and immutable.
The worker transfers each due installment from company to system account through the
double-entry ledger, decreases company debt by only the principal component and marks the
loan repaid exactly once.

Insufficient available company cash never overdraws the account and never creates a partial
transfer. It creates one immutable failed payment and the abstract
`installment_default` status, then applies configured reputation and investigation effects.
Offer expiry, payment, repayment and default are audited; loan lifecycle changes publish
durable realtime events.

## Season boundary and verification

Season close snapshots active loan terms and remaining principal/interest, then cancels the
seasonal obligation alongside the archived company. Applications, payments, disbursement
and installment transactions, audit records and the archived debt snapshot remain.

Migration `0013_loans` passes a fresh upgrade, downgrade, re-upgrade and drift check. Tests
cover RBAC, risk quotes, rejection, idempotency, balanced payout, exact installment sums,
immutable terms, complete repayment, abstract default, expired offers, repeated worker runs
and season archival. The responsive finance UI covers loading/empty/error/success, offer
review, confirmed acceptance, repayment progress and default state. Desktop and mobile
Playwright run the acceptance flow with Axe.
