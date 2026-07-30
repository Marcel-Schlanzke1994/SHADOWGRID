# Phase 10D — Real estate and headquarters

Phase 10D adds persistent player-owned land, buildings, commercial space and
headquarters. Each Cologne district receives one deterministic object of every type.
Properties retain their player owner across season boundaries; seasonal company use and
leases do not.

## District indices and pricing

Every district has a versioned current index plus immutable daily snapshots. The server
derives price, rent and demand indices from property value, prosperity, employment,
safety, digital infrastructure, economic activity, cartel influence and applicable world
events. All factors use bounded integer basis points. The client displays server-returned
effective prices and never calculates an authoritative purchase or rent value.

Bootstrap creates exactly four properties per district and is safe to repeat. System
inventory starts as sale listings. A purchase locks the property, revalidates the listing
and transfers player cash to the system account. A resale instead transfers cash directly
between buyer and seller. Both paths append immutable transfer history and balanced ledger
transactions; ownership, identity and location cannot be rewritten through the API.

## Listings, leases and company use

Owners can publish idempotent sale or rent listings only while an object is unused. A
company lease requires ownership of the tenant company, posts the first indexed rent
immediately from the company account to the landlord and records immutable payment terms.
The worker settles each later period exactly once. Insufficient unreserved company cash
creates an abstract default payment without overdraft or partial transfer, releases the
property and adds a bounded company risk effect.

An unlisted owned object can be assigned directly to an owned company. Headquarters
properties can then be upgraded through a confirmed, balanced company-to-system ledger
transfer. Upgrade levels and costs are immutable historical improvements; the effective
cost uses the district price index and integer cents.

## Season boundary and verification

Season close snapshots every player-owned property, cancels active leases and clears
company use before seasonal companies are archived. Player ownership, transfers,
improvements, lease payments and financial history remain intact.

Migration `0015_real_estate` passes fresh upgrade, downgrade, re-upgrade and schema-drift
verification. Backend tests cover deterministic seeding, RBAC, idempotent purchase and
resale, immutable identity, balanced transfers, completed and defaulted leases, scheduler
retry safety, headquarters upgrades and season preservation. The responsive web UI covers
district indices, the property market, owned listings, confirmed purchases and leases,
company assignment, headquarters upgrades and lease history. Desktop and mobile
Playwright execute the complete flow with Axe.
