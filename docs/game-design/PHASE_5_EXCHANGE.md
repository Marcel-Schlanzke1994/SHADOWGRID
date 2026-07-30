# Phase 5: IPO and stock exchange

Phase 5 turns eligible private companies into public companies with a fixed integer share
supply. The API owns every eligibility decision, reservation, match, transfer and dividend.
The web client displays authoritative values and submits intent; it never calculates a fill
or changes cash, holdings or ownership.

## IPO eligibility and issuance

The following settings are configurable and validated as bounded integers:

- minimum enterprise value;
- number of required audited, profitable economy periods;
- minimum compliance and employee count;
- maximum investigation pressure;
- listing fee.

Only the founder-controlled company can request an IPO. Eligibility reads the most recent
immutable company-economy reports and the free balance of the company account. The listing
fee moves through the balanced account ledger. A successful IPO atomically creates one
common share class, founder and issuer holdings, two immutable issuance-ledger entries, and
the issuer's opening sell order.

`ShareClass.total_shares` and the issuance fields on the listing are immutable after
creation. The sum of all `ShareHolding.quantity` rows must equal that total after issuance
and every trade. Offered but unsold shares remain in the issuer holding and are reserved by
the IPO order. Profile ownership basis points are a derived compatibility projection;
issuer treasury shares remain explicit in the authoritative holdings rather than being
silently attributed to a player.

The initial price is integer cents:

`enterprise_value_cents // total_shares`

An allocation that would produce a zero-cent price, no retained founder stake or an
offering equal to the entire supply is rejected.

## Orders, matching and settlement

Version 1 supports market and limit buy/sell orders. Limit orders must remain within the
configured deviation from the latest price. Orders may have a timezone-aware expiry.

Before an order enters the book:

- a buy reserves its maximum executable cash;
- a sell reserves available shares;
- an unavailable balance or holding is rejected;
- the profile/listing/idempotency tuple prevents duplicate submission.

The matching engine uses best price followed by oldest creation time and stable ID. It
supports full and partial fills and excludes orders owned by the same profile. A market
order executes available liquidity and cancels any unfilled remainder. Open limit
remainders stay reserved until execution, explicit cancellation or worker-driven expiry.

Each fill runs in one database transaction:

1. lock the listing, share class, matching orders, accounts and holdings;
2. recheck cash and share reservations;
3. transfer cash through a balanced ledger transaction;
4. transfer the fixed shares and append paired immutable share-ledger entries;
5. append the immutable trade and price snapshot;
6. update order remainders, listing price and derived ownership;
7. create buyer and seller notifications;
8. verify the total-share invariant before commit.

SQLite serializes exchange commands with a process lock for local tests. PostgreSQL adds a
world exchange lock, resource row locks and unique constraints for cross-request safety.
The API rate-limits order creation
and cancellation per profile. The ARQ worker expires due orders every minute and releases
their reservations idempotently.

## Dividends

The founder is the authorized company leader in the version-1 governance model. A dividend
declaration locks the listing, company, share class and all eligible profile holdings,
captures their quantities at one UTC snapshot, verifies that the company can fund the full
distribution, and pays every entitlement in one transaction.

Issuer treasury shares are not dividend recipients. Each recipient gets one immutable
entitlement and one balanced company-to-profile ledger transfer. The declaration's
idempotency key and database constraints prevent duplicate payment. A failure in any
recipient transfer rolls back the declaration and every earlier payment.

## API and web contracts

- `GET /api/v1/exchange/config`
- `GET /api/v1/companies/{company_id}/ipo-eligibility`
- `POST /api/v1/companies/{company_id}/ipo`
- `GET /api/v1/exchange/listings`
- `GET /api/v1/exchange/listings/{listing_id}`
- `GET /api/v1/exchange/listings/{listing_id}/order-book`
- `GET /api/v1/exchange/listings/{listing_id}/trades`
- `GET /api/v1/exchange/listings/{listing_id}/prices`
- `GET /api/v1/exchange/listings/{listing_id}/reports`
- `GET /api/v1/exchange/listings/{listing_id}/shareholders`
- `POST /api/v1/exchange/orders`
- `DELETE /api/v1/exchange/orders/{order_id}`
- `GET /api/v1/exchange/orders/me`
- `GET /api/v1/exchange/portfolio`
- `GET /api/v1/exchange/listings/{listing_id}/dividends`
- `POST /api/v1/companies/{company_id}/dividends`

The localized web flow provides listing overview/detail, audited reports, accessible price
chart, order book, confirmed buy/sell ticket, own-order cancellation, portfolio, dividend
history, main shareholders and an eligibility-aware IPO form. Loading, empty, error and
success states are explicit. The deterministic demo seed contains three listings, primary
and secondary trades, price snapshots, open liquidity and multiple portfolio holders.

Backend tests cover full and partial fills, price-time priority, concurrent buyers and
sellers, cash/share reservation, cancellation, expiry, insufficient resources, self-trade
prevention, rounding, duplicate requests, injected rollback, dividend snapshots, ledger
balance and supply invariance. Desktop and mobile Playwright cover IPO, order, cancellation
and dividend confirmation with serious/critical Axe checks.
