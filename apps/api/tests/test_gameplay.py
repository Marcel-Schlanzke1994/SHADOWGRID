from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.domain import resolve_operation
from shadowgrid.models import Evidence, LedgerEntry, Operation
from sqlalchemy import select


def test_operation_is_server_authoritative_and_resolves_once(
    client, auth_headers, joined_profile
) -> None:
    districts = client.get("/api/v1/districts", headers=auth_headers).json()
    specialists = client.get("/api/v1/specialists", headers=auth_headers).json()
    payload = {
        "operation_type": "intelligence_gathering",
        "district_id": districts[0]["id"],
        "specialist_id": specialists[0]["id"],
        "target": "Fictional market signal",
        "budget": 2000,
        "intelligence_spend": 1,
        "risk_posture": "balanced",
        "secrecy": 60,
        "result": "critical_success",
    }
    response = client.post(
        "/api/v1/operations",
        headers={**auth_headers, "Idempotency-Key": "operation-start-0001"},
        json=payload,
    )
    assert response.status_code == 201
    assert response.json()["result"] is None
    db = SessionLocal()
    operation = db.get(Operation, response.json()["id"])
    assert operation is not None
    operation.finishes_at = datetime.now(UTC) - timedelta(seconds=1)
    db.commit()
    resolve_operation(db, operation, get_settings())
    first_result = operation.result
    first_outcome = operation.outcome_json
    db.commit()
    resolve_operation(db, operation, get_settings())
    db.commit()
    assert operation.result == first_result
    assert operation.outcome_json == first_outcome
    bookings = list(
        db.scalars(
            select(LedgerEntry).where(
                LedgerEntry.reference_id == operation.id, LedgerEntry.reason == "operation_result"
            )
        )
    )
    assert len({item.resource_type for item in bookings}) == len(bookings)
    db.close()


def test_operation_slot_and_specialist_ownership_are_enforced(
    client, auth_headers, joined_profile
) -> None:
    districts = client.get("/api/v1/districts", headers=auth_headers).json()
    specialists = client.get("/api/v1/specialists", headers=auth_headers).json()
    payload = {
        "operation_type": "business_expansion",
        "district_id": districts[0]["id"],
        "specialist_id": specialists[0]["id"],
        "target": "Local expansion",
        "budget": 1000,
        "intelligence_spend": 0,
        "risk_posture": "cautious",
        "secrecy": 70,
    }
    first = client.post(
        "/api/v1/operations",
        headers={**auth_headers, "Idempotency-Key": "slot-check-0001"},
        json=payload,
    )
    assert first.status_code == 201
    second = client.post(
        "/api/v1/operations",
        headers={**auth_headers, "Idempotency-Key": "slot-check-0002"},
        json=payload,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "operation.specialist_unavailable"


def test_investigation_never_exposes_actual_evidence_strength(
    client, auth_headers, joined_profile
) -> None:
    db = SessionLocal()
    profile_id = str(joined_profile["id"])
    profile = db.get(
        __import__("shadowgrid.models", fromlist=["PlayerProfile"]).PlayerProfile, profile_id
    )
    assert profile is not None
    profile.investigation_pressure = 75
    db.add(
        Evidence(
            profile_id=profile_id,
            evidence_type="digital_trace",
            strength=77,
            source_reference="hidden-test",
        )
    )
    db.commit()
    db.close()
    response = client.get("/api/v1/investigations", headers=auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert body["estimated"] is True
    assert body["known_signals"][0]["estimated_strength"] != 77
    assert "actual" not in response.text.lower()
