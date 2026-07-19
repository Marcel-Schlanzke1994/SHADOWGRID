from __future__ import annotations

from decimal import Decimal

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from shadowgrid.database import SessionLocal
from shadowgrid.domain import apply_profile_resource
from shadowgrid.models import LedgerEntry, PlayerProfile, ResourceBalance
from sqlalchemy import func, select


def test_initial_grant_is_exactly_once(client, auth_headers, joined_profile) -> None:
    profile_id = str(joined_profile["id"])
    db = SessionLocal()
    balance = db.get(ResourceBalance, profile_id)
    assert balance is not None
    assert balance.cash == Decimal("80000.00")
    assert balance.capital == Decimal("25000.00")
    assert balance.influence == Decimal("10.00")
    count = db.scalar(
        select(func.count())
        .select_from(LedgerEntry)
        .where(LedgerEntry.owner_id == profile_id, LedgerEntry.reason == "initial_grant")
    )
    assert count == 6
    db.close()


def test_duplicate_purchase_returns_same_business_and_single_booking(
    client, auth_headers, joined_profile
) -> None:
    districts = client.get("/api/v1/districts", headers=auth_headers).json()
    payload = {
        "business_type": "gastronomy",
        "district_id": districts[0]["id"],
        "name": "Ledger House",
    }
    headers = {**auth_headers, "Idempotency-Key": "business-purchase-0001"}
    first = client.post("/api/v1/businesses", headers=headers, json=payload)
    second = client.post("/api/v1/businesses", headers=headers, json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    db = SessionLocal()
    entries = list(
        db.scalars(
            select(LedgerEntry).where(
                LedgerEntry.owner_id == joined_profile["id"],
                LedgerEntry.reason == "business_purchase",
            )
        )
    )
    assert len(entries) == 1
    assert entries[0].amount == Decimal("-25000.00")
    db.close()


@given(st.lists(st.integers(min_value=-200, max_value=500), min_size=1, max_size=30))
@settings(
    max_examples=20,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture, HealthCheck.too_slow],
)
def test_ledger_balance_equals_sum_of_applied_deltas(joined_profile, deltas: list[int]) -> None:
    db = SessionLocal()
    profile = db.scalar(select(PlayerProfile))
    assert profile is not None
    starting = profile.resources.cash
    base_version = profile.resources.version
    accepted = Decimal("0")
    for index, delta in enumerate(deltas):
        if starting + accepted + delta < 0:
            continue
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            delta,
            reason="property_test",
            reference_type="test",
            reference_id=profile.id,
            idempotency_key=f"property-{base_version}-{index}",
        )
        accepted += Decimal(delta)
    db.commit()
    db.refresh(profile.resources)
    assert profile.resources.cash == starting + accepted
    db.close()
