# Phase 10C — Company bonds

Phase 10C lets companies issue fixed-face-value, fixed-coupon bonds without granting
ownership or voting rights. An issue defines an immutable symbol, face value, unit supply,
coupon rate and term. Total principal is bounded by company enterprise value and the
configured issuance ceiling.

## Offering, reservations and holdings

Subscriptions transfer player cash to the company through the balanced account ledger and
append an immutable bond-ownership ledger entry. While an issue remains in offering, all
subscription proceeds are reserved on the company account and cannot be spent. This makes
partial offerings safe. The issuer can activate after at least one subscription; a fully
subscribed issue activates automatically, and the worker activates a subscribed issue when
its offering window ends. Empty expired offerings cancel.

Activation releases only the reserved sold principal and adds that principal to the company
debt read model. Aggregate holdings retain one row per player/issue while immutable
subscription and bond-ledger rows provide the ownership history. No bond grants company
equity.

## Coupons, redemption and default

Coupon cents per unit use ceiling integer arithmetic and never use floating point. Each due
period precomputes the complete obligation across all current holders. If sufficient
unreserved issuer cash exists, every holder receives a ledger-backed coupon. At maturity,
the final coupon and face-value redemption are settled atomically, holdings receive
negative redemption ledger entries, company principal debt is removed and the issue becomes
repaid. Unique issue/period/holder/payment-type constraints make retries harmless.

If the issuer cannot cover the whole due period, no holder is paid partially. Immutable
default settlements are created without transactions, the issue receives an abstract
`coupon_default` or `maturity_default`, and configured reputation/investigation effects are
applied once. Lifecycle actions are audited and publish durable realtime records.

## Season boundary and verification

Season close snapshots every live issue. Reserved partial-offering proceeds are released
only for a full principal refund. Active issues are redeemed early when the issuer can cover
all principal; otherwise they retain an abstract season-close default. Holdings, financial
transactions, settlements and ownership-ledger history are never deleted.

Migration `0014_bonds` passes fresh upgrade, downgrade, re-upgrade and drift verification.
Tests cover multi-investor reservations, RBAC, idempotency, activation, holdings,
double-entry subscriptions, exact coupons, maturity redemption, default, offering expiry,
repeated scheduling and season close. The responsive web UI covers emission, confirmed
subscription, confirmed activation, offering progress, holdings and default states.
Desktop and mobile Playwright run the full acceptance flow with Axe.
