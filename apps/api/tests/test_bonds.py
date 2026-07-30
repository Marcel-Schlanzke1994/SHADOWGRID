from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from shadowgrid.bonds import advance_bonds
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.finance import (
    ensure_system_account,
    money_to_cents,
    post_balanced_transfer,
    transaction_balance_cents,
)
from shadowgrid.models import (
    BondHolding,
    BondIssue,
    BondLedgerEntry,
    BondSettlement,
    BondSubscription,
    Company,
    District,
    LedgerTransaction,
    RealtimeEvent,
    ResourceBalance,
    User,
    World,
)
from shadowgrid.security import hash_password
from sqlalchemy import func, select

PASSWORD = "StrongPassword123"


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _join_player(
    client: TestClient,
    *,
    suffix: str,
) -> tuple[dict[str, str], str]:
    email = f"bond-{suffix}@example.com"
    with SessionLocal() as db:
        world = db.scalar(select(World))
        district = db.scalar(select(District))
        assert world is not None and district is not None
        db.add(
            User(
                email=email,
                password_hash=hash_password(PASSWORD),
                display_name=f"Bond {suffix}",
                email_verified=True,
            )
        )
        db.commit()
        world_id = world.id
        district_id = district.id
    headers = _login(client, email)
    joined = client.post(
        f"/api/v1/worlds/{world_id}/join",
        headers={**headers, "Idempotency-Key": f"bond-join-{suffix}"},
        json={
            "codename": f"Bond {suffix}",
            "archetype": "business_consortium",
            "home_district_id": district_id,
        },
    )
    assert joined.status_code == 200, joined.text
    return headers, str(joined.json()["id"])


def _create_company(
    client: TestClient,
    headers: dict[str, str],
    *,
    suffix: str,
) -> str:
    district = client.get("/api/v1/districts", headers=headers).json()[0]
    response = client.post(
        "/api/v1/companies",
        headers={**headers, "Idempotency-Key": f"bond-company-{suffix}"},
        json={
            "name": f"Bond {suffix} GmbH",
            "industry": "technology",
            "district_id": district["id"],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _issue(
    client: TestClient,
    headers: dict[str, str],
    company_id: str,
    *,
    key: str,
    symbol: str,
    face_value_cents: int = 100_000,
    total_units: int = 5,
    term_periods: int = 2,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/bonds/issues",
        headers={**headers, "Idempotency-Key": key},
        json={
            "issuer_company_id": company_id,
            "symbol": symbol,
            "title": f"{symbol} growth bond",
            "face_value_cents": face_value_cents,
            "total_units": total_units,
            "coupon_rate_bps": 800,
            "term_periods": term_periods,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _subscribe(
    client: TestClient,
    headers: dict[str, str],
    issue_id: str,
    *,
    quantity: int,
    key: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/bonds/issues/{issue_id}/subscribe",
        headers={**headers, "Idempotency-Key": key},
        json={"quantity": quantity},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_bond_issue_subscriptions_reservations_holdings_and_activation(
    client: TestClient,
) -> None:
    issuer_headers, _ = _join_player(client, suffix="issuer")
    first_headers, first_profile_id = _join_player(client, suffix="first")
    second_headers, second_profile_id = _join_player(client, suffix="second")
    company_id = _create_company(client, issuer_headers, suffix="Issuer")
    issue = _issue(
        client,
        issuer_headers,
        company_id,
        key="bond-issue-001",
        symbol="RBG1",
    )
    duplicate_issue = _issue(
        client,
        issuer_headers,
        company_id,
        key="bond-issue-001",
        symbol="RBG1",
    )
    assert issue["id"] == duplicate_issue["id"]

    first = _subscribe(
        client,
        first_headers,
        str(issue["id"]),
        quantity=2,
        key="bond-subscribe-first",
    )
    repeated = _subscribe(
        client,
        first_headers,
        str(issue["id"]),
        quantity=2,
        key="bond-subscribe-first",
    )
    assert first["id"] == repeated["id"]
    with SessionLocal() as db:
        company = db.get(Company, company_id)
        stored_issue = db.get(BondIssue, issue["id"])
        assert company is not None and stored_issue is not None
        assert stored_issue.status == "offering"
        assert company.account.reserved_cents == 200_000
        assert company.debt_cents == 0

    forbidden = client.post(
        f"/api/v1/bonds/issues/{issue['id']}/activate",
        headers=first_headers,
    )
    assert forbidden.status_code == 403
    _subscribe(
        client,
        second_headers,
        str(issue["id"]),
        quantity=3,
        key="bond-subscribe-second",
    )

    with SessionLocal() as db:
        company = db.get(Company, company_id)
        stored_issue = db.get(BondIssue, issue["id"])
        assert company is not None and stored_issue is not None
        assert stored_issue.status == "active"
        assert stored_issue.sold_units == 5
        assert company.account.reserved_cents == 0
        assert company.debt_cents == 500_000
        holdings = list(
            db.scalars(
                select(BondHolding)
                .where(BondHolding.issue_id == stored_issue.id)
                .order_by(BondHolding.profile_id)
            )
        )
        assert {item.profile_id: item.quantity for item in holdings} == {
            first_profile_id: 2,
            second_profile_id: 3,
        }
        assert (
            db.scalar(
                select(func.count())
                .select_from(BondLedgerEntry)
                .where(BondLedgerEntry.issue_id == stored_issue.id)
            )
            == 2
        )
        subscriptions = list(
            db.scalars(select(BondSubscription).where(BondSubscription.issue_id == stored_issue.id))
        )
        assert all(
            transaction_balance_cents(db, item.transaction_id) == 0 for item in subscriptions
        )
        stored_issue.face_value_cents += 1
        with pytest.raises(ValueError, match="immutable"):
            db.flush()


def test_coupon_and_redemption_pay_every_holder_exactly_once(
    client: TestClient,
) -> None:
    issuer_headers, _ = _join_player(client, suffix="repay-issuer")
    investor_headers, investor_profile_id = _join_player(client, suffix="repay-investor")
    company_id = _create_company(client, issuer_headers, suffix="Repay")
    issue = _issue(
        client,
        issuer_headers,
        company_id,
        key="bond-repay-issue",
        symbol="PAY2",
        total_units=3,
        term_periods=2,
    )
    _subscribe(
        client,
        investor_headers,
        str(issue["id"]),
        quantity=3,
        key="bond-repay-subscribe",
    )

    with SessionLocal() as db:
        stored_issue = db.get(BondIssue, issue["id"])
        company = db.get(Company, company_id)
        balance = db.get(ResourceBalance, investor_profile_id)
        assert stored_issue is not None and company is not None and balance is not None
        investor_cash_before = money_to_cents(balance.cash)
        assert stored_issue.next_coupon_at is not None
        at = stored_issue.next_coupon_at + timedelta(
            minutes=get_settings().bond_coupon_interval_minutes,
            seconds=1,
        )
        result = advance_bonds(db, get_settings(), at=at)
        assert result == {
            "issues_activated": 0,
            "issues_cancelled": 0,
            "coupon_periods_paid": 2,
            "issues_defaulted": 0,
            "issues_repaid": 1,
        }
        db.refresh(stored_issue)
        db.refresh(company)
        db.refresh(balance)
        assert stored_issue.status == "repaid"
        assert stored_issue.coupons_paid == 2
        assert company.debt_cents == 0
        assert money_to_cents(balance.cash) == investor_cash_before + 348_000
        settlements = list(
            db.scalars(
                select(BondSettlement)
                .where(BondSettlement.issue_id == stored_issue.id)
                .order_by(
                    BondSettlement.period_number,
                    BondSettlement.payment_type,
                )
            )
        )
        assert [
            (item.period_number, item.payment_type, item.amount_cents) for item in settlements
        ] == [
            (1, "coupon", 24_000),
            (2, "coupon", 24_000),
            (2, "redemption", 300_000),
        ]
        assert all(
            item.transaction_id is not None
            and transaction_balance_cents(db, item.transaction_id) == 0
            for item in settlements
        )
        holding = db.scalar(select(BondHolding).where(BondHolding.issue_id == stored_issue.id))
        assert holding is not None and holding.quantity == 0
        transaction_count = db.scalar(
            select(func.count())
            .select_from(LedgerTransaction)
            .where(LedgerTransaction.transaction_type.in_(("bond_coupon", "bond_redemption")))
        )
        assert advance_bonds(db, get_settings(), at=at) == {
            "issues_activated": 0,
            "issues_cancelled": 0,
            "coupon_periods_paid": 0,
            "issues_defaulted": 0,
            "issues_repaid": 0,
        }
        assert (
            db.scalar(
                select(func.count())
                .select_from(LedgerTransaction)
                .where(LedgerTransaction.transaction_type.in_(("bond_coupon", "bond_redemption")))
            )
            == transaction_count
        )


def test_coupon_default_and_empty_offering_expiry_are_retry_safe(
    client: TestClient,
) -> None:
    issuer_headers, _ = _join_player(client, suffix="default-issuer")
    investor_headers, _ = _join_player(client, suffix="default-investor")
    company_id = _create_company(client, issuer_headers, suffix="Default")
    issue = _issue(
        client,
        issuer_headers,
        company_id,
        key="bond-default-issue",
        symbol="DEF3",
        face_value_cents=500_000,
        total_units=1,
        term_periods=2,
    )
    empty = _issue(
        client,
        issuer_headers,
        company_id,
        key="bond-empty-issue",
        symbol="EMP4",
        face_value_cents=100_000,
        total_units=1,
        term_periods=2,
    )
    _subscribe(
        client,
        investor_headers,
        str(issue["id"]),
        quantity=1,
        key="bond-default-subscribe",
    )

    with SessionLocal() as db:
        stored_issue = db.get(BondIssue, issue["id"])
        empty_issue = db.get(BondIssue, empty["id"])
        company = db.get(Company, company_id)
        assert stored_issue is not None and empty_issue is not None and company is not None
        assert stored_issue.next_coupon_at is not None
        reputation_before = company.reputation_bps
        pressure_before = company.investigation_pressure_bps
        available = company.account.balance_cents - company.account.reserved_cents
        post_balanced_transfer(
            db,
            world_id=company.world_id,
            source_account=company.account,
            target_account=ensure_system_account(db, company.world_id),
            amount_cents=available,
            transaction_type="bond_test_cash_drain",
            idempotency_key=f"bond-test-drain:{stored_issue.id}",
            reference_type="bond_issue",
            reference_id=stored_issue.id,
            actor_profile_id=None,
        )
        db.commit()
        at = max(stored_issue.next_coupon_at, empty_issue.offering_ends_at) + timedelta(seconds=1)
        result = advance_bonds(db, get_settings(), at=at)
        assert result == {
            "issues_activated": 0,
            "issues_cancelled": 1,
            "coupon_periods_paid": 0,
            "issues_defaulted": 1,
            "issues_repaid": 0,
        }
        db.refresh(stored_issue)
        db.refresh(empty_issue)
        db.refresh(company)
        assert stored_issue.status == "defaulted"
        assert stored_issue.default_reason == "coupon_default"
        assert empty_issue.status == "cancelled"
        assert company.reputation_bps == (
            reputation_before - get_settings().bond_default_reputation_penalty_bps
        )
        assert company.investigation_pressure_bps == (
            pressure_before + get_settings().bond_default_investigation_penalty_bps
        )
        settlement = db.scalar(
            select(BondSettlement).where(BondSettlement.issue_id == stored_issue.id)
        )
        assert settlement is not None and settlement.status == "defaulted"
        assert settlement.transaction_id is None
        event_count = db.scalar(
            select(func.count())
            .select_from(RealtimeEvent)
            .where(RealtimeEvent.event_type == "bond.defaulted")
        )
        assert advance_bonds(db, get_settings(), at=at) == {
            "issues_activated": 0,
            "issues_cancelled": 0,
            "coupon_periods_paid": 0,
            "issues_defaulted": 0,
            "issues_repaid": 0,
        }
        assert (
            db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(RealtimeEvent.event_type == "bond.defaulted")
            )
            == event_count
        )
