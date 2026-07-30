from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from httpx import Response
from shadowgrid import exchange
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.economy import ensure_city_sector_markets, run_economy_tick
from shadowgrid.exchange import expire_due_orders, place_order
from shadowgrid.finance import transaction_balance_cents
from shadowgrid.models import (
    Account,
    CompanyEconomyReport,
    CompanyOwnership,
    District,
    DividendDeclaration,
    DividendEntitlement,
    ExchangeListing,
    ExchangeOrder,
    ExchangeTrade,
    LedgerTransaction,
    Notification,
    PlayerProfile,
    PriceSnapshot,
    ResourceBalance,
    ShareClass,
    ShareHolding,
    ShareLedgerEntry,
    User,
    World,
)
from shadowgrid.security import hash_password
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def _create_company(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Exchange Logistics",
    key: str = "exchange-company",
) -> dict[str, object]:
    district = client.get("/api/v1/districts", headers=headers).json()[0]
    response = client.post(
        "/api/v1/companies",
        headers={**headers, "Idempotency-Key": key},
        json={
            "name": name,
            "industry": "logistics",
            "district_id": district["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


def _join_additional_player(
    client: TestClient,
    *,
    suffix: str,
) -> tuple[dict[str, str], dict[str, object]]:
    email = f"exchange-{suffix}@example.com"
    with SessionLocal() as db:
        user = User(
            email=email,
            password_hash=hash_password("StrongPassword123"),
            display_name=f"Exchange {suffix}",
            email_verified=True,
        )
        db.add(user)
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    with SessionLocal() as db:
        world = db.scalar(select(World))
        district = db.scalar(select(District))
        assert world is not None and district is not None
        world_id = world.id
        district_id = district.id
    joined = client.post(
        f"/api/v1/worlds/{world_id}/join",
        headers={**headers, "Idempotency-Key": f"exchange-join-{suffix}"},
        json={
            "codename": f"Exchange {suffix}",
            "archetype": "business_consortium",
            "home_district_id": district_id,
        },
    )
    assert joined.status_code == 200
    return headers, joined.json()


def _make_company_ipo_eligible(world_id: str) -> None:
    with SessionLocal() as db:
        markets = ensure_city_sector_markets(db, world_id)
        logistics = next(item for item in markets if item.industry == "logistics")
        logistics.demand_units = 10_000
        db.commit()
    base = datetime.now(UTC).replace(minute=0, second=0, microsecond=0) - timedelta(hours=8)
    for offset in range(3):
        with SessionLocal() as db:
            run_economy_tick(db, world_id, at=base + timedelta(hours=offset))


def _prepare_listing(
    client: TestClient,
    headers: dict[str, str],
    profile: dict[str, object],
    *,
    total_shares: int = 10_000,
    offered_shares: int = 2_000,
    symbol: str = "GRID",
) -> tuple[dict[str, object], dict[str, object]]:
    company = _create_company(client, headers)
    _make_company_ipo_eligible(str(profile["world_id"]))
    response = client.post(
        f"/api/v1/companies/{company['id']}/ipo",
        headers={**headers, "Idempotency-Key": f"ipo-{symbol.lower()}"},
        json={
            "symbol": symbol.lower(),
            "total_shares": total_shares,
            "offered_shares": offered_shares,
        },
    )
    assert response.status_code == 201, response.text
    return company, response.json()


def _post_order(
    client: TestClient,
    headers: dict[str, str],
    *,
    listing_id: str,
    key: str,
    side: str,
    order_type: str,
    quantity: int,
    limit_price_cents: int | None = None,
    expires_at: datetime | None = None,
) -> Response:
    return client.post(
        "/api/v1/exchange/orders",
        headers={**headers, "Idempotency-Key": key},
        json={
            "listing_id": listing_id,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "limit_price_cents": limit_price_cents,
            "expires_at": expires_at.isoformat() if expires_at is not None else None,
        },
    )


def _supply(db: Session, share_class_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(ShareHolding.quantity), 0)).where(
                ShareHolding.share_class_id == share_class_id
            )
        )
        or 0
    )


def test_ipo_contract_eligibility_rounding_idempotency_and_supply(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    company = _create_company(client, auth_headers)
    before = client.get(
        f"/api/v1/companies/{company['id']}/ipo-eligibility",
        headers=auth_headers,
    )
    assert before.status_code == 200
    assert before.json()["eligible"] is False
    assert set(before.json()["reasons"]) >= {"audited_reports", "profitable_periods"}

    _make_company_ipo_eligible(str(joined_profile["world_id"]))
    eligibility = client.get(
        f"/api/v1/companies/{company['id']}/ipo-eligibility",
        headers=auth_headers,
    )
    assert eligibility.status_code == 200
    assert eligibility.json()["eligible"] is True
    assert eligibility.json()["metrics"]["profitable_periods"] == 3

    config = client.get("/api/v1/exchange/config", headers=auth_headers)
    assert config.status_code == 200
    assert config.json()["profitable_periods"] == 3
    assert config.json()["order_rate_limit_per_minute"] == 60

    headers = {**auth_headers, "Idempotency-Key": "ipo-rounding"}
    payload = {"symbol": "r99", "total_shares": 99_999, "offered_shares": 20_000}
    first = client.post(
        f"/api/v1/companies/{company['id']}/ipo",
        headers=headers,
        json=payload,
    )
    repeated = client.post(
        f"/api/v1/companies/{company['id']}/ipo",
        headers=headers,
        json=payload,
    )
    assert first.status_code == repeated.status_code == 201
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["symbol"] == "R99"
    assert first.json()["initial_price_cents"] == (first.json()["enterprise_value_cents"] // 99_999)

    listing_id = first.json()["id"]
    with SessionLocal() as db:
        listing = db.get(ExchangeListing, listing_id)
        share_class = db.scalar(select(ShareClass).where(ShareClass.listing_id == listing_id))
        assert listing is not None and share_class is not None
        holdings = list(
            db.scalars(select(ShareHolding).where(ShareHolding.share_class_id == share_class.id))
        )
        assert sum(item.quantity for item in holdings) == 99_999
        assert sum(item.reserved_quantity for item in holdings) == 20_000
        assert _supply(db, share_class.id) == share_class.total_shares
        issuance = list(
            db.scalars(
                select(ShareLedgerEntry).where(
                    ShareLedgerEntry.share_class_id == share_class.id,
                    ShareLedgerEntry.reason == "ipo_issuance",
                )
            )
        )
        assert sum(item.quantity_delta for item in issuance) == 99_999
        ownership = list(
            db.scalars(select(CompanyOwnership).where(CompanyOwnership.company_id == company["id"]))
        )
        profile_shares = sum(item.quantity for item in holdings if item.owner_type == "profile")
        assert sum(item.ownership_bps for item in ownership) == (
            profile_shares * 10_000 // share_class.total_shares
        )
        assert transaction_balance_cents(db, listing.fee_transaction_id) == 0
        share_class.total_shares += 1
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
        listing = db.get(ExchangeListing, listing_id)
        assert listing is not None
        listing.total_shares += 1
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()

    listing_response = client.get(
        f"/api/v1/exchange/listings/{listing_id}",
        headers=auth_headers,
    )
    reports = client.get(
        f"/api/v1/exchange/listings/{listing_id}/reports",
        headers=auth_headers,
    )
    assert listing_response.status_code == 200
    assert len(reports.json()) == 3
    assert all(item["profit_cents"] > 0 for item in reports.json())

    duplicate_ipo = client.post(
        f"/api/v1/companies/{company['id']}/ipo",
        headers={**auth_headers, "Idempotency-Key": "ipo-second-attempt"},
        json={"symbol": "OTHER", "total_shares": 10_000, "offered_shares": 2_000},
    )
    assert duplicate_ipo.status_code == 409
    assert duplicate_ipo.json()["error"]["code"] == "exchange.ipo_ineligible"


def test_full_and_partial_fills_reservations_cancellation_expiry_and_guards(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, listing = _prepare_listing(client, auth_headers, joined_profile)
    buyer_headers, buyer = _join_additional_player(client, suffix="buyer")
    price = int(listing["initial_price_cents"])
    listing_id = str(listing["id"])

    full = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="exchange-full-fill",
        side="buy",
        order_type="limit",
        quantity=500,
        limit_price_cents=price,
    )
    repeated = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="exchange-full-fill",
        side="buy",
        order_type="limit",
        quantity=500,
        limit_price_cents=price,
    )
    assert full.status_code == repeated.status_code == 201
    assert full.json()["id"] == repeated.json()["id"]
    assert full.json()["status"] == "filled"

    partial = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="exchange-partial-fill",
        side="buy",
        order_type="limit",
        quantity=2_000,
        limit_price_cents=price,
    )
    assert partial.status_code == 201
    assert partial.json()["status"] == "partially_filled"
    assert partial.json()["remaining_quantity"] == 500
    assert partial.json()["reserved_cash_cents"] == 500 * price

    cancelled = client.delete(
        f"/api/v1/exchange/orders/{partial.json()['id']}",
        headers={**buyer_headers, "Idempotency-Key": "exchange-cancel-partial"},
    )
    cancelled_again = client.delete(
        f"/api/v1/exchange/orders/{partial.json()['id']}",
        headers={**buyer_headers, "Idempotency-Key": "exchange-cancel-partial"},
    )
    assert cancelled.status_code == cancelled_again.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["reserved_cash_cents"] == 0

    insufficient_cash = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="exchange-insufficient-cash",
        side="buy",
        order_type="limit",
        quantity=100_000_000,
        limit_price_cents=price,
    )
    assert insufficient_cash.status_code == 409
    assert insufficient_cash.json()["error"]["code"] == "resource.insufficient"

    insufficient_shares = _post_order(
        client,
        auth_headers,
        listing_id=listing_id,
        key="exchange-insufficient-shares",
        side="sell",
        order_type="limit",
        quantity=8_001,
        limit_price_cents=price,
    )
    assert insufficient_shares.status_code == 409
    assert insufficient_shares.json()["error"]["code"] == "exchange.insufficient_shares"

    extreme_price = _post_order(
        client,
        auth_headers,
        listing_id=listing_id,
        key="exchange-price-deviation",
        side="sell",
        order_type="limit",
        quantity=1,
        limit_price_cents=price * 2,
    )
    assert extreme_price.status_code == 422
    assert extreme_price.json()["error"]["code"] == "exchange.price_deviation"

    own_sell = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="exchange-own-sell",
        side="sell",
        order_type="limit",
        quantity=10,
        limit_price_cents=price,
    )
    assert own_sell.status_code == 201
    self_buy = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="exchange-self-buy",
        side="buy",
        order_type="market",
        quantity=10,
    )
    assert self_buy.status_code == 409
    assert self_buy.json()["error"]["code"] == "exchange.no_liquidity"

    expires_at = datetime.now(UTC) + timedelta(minutes=5)
    expiring = _post_order(
        client,
        auth_headers,
        listing_id=listing_id,
        key="exchange-expiring",
        side="sell",
        order_type="limit",
        quantity=20,
        limit_price_cents=price + 1,
        expires_at=expires_at,
    )
    assert expiring.status_code == 201
    with SessionLocal() as db:
        assert expire_due_orders(db, at=expires_at + timedelta(seconds=1)) == 1
    own_orders = client.get("/api/v1/exchange/orders/me", headers=auth_headers)
    expired = next(item for item in own_orders.json() if item["id"] == expiring.json()["id"])
    assert expired["status"] == "expired"
    assert expired["reserved_shares"] == 0

    monkeypatch.setattr(get_settings(), "exchange_order_rate_limit_per_minute", 1)
    rate_limited = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="exchange-rate-limited",
        side="buy",
        order_type="limit",
        quantity=1,
        limit_price_cents=price,
    )
    assert rate_limited.status_code == 429
    assert rate_limited.json()["error"]["code"] == "exchange.rate_limited"

    with SessionLocal() as db:
        buyer_account = db.scalar(
            select(Account).where(
                Account.owner_type == "profile",
                Account.owner_id == buyer["id"],
            )
        )
        assert buyer_account is not None
        assert buyer_account.reserved_cents == 0
        assert db.scalar(select(func.count(ExchangeTrade.id))) == 2
        assert db.scalar(select(func.count(PriceSnapshot.id))) == 2
        assert (
            db.scalar(
                select(func.count(Notification.id)).where(
                    Notification.event_type == "exchange.trade.executed"
                )
            )
            == 4
        )


def test_concurrent_buyers_preserve_supply_and_price_time_priority(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    _, listing = _prepare_listing(
        client,
        auth_headers,
        joined_profile,
        offered_shares=3_000,
    )
    _, buyer_one = _join_additional_player(client, suffix="concurrent-one")
    _, buyer_two = _join_additional_player(client, suffix="concurrent-two")
    _, buyer_three = _join_additional_player(client, suffix="priority-three")
    price = int(listing["initial_price_cents"])
    listing_id = str(listing["id"])

    def concurrent_buy(profile_id: str, key: str) -> tuple[str, str]:
        with SessionLocal() as db:
            profile = db.get(PlayerProfile, profile_id)
            assert profile is not None
            order = place_order(
                db,
                profile,
                listing_id=listing_id,
                side="buy",
                order_type="limit",
                quantity=2_000,
                limit_price_cents=price,
                expires_at=None,
                idempotency_key=key,
                request_id=key,
                settings=get_settings(),
            )
            return order.id, order.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(concurrent_buy, str(buyer_one["id"]), "concurrent-buy-one"),
            executor.submit(concurrent_buy, str(buyer_two["id"]), "concurrent-buy-two"),
        ]
        results = [future.result() for future in futures]
    assert sorted(status for _, status in results) == ["filled", "partially_filled"]
    partial_order_id = next(
        order_id for order_id, status in results if status == "partially_filled"
    )
    with SessionLocal() as db:
        partial_order = db.get(ExchangeOrder, partial_order_id)
        assert partial_order is not None and partial_order.profile_id is not None
        partial_owner = db.get(PlayerProfile, partial_order.profile_id)
        assert partial_owner is not None
        exchange.cancel_order(
            db,
            partial_owner,
            partial_order.id,
            idempotency_key="cancel-concurrent-remainder",
            request_id="cancel-concurrent-remainder",
        )

    with SessionLocal() as db:
        share_class = db.scalar(select(ShareClass).where(ShareClass.listing_id == listing_id))
        assert share_class is not None
        assert _supply(db, share_class.id) == share_class.total_shares
        assert (
            db.scalar(
                select(func.coalesce(func.sum(ExchangeTrade.quantity), 0)).where(
                    ExchangeTrade.listing_id == listing_id
                )
            )
            == 3_000
        )
        holdings = list(
            db.scalars(
                select(ShareHolding)
                .where(
                    ShareHolding.share_class_id == share_class.id,
                    ShareHolding.profile_id.in_((str(buyer_one["id"]), str(buyer_two["id"]))),
                )
                .order_by(ShareHolding.quantity.desc())
            )
        )
        assert [holding.quantity for holding in holdings] == [2_000, 1_000]
        seller_id = str(holdings[0].profile_id)

    def place_direct(
        profile_id: str,
        *,
        key: str,
        side: str,
        quantity: int,
        limit_price: int,
    ) -> str:
        with SessionLocal() as db:
            profile = db.get(PlayerProfile, profile_id)
            assert profile is not None
            return place_order(
                db,
                profile,
                listing_id=listing_id,
                side=side,
                order_type="limit",
                quantity=quantity,
                limit_price_cents=limit_price,
                expires_at=None,
                idempotency_key=key,
                request_id=key,
                settings=get_settings(),
            ).id

    older_buy_id = place_direct(
        str(buyer_three["id"]),
        key="priority-older-buy",
        side="buy",
        quantity=100,
        limit_price=price,
    )
    newer_buy_id = place_direct(
        str(joined_profile["id"]),
        key="priority-newer-buy",
        side="buy",
        quantity=100,
        limit_price=price,
    )
    sell_id = place_direct(
        seller_id,
        key="priority-sell",
        side="sell",
        quantity=150,
        limit_price=price,
    )

    with SessionLocal() as db:
        older = db.get(ExchangeOrder, older_buy_id)
        newer = db.get(ExchangeOrder, newer_buy_id)
        sale = db.get(ExchangeOrder, sell_id)
        share_class = db.scalar(select(ShareClass).where(ShareClass.listing_id == listing_id))
        assert older is not None and newer is not None and sale is not None
        assert older.status == "filled"
        assert newer.status == "partially_filled"
        assert newer.remaining_quantity == 50
        assert sale.status == "filled"
        assert share_class is not None
        assert _supply(db, share_class.id) == share_class.total_shares


def test_concurrent_sellers_cannot_overfill_a_resting_buy(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    _, listing = _prepare_listing(
        client,
        auth_headers,
        joined_profile,
        offered_shares=2_000,
    )
    buyer_headers, buyer = _join_additional_player(client, suffix="seller-holder")
    _, resting_buyer = _join_additional_player(client, suffix="resting-buyer")
    price = int(listing["initial_price_cents"])
    listing_id = str(listing["id"])
    allocation = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="seller-allocation",
        side="buy",
        order_type="limit",
        quantity=2_000,
        limit_price_cents=price,
    )
    assert allocation.status_code == 201

    with SessionLocal() as db:
        profile = db.get(PlayerProfile, str(resting_buyer["id"]))
        assert profile is not None
        resting = place_order(
            db,
            profile,
            listing_id=listing_id,
            side="buy",
            order_type="limit",
            quantity=1_000,
            limit_price_cents=price,
            expires_at=None,
            idempotency_key="resting-buy",
            request_id="resting-buy",
            settings=get_settings(),
        )
        resting_id = resting.id

    def concurrent_sell(profile_id: str, key: str) -> tuple[str, str]:
        with SessionLocal() as db:
            profile = db.get(PlayerProfile, profile_id)
            assert profile is not None
            order = place_order(
                db,
                profile,
                listing_id=listing_id,
                side="sell",
                order_type="limit",
                quantity=700,
                limit_price_cents=price,
                expires_at=None,
                idempotency_key=key,
                request_id=key,
                settings=get_settings(),
            )
            return order.id, order.status

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(
                concurrent_sell,
                str(joined_profile["id"]),
                "concurrent-sell-founder",
            ),
            executor.submit(
                concurrent_sell,
                str(buyer["id"]),
                "concurrent-sell-holder",
            ),
        ]
        results = [future.result() for future in futures]
    assert sorted(status for _, status in results) == ["filled", "partially_filled"]

    with SessionLocal() as db:
        resting = db.get(ExchangeOrder, resting_id)
        share_class = db.scalar(select(ShareClass).where(ShareClass.listing_id == listing_id))
        assert resting is not None and resting.status == "filled"
        filled = int(
            db.scalar(
                select(func.coalesce(func.sum(ExchangeTrade.quantity), 0)).where(
                    ExchangeTrade.buy_order_id == resting_id
                )
            )
            or 0
        )
        assert filled == 1_000
        assert share_class is not None
        assert _supply(db, share_class.id) == share_class.total_shares


def test_trade_failure_rolls_back_cash_shares_orders_and_audit(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, listing = _prepare_listing(client, auth_headers, joined_profile)
    _, buyer = _join_additional_player(client, suffix="rollback")
    listing_id = str(listing["id"])
    price = int(listing["initial_price_cents"])

    with SessionLocal() as db:
        share_class = db.scalar(select(ShareClass).where(ShareClass.listing_id == listing_id))
        issuer = db.scalar(
            select(ShareHolding).where(
                ShareHolding.share_class_id == share_class.id,
                ShareHolding.company_id.is_not(None),
            )
        )
        balance = db.scalar(
            select(ResourceBalance).where(ResourceBalance.profile_id == buyer["id"])
        )
        assert share_class is not None and issuer is not None and balance is not None
        issuer_before = issuer.quantity
        buyer_cash_before = balance.cash
        ipo_order = db.scalar(
            select(ExchangeOrder).where(
                ExchangeOrder.listing_id == listing_id,
                ExchangeOrder.order_type == "ipo",
            )
        )
        assert ipo_order is not None
        ipo_remaining_before = ipo_order.remaining_quantity

    def fail_transfer(*args: object, **kwargs: object) -> object:
        raise RuntimeError("injected exchange transfer failure")

    monkeypatch.setattr(exchange, "transfer_profile_cash_to_account", fail_transfer)
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, str(buyer["id"]))
        assert profile is not None
        with pytest.raises(RuntimeError, match="injected"):
            place_order(
                db,
                profile,
                listing_id=listing_id,
                side="buy",
                order_type="limit",
                quantity=100,
                limit_price_cents=price,
                expires_at=None,
                idempotency_key="rollback-buy",
                request_id="rollback-buy",
                settings=get_settings(),
            )
        db.rollback()

    with SessionLocal() as db:
        share_class = db.scalar(select(ShareClass).where(ShareClass.listing_id == listing_id))
        issuer = db.scalar(
            select(ShareHolding).where(
                ShareHolding.share_class_id == share_class.id,
                ShareHolding.company_id.is_not(None),
            )
        )
        balance = db.scalar(
            select(ResourceBalance).where(ResourceBalance.profile_id == buyer["id"])
        )
        ipo_order = db.scalar(
            select(ExchangeOrder).where(
                ExchangeOrder.listing_id == listing_id,
                ExchangeOrder.order_type == "ipo",
            )
        )
        assert share_class is not None and issuer is not None and balance is not None
        assert ipo_order is not None
        assert issuer.quantity == issuer_before
        assert ipo_order.remaining_quantity == ipo_remaining_before
        assert balance.cash == buyer_cash_before
        assert db.scalar(select(func.count(ExchangeTrade.id))) == 0
        assert (
            db.scalar(
                select(func.count(ExchangeOrder.id)).where(
                    ExchangeOrder.idempotency_key == "rollback-buy"
                )
            )
            == 0
        )
        assert _supply(db, share_class.id) == share_class.total_shares


def test_dividend_snapshot_is_atomic_balanced_immutable_and_idempotent(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    company, listing = _prepare_listing(
        client,
        auth_headers,
        joined_profile,
        total_shares=10_000,
        offered_shares=1_000,
    )
    buyer_headers, buyer = _join_additional_player(client, suffix="dividend")
    price = int(listing["initial_price_cents"])
    listing_id = str(listing["id"])
    buy = _post_order(
        client,
        buyer_headers,
        listing_id=listing_id,
        key="dividend-allocation",
        side="buy",
        order_type="limit",
        quantity=250,
        limit_price_cents=price,
    )
    assert buy.status_code == 201

    with SessionLocal() as db:
        balances_before = {
            balance.profile_id: balance.cash
            for balance in db.scalars(
                select(ResourceBalance).where(
                    ResourceBalance.profile_id.in_((str(joined_profile["id"]), str(buyer["id"])))
                )
            )
        }

    unauthorized = client.post(
        f"/api/v1/companies/{company['id']}/dividends",
        headers={**buyer_headers, "Idempotency-Key": "dividend-unauthorized"},
        json={"per_share_cents": 2},
    )
    assert unauthorized.status_code == 403
    assert unauthorized.json()["error"]["code"] == "company.control_required"

    headers = {**auth_headers, "Idempotency-Key": "dividend-one"}
    first = client.post(
        f"/api/v1/companies/{company['id']}/dividends",
        headers=headers,
        json={"per_share_cents": 2},
    )
    repeated = client.post(
        f"/api/v1/companies/{company['id']}/dividends",
        headers=headers,
        json={"per_share_cents": 2},
    )
    assert first.status_code == repeated.status_code == 201
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["eligible_shares"] == 9_250
    assert first.json()["total_paid_cents"] == 18_500

    history = client.get(
        f"/api/v1/exchange/listings/{listing_id}/dividends",
        headers=buyer_headers,
    )
    shareholders = client.get(
        f"/api/v1/exchange/listings/{listing_id}/shareholders",
        headers=buyer_headers,
    )
    portfolio = client.get("/api/v1/exchange/portfolio", headers=buyer_headers)
    assert history.status_code == shareholders.status_code == portfolio.status_code == 200
    assert len(history.json()) == 1
    assert portfolio.json()[0]["quantity"] == 250
    assert sum(item["ownership_bps"] for item in shareholders.json()) == 9_250

    with SessionLocal() as db:
        declaration = db.get(DividendDeclaration, first.json()["id"])
        share_class = db.scalar(select(ShareClass).where(ShareClass.listing_id == listing_id))
        assert declaration is not None and share_class is not None
        entitlements = list(
            db.scalars(
                select(DividendEntitlement).where(
                    DividendEntitlement.declaration_id == declaration.id
                )
            )
        )
        assert len(entitlements) == 2
        assert sorted(item.quantity for item in entitlements) == [250, 9_000]
        assert sum(item.amount_cents for item in entitlements) == 18_500
        assert len({item.transaction_id for item in entitlements}) == 2
        for item in entitlements:
            assert transaction_balance_cents(db, item.transaction_id) == 0
        balances_after = {
            balance.profile_id: balance.cash
            for balance in db.scalars(
                select(ResourceBalance).where(
                    ResourceBalance.profile_id.in_((str(joined_profile["id"]), str(buyer["id"])))
                )
            )
        }
        assert balances_after[str(joined_profile["id"])] == balances_before[
            str(joined_profile["id"])
        ] + Decimal("180.00")
        assert balances_after[str(buyer["id"])] == balances_before[str(buyer["id"])] + Decimal(
            "5.00"
        )
        assert _supply(db, share_class.id) == share_class.total_shares
        declaration.total_paid_cents = 1
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()
        assert (
            db.scalar(
                select(func.count(LedgerTransaction.id)).where(
                    LedgerTransaction.transaction_type == "exchange_dividend"
                )
            )
            == 2
        )
        assert (
            db.scalar(
                select(func.count(CompanyEconomyReport.id)).where(
                    CompanyEconomyReport.company_id == company["id"]
                )
            )
            == 3
        )
