from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from shadowgrid.bootstrap import bootstrap_world
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.finance import (
    ensure_system_account,
    post_balanced_transfer,
    transaction_balance_cents,
)
from shadowgrid.models import (
    Company,
    District,
    LedgerTransaction,
    PropertyImprovement,
    PropertyLease,
    PropertyLeasePayment,
    PropertyTransfer,
    RealEstateDistrictIndex,
    RealEstateIndexSnapshot,
    RealEstateProperty,
    User,
    World,
)
from shadowgrid.real_estate import advance_real_estate
from shadowgrid.security import hash_password
from sqlalchemy import func, select

PASSWORD = "StrongPassword123"


def _seed_real_estate() -> None:
    with SessionLocal() as db:
        bootstrap_world(db, get_settings())
        db.commit()


def _join_player(
    client: TestClient,
    *,
    suffix: str,
) -> tuple[dict[str, str], str]:
    email = f"property-{suffix}@example.com"
    with SessionLocal() as db:
        world = db.scalar(select(World))
        district = db.scalar(select(District))
        assert world is not None and district is not None
        db.add(
            User(
                email=email,
                password_hash=hash_password(PASSWORD),
                display_name=f"Property {suffix}",
                email_verified=True,
            )
        )
        db.commit()
        world_id = world.id
        district_id = district.id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    joined = client.post(
        f"/api/v1/worlds/{world_id}/join",
        headers={**headers, "Idempotency-Key": f"property-join-{suffix}"},
        json={
            "codename": f"Property {suffix}",
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
        headers={**headers, "Idempotency-Key": f"property-company-{suffix}"},
        json={
            "name": f"Property {suffix} GmbH",
            "industry": "technology",
            "district_id": district["id"],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _property(
    client: TestClient,
    headers: dict[str, str],
    property_type: str,
) -> dict[str, object]:
    response = client.get("/api/v1/real-estate/properties", headers=headers)
    assert response.status_code == 200, response.text
    return next(
        item
        for item in response.json()
        if item["property_type"] == property_type and item["status"] == "available"
    )


def _buy(
    client: TestClient,
    headers: dict[str, str],
    property_id: str,
    *,
    key: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/real-estate/properties/{property_id}/buy",
        headers={**headers, "Idempotency-Key": key},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_bootstrap_seeds_district_indices_and_properties_once(
    client: TestClient,
) -> None:
    _seed_real_estate()
    _seed_real_estate()
    headers, _ = _join_player(client, suffix="bootstrap")

    indices = client.get("/api/v1/real-estate/indices", headers=headers)
    properties = client.get("/api/v1/real-estate/properties", headers=headers)
    config = client.get("/api/v1/real-estate/config", headers=headers)
    assert indices.status_code == properties.status_code == config.status_code == 200
    assert len(indices.json()) == 5
    assert len(properties.json()) == 20
    assert {item["property_type"] for item in properties.json()} == {
        "land",
        "building",
        "commercial_space",
        "headquarters",
    }
    assert all(item["effective_sale_price_cents"] > 0 for item in properties.json())
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RealEstateDistrictIndex)) == 5
        assert db.scalar(select(func.count()).select_from(RealEstateIndexSnapshot)) == 5


def test_system_purchase_resale_and_ownership_are_ledger_backed(
    client: TestClient,
) -> None:
    _seed_real_estate()
    first_headers, first_profile_id = _join_player(client, suffix="first")
    second_headers, second_profile_id = _join_player(client, suffix="second")
    property_ = _property(client, first_headers, "land")
    property_id = str(property_["id"])

    first = _buy(
        client,
        first_headers,
        property_id,
        key="p" * 80,
    )
    repeated = _buy(
        client,
        first_headers,
        property_id,
        key="p" * 80,
    )
    assert first["id"] == repeated["id"]
    listed = client.post(
        f"/api/v1/real-estate/properties/{property_id}/list-sale",
        headers={**first_headers, "Idempotency-Key": "property-list-sale"},
        json={"asking_price_cents": 1_250_000},
    )
    assert listed.status_code == 200, listed.text
    resale = _buy(
        client,
        second_headers,
        property_id,
        key="property-buy-second",
    )
    assert resale["seller_profile_id"] == first_profile_id
    assert resale["buyer_profile_id"] == second_profile_id
    assert resale["transfer_type"] == "resale"

    forbidden = client.post(
        f"/api/v1/real-estate/properties/{property_id}/list-sale",
        headers={**first_headers, "Idempotency-Key": "property-list-foreign"},
        json={"asking_price_cents": 1_500_000},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "property.not_owned"

    with SessionLocal() as db:
        stored = db.get(RealEstateProperty, property_id)
        transfers = list(
            db.scalars(
                select(PropertyTransfer)
                .where(PropertyTransfer.property_id == property_id)
                .order_by(PropertyTransfer.created_at)
            )
        )
        assert stored is not None and stored.owner_profile_id == second_profile_id
        assert len(transfers) == 2
        transactions = [
            db.get(LedgerTransaction, transfer.transaction_id) for transfer in transfers
        ]
        assert any(
            transaction is not None and 120 < len(transaction.idempotency_key) <= 160
            for transaction in transactions
        )
        assert all(
            transaction_balance_cents(db, transfer.transaction_id) == 0 for transfer in transfers
        )
        stored.property_code = "tampered-code"
        with pytest.raises(ValueError, match="immutable"):
            db.flush()


def test_lease_pays_each_period_once_and_completes(
    client: TestClient,
) -> None:
    _seed_real_estate()
    headers, _ = _join_player(client, suffix="lease")
    company_id = _create_company(client, headers, suffix="Lease")
    property_ = _property(client, headers, "commercial_space")
    property_id = str(property_["id"])
    _buy(client, headers, property_id, key="property-buy-lease")
    listing = client.post(
        f"/api/v1/real-estate/properties/{property_id}/list-rent",
        headers={**headers, "Idempotency-Key": "property-list-rent"},
        json={"rent_cents_per_period": 100_000},
    )
    assert listing.status_code == 200, listing.text
    lease = client.post(
        f"/api/v1/real-estate/properties/{property_id}/lease",
        headers={**headers, "Idempotency-Key": "property-lease-start"},
        json={"tenant_company_id": company_id, "term_periods": 2},
    )
    duplicate = client.post(
        f"/api/v1/real-estate/properties/{property_id}/lease",
        headers={**headers, "Idempotency-Key": "property-lease-start"},
        json={"tenant_company_id": company_id, "term_periods": 2},
    )
    assert lease.status_code == duplicate.status_code == 201
    assert lease.json()["id"] == duplicate.json()["id"]
    assert lease.json()["periods_paid"] == 1

    with SessionLocal() as db:
        stored = db.get(PropertyLease, lease.json()["id"])
        assert stored is not None
        at = stored.next_payment_at + timedelta(seconds=1)
        result = advance_real_estate(db, get_settings(), at=at)
        assert result["rent_payments_paid"] == 1
        assert result["leases_completed"] == 1
        assert advance_real_estate(db, get_settings(), at=at) == {
            "indices_refreshed": 0,
            "rent_payments_paid": 0,
            "leases_defaulted": 0,
            "leases_completed": 0,
        }
        db.refresh(stored)
        assert stored.status == "completed"
        payments = list(
            db.scalars(
                select(PropertyLeasePayment)
                .where(PropertyLeasePayment.lease_id == stored.id)
                .order_by(PropertyLeasePayment.period_number)
            )
        )
        assert [(payment.period_number, payment.status) for payment in payments] == [
            (1, "paid"),
            (2, "paid"),
        ]
        assert all(
            payment.transaction_id is not None
            and transaction_balance_cents(db, payment.transaction_id) == 0
            for payment in payments
        )
        property_after = db.get(RealEstateProperty, property_id)
        assert property_after is not None
        assert property_after.status == "owned"
        assert property_after.company_use_id is None


def test_rent_default_and_headquarters_upgrade_are_retry_safe(
    client: TestClient,
) -> None:
    _seed_real_estate()
    headers, profile_id = _join_player(client, suffix="hq")
    company_id = _create_company(client, headers, suffix="HQ")
    headquarters = _property(client, headers, "headquarters")
    headquarters_id = str(headquarters["id"])
    _buy(client, headers, headquarters_id, key="property-buy-hq")
    assigned = client.post(
        f"/api/v1/real-estate/properties/{headquarters_id}/assign",
        headers={**headers, "Idempotency-Key": "property-assign-hq"},
        json={"company_id": company_id},
    )
    repeated_assignment = client.post(
        f"/api/v1/real-estate/properties/{headquarters_id}/assign",
        headers={**headers, "Idempotency-Key": "property-assign-hq"},
        json={"company_id": company_id},
    )
    assert assigned.status_code == repeated_assignment.status_code == 200
    assert assigned.json()["company_use_id"] == company_id
    upgraded = client.post(
        f"/api/v1/real-estate/properties/{headquarters_id}/headquarters/upgrade",
        headers={**headers, "Idempotency-Key": "property-upgrade-hq"},
    )
    repeated_upgrade = client.post(
        f"/api/v1/real-estate/properties/{headquarters_id}/headquarters/upgrade",
        headers={**headers, "Idempotency-Key": "property-upgrade-hq"},
    )
    assert upgraded.status_code == repeated_upgrade.status_code == 201
    assert upgraded.json()["id"] == repeated_upgrade.json()["id"]
    assert upgraded.json()["level_after"] == 1

    rentable = _property(client, headers, "land")
    rentable_id = str(rentable["id"])
    _buy(client, headers, rentable_id, key="property-buy-default")
    listed = client.post(
        f"/api/v1/real-estate/properties/{rentable_id}/list-rent",
        headers={**headers, "Idempotency-Key": "property-list-default"},
        json={"rent_cents_per_period": 500_000},
    )
    assert listed.status_code == 200, listed.text
    lease = client.post(
        f"/api/v1/real-estate/properties/{rentable_id}/lease",
        headers={**headers, "Idempotency-Key": "property-lease-default"},
        json={"tenant_company_id": company_id, "term_periods": 3},
    )
    assert lease.status_code == 201, lease.text

    with SessionLocal() as db:
        company = db.get(Company, company_id)
        stored_lease = db.get(PropertyLease, lease.json()["id"])
        assert company is not None and stored_lease is not None
        available = company.account.balance_cents - company.account.reserved_cents
        post_balanced_transfer(
            db,
            world_id=company.world_id,
            source_account=company.account,
            target_account=ensure_system_account(db, company.world_id),
            amount_cents=available,
            transaction_type="property_test_cash_drain",
            idempotency_key=f"property-test-drain:{stored_lease.id}",
            reference_type="property_lease",
            reference_id=stored_lease.id,
            actor_profile_id=profile_id,
        )
        db.commit()
        at = stored_lease.next_payment_at + timedelta(seconds=1)
        result = advance_real_estate(db, get_settings(), at=at)
        assert result["leases_defaulted"] == 1
        assert advance_real_estate(db, get_settings(), at=at)["leases_defaulted"] == 0
        db.refresh(stored_lease)
        assert stored_lease.status == "defaulted"
        payment = db.scalar(
            select(PropertyLeasePayment).where(
                PropertyLeasePayment.lease_id == stored_lease.id,
                PropertyLeasePayment.status == "defaulted",
            )
        )
        assert payment is not None and payment.transaction_id is None
        assert db.scalar(select(func.count()).select_from(PropertyImprovement)) == 1
        upgrade_transaction = db.get(
            LedgerTransaction,
            str(upgraded.json()["transaction_id"]),
        )
        assert upgrade_transaction is not None
        assert transaction_balance_cents(db, upgrade_transaction.id) == 0
