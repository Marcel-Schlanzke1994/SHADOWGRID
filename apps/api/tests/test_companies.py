from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.domain import apply_profile_resource
from shadowgrid.finance import transaction_balance_cents
from shadowgrid.models import (
    AccountLedgerEntry,
    Company,
    CompanyInvestment,
    CompanyMetric,
    CompanyOwnership,
    District,
    LedgerTransaction,
    PlayerProfile,
    User,
    World,
)
from shadowgrid.security import hash_password
from sqlalchemy import func, select


def _company_payload(client: TestClient, headers: dict[str, str]) -> dict[str, str]:
    district = client.get("/api/v1/districts", headers=headers).json()[0]
    return {
        "name": "RheinCargo Solutions",
        "industry": "logistics",
        "district_id": district["id"],
    }


def _second_player_headers(client: TestClient) -> dict[str, str]:
    with SessionLocal() as db:
        user = User(
            email="second-player@example.com",
            password_hash=hash_password("StrongPassword123"),
            display_name="Second Player",
            email_verified=True,
        )
        db.add(user)
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "second-player@example.com", "password": "StrongPassword123"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    with SessionLocal() as db:
        world = db.scalar(select(World))
        district = db.scalar(select(District))
        assert world is not None and district is not None
        world_id = world.id
        district_id = district.id
    joined = client.post(
        f"/api/v1/worlds/{world_id}/join",
        headers={**headers, "Idempotency-Key": "second-player-join"},
        json={
            "codename": "Second Network",
            "archetype": "business_consortium",
            "home_district_id": district_id,
        },
    )
    assert joined.status_code == 200
    return headers


def test_company_creation_is_idempotent_owned_and_balanced(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    config = client.get("/api/v1/companies/config", headers=auth_headers)
    assert config.status_code == 200
    assert config.json()["founding_cost_cents"] == 2_000_000
    assert set(config.json()["industries"]) == {"gastronomy", "logistics", "technology"}

    headers = {**auth_headers, "Idempotency-Key": "c" * 80}
    first = client.post(
        "/api/v1/companies",
        headers=headers,
        json=_company_payload(client, auth_headers),
    )
    repeated = client.post(
        "/api/v1/companies",
        headers=headers,
        json=_company_payload(client, auth_headers),
    )

    assert first.status_code == repeated.status_code == 201
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["account_balance_cents"] == 2_000_000
    assert first.json()["enterprise_value_cents"] == 20_000_000
    company_id = first.json()["id"]

    resources = client.get("/api/v1/players/me/resources", headers=auth_headers)
    assert Decimal(str(resources.json()["cash"])) == Decimal("60000.00")

    with SessionLocal() as db:
        assert db.scalar(select(func.count(Company.id))) == 1
        ownership = list(
            db.scalars(select(CompanyOwnership).where(CompanyOwnership.company_id == company_id))
        )
        assert sum(item.ownership_bps for item in ownership) == 10_000
        transaction = db.scalar(
            select(LedgerTransaction).where(
                LedgerTransaction.transaction_type == "company_founding"
            )
        )
        assert transaction is not None
        assert 80 < len(transaction.idempotency_key) <= 160
        entries = list(
            db.scalars(
                select(AccountLedgerEntry).where(
                    AccountLedgerEntry.transaction_id == transaction.id
                )
            )
        )
        assert sorted(item.amount_cents for item in entries) == [-2_000_000, 2_000_000]
        assert transaction_balance_cents(db, transaction.id) == 0
        metrics = list(
            db.scalars(select(CompanyMetric).where(CompanyMetric.company_id == company_id))
        )
        assert len(metrics) == 1
        assert metrics[0].reason == "company_founding"
        transaction.transaction_type = "tampered"
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()

    ownership_response = client.get(
        f"/api/v1/companies/{company_id}/ownership",
        headers=auth_headers,
    )
    assert ownership_response.status_code == 200
    assert ownership_response.json()[0]["ownership_bps"] == 10_000

    duplicate_name = client.post(
        "/api/v1/companies",
        headers={**auth_headers, "Idempotency-Key": "company-create-duplicate-name"},
        json={**_company_payload(client, auth_headers), "name": "  RHEINCARGO   SOLUTIONS  "},
    )
    assert duplicate_name.status_code == 409
    assert duplicate_name.json()["error"]["code"] == "company.name_taken"


def test_company_investment_changes_only_configured_metric_and_is_idempotent(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    created = client.post(
        "/api/v1/companies",
        headers={**auth_headers, "Idempotency-Key": "company-create-investable"},
        json=_company_payload(client, auth_headers),
    )
    assert created.status_code == 201
    company_id = created.json()["id"]
    headers = {**auth_headers, "Idempotency-Key": "company-invest-capacity"}

    invested = client.post(
        f"/api/v1/companies/{company_id}/investments",
        headers=headers,
        json={"investment_type": "capacity"},
    )
    repeated = client.post(
        f"/api/v1/companies/{company_id}/investments",
        headers=headers,
        json={"investment_type": "capacity"},
    )

    assert invested.status_code == repeated.status_code == 200
    assert invested.json()["capacity"] == created.json()["capacity"] + 500
    assert invested.json()["quality"] == created.json()["quality"]
    assert invested.json()["innovation_bps"] == created.json()["innovation_bps"]
    assert invested.json()["compliance_bps"] == created.json()["compliance_bps"]
    assert invested.json()["account_balance_cents"] == 2_500_000
    assert invested.json()["version"] == created.json()["version"] + 1

    detail = client.get(f"/api/v1/companies/{company_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert len(detail.json()["investments"]) == 1
    assert len(detail.json()["metrics_history"]) == 2
    assert detail.json()["investments"][0]["amount_cents"] == 500_000

    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count(CompanyInvestment.id)).where(
                    CompanyInvestment.company_id == company_id
                )
            )
            == 1
        )
        transaction = db.scalar(
            select(LedgerTransaction).where(
                LedgerTransaction.transaction_type == "company_investment"
            )
        )
        assert transaction is not None
        assert transaction_balance_cents(db, transaction.id) == 0


def test_insufficient_cash_and_foreign_investment_are_rejected(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, str(joined_profile["id"]))
        assert profile is not None
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            Decimal("-70000.00"),
            reason="test_reservation",
            reference_type="profile",
            reference_id=profile.id,
            idempotency_key="test-reserve-company-cash",
        )
        db.commit()

    rejected = client.post(
        "/api/v1/companies",
        headers={**auth_headers, "Idempotency-Key": "company-create-insufficient"},
        json=_company_payload(client, auth_headers),
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "resource.insufficient"

    with SessionLocal() as db:
        profile = db.get(PlayerProfile, str(joined_profile["id"]))
        assert profile is not None
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            Decimal("30000.00"),
            reason="test_refund",
            reference_type="profile",
            reference_id=profile.id,
            idempotency_key="test-refund-company-cash",
        )
        db.commit()
    created = client.post(
        "/api/v1/companies",
        headers={**auth_headers, "Idempotency-Key": "company-create-owner"},
        json=_company_payload(client, auth_headers),
    )
    assert created.status_code == 201

    foreign_headers = _second_player_headers(client)
    foreign = client.post(
        f"/api/v1/companies/{created.json()['id']}/investments",
        headers={**foreign_headers, "Idempotency-Key": "foreign-company-investment"},
        json={"investment_type": "quality"},
    )
    assert foreign.status_code == 403
    assert foreign.json()["error"]["code"] == "company.not_owner"
