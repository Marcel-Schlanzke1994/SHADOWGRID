from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.models import (
    AuditLog,
    City,
    District,
    IntelligenceOperation,
    IntelligenceReport,
    IntelligenceReportOffer,
    Notification,
    PlayerProfile,
    ResourceBalance,
    Specialist,
    StrategicAction,
    StrategicEffect,
    User,
    World,
)
from shadowgrid.security import hash_password
from sqlalchemy import func, select

PASSWORD = "StrongPassword123"


def _create_player(
    client: TestClient,
    *,
    email: str,
    codename: str,
    cash: Decimal = Decimal("500000"),
    intelligence: Decimal = Decimal("500"),
    is_admin: bool = False,
) -> tuple[str, dict[str, str]]:
    with SessionLocal() as db:
        world = db.scalar(select(World))
        city = db.scalar(select(City))
        district = db.scalar(select(District))
        assert world is not None and city is not None and district is not None
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            display_name=codename,
            email_verified=True,
            is_admin=is_admin,
        )
        db.add(user)
        db.flush()
        profile = PlayerProfile(
            user_id=user.id,
            world_id=world.id,
            city_id=city.id,
            codename=codename,
            archetype="business_consortium",
            home_district_id=district.id,
            tutorial_step=7,
            protected_until=datetime.now(UTC) - timedelta(days=1),
        )
        db.add(profile)
        db.flush()
        db.add(
            ResourceBalance(
                profile_id=profile.id,
                cash=cash,
                capital=Decimal("250000"),
                influence=Decimal("500"),
                intelligence=intelligence,
                logistics_capacity=Decimal("100"),
                personnel_capacity=Decimal("100"),
            )
        )
        profile_id = profile.id
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    return profile_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _specialist(profile_id: str, name: str = "Analyst") -> str:
    with SessionLocal() as db:
        specialist = Specialist(
            profile_id=profile_id,
            name=name,
            role="market_analyst",
            level=5,
            energy=100,
            experience_points=0,
            skills_json={"analysis": 80, "leadership": 50},
            competence=80,
            loyalty=70,
            ambition=50,
            stress=0,
            exposure=0,
            salary=Decimal("1500"),
            salary_cents=150_000,
            status="hired",
            hired_at=datetime.now(UTC),
        )
        db.add(specialist)
        db.commit()
        db.refresh(specialist)
        return specialist.id


def _operation(
    client: TestClient,
    headers: dict[str, str],
    *,
    target_profile_id: str,
    specialist_id: str,
    key: str,
    information_type: str = "covert",
    category: str = "economy",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/intelligence/operations",
        headers={**headers, "Idempotency-Key": key},
        json={
            "target_profile_id": target_profile_id,
            "specialist_id": specialist_id,
            "information_type": information_type,
            "category": category,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_intelligence_success_idempotency_cooldown_resources_and_access(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_id, actor_headers = _create_player(
        client, email="intel-actor@example.com", codename="Intel Actor"
    )
    target_id, target_headers = _create_player(
        client, email="intel-target@example.com", codename="Intel Target"
    )
    specialist_id = _specialist(actor_id)
    monkeypatch.setattr(
        "shadowgrid.intelligence._rolls",
        lambda *_: ("a" * 64, 100, 9_999, 1),
    )

    operation = _operation(
        client,
        actor_headers,
        target_profile_id=target_id,
        specialist_id=specialist_id,
        key="intelligence-success-0001",
    )
    assert operation["outcome"] == "success"
    assert operation["detected"] is False
    duplicate = _operation(
        client,
        actor_headers,
        target_profile_id=target_id,
        specialist_id=specialist_id,
        key="intelligence-success-0001",
    )
    assert duplicate["id"] == operation["id"]

    reports = client.get("/api/v1/intelligence/reports", headers=actor_headers)
    assert reports.status_code == 200
    report = reports.json()[0]
    assert report["target_id"] == target_id
    assert report["confidence_bps"] == 8_000
    assert report["age_seconds"] >= 0
    denied = client.get(
        f"/api/v1/intelligence/reports/{report['id']}",
        headers=target_headers,
    )
    assert denied.status_code == 404

    cooldown = client.post(
        "/api/v1/intelligence/operations",
        headers={**actor_headers, "Idempotency-Key": "intelligence-cooldown-0002"},
        json={
            "target_profile_id": target_id,
            "specialist_id": specialist_id,
            "information_type": "covert",
            "category": "economy",
        },
    )
    assert cooldown.status_code == 409
    assert cooldown.json()["error"]["code"] == "intelligence.cooldown"

    poor_id, poor_headers = _create_player(
        client,
        email="intel-poor@example.com",
        codename="Intel Poor",
        cash=Decimal("0"),
        intelligence=Decimal("0"),
    )
    poor_specialist = _specialist(poor_id, "Poor Analyst")
    insufficient = client.post(
        "/api/v1/intelligence/operations",
        headers={**poor_headers, "Idempotency-Key": "intelligence-poor-0001"},
        json={
            "target_profile_id": target_id,
            "specialist_id": poor_specialist,
            "information_type": "covert",
            "category": "companies",
        },
    )
    assert insufficient.status_code == 409
    assert insufficient.json()["error"]["code"] == "resource.insufficient"

    with SessionLocal() as db:
        balance = db.get(ResourceBalance, actor_id)
        assert balance is not None
        assert balance.cash == Decimal("499250.00")
        assert balance.intelligence == Decimal("470.00")
        assert (
            db.scalar(
                select(func.count())
                .select_from(IntelligenceOperation)
                .where(IntelligenceOperation.actor_profile_id == actor_id)
            )
            == 1
        )
        stored = db.get(IntelligenceReport, report["id"])
        assert stored is not None
        assert stored.accuracy_state == "correct"
        stored.statement = "Mutation must fail"
        with pytest.raises(ValueError, match="immutable"):
            db.flush()


def test_partial_false_detection_expiry_and_admin_trace(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    admin_id, admin_headers = _create_player(
        client,
        email="intel-admin@example.com",
        codename="Intel Admin",
        is_admin=True,
    )
    target_id, target_headers = _create_player(
        client,
        email="intel-detected@example.com",
        codename="Detected Target",
    )
    specialist_id = _specialist(admin_id)

    def deterministic_rolls(_: str, __: str, key: str) -> tuple[str, int, int, int]:
        if key == "intelligence-partial-0001":
            return "b" * 64, 8_500, 9_999, 2
        return "c" * 64, 9_999, 0, 3

    monkeypatch.setattr("shadowgrid.intelligence._rolls", deterministic_rolls)
    partial = _operation(
        client,
        admin_headers,
        target_profile_id=target_id,
        specialist_id=specialist_id,
        key="intelligence-partial-0001",
        information_type="analyzed",
        category="economy",
    )
    assert partial["outcome"] == "partial"
    failure = _operation(
        client,
        admin_headers,
        target_profile_id=target_id,
        specialist_id=specialist_id,
        key="intelligence-failure-0002",
        information_type="covert",
        category="companies",
    )
    assert failure["outcome"] == "failure"
    assert failure["detected"] is True

    admin_trace = client.get("/api/v1/admin/intelligence/operations", headers=admin_headers)
    assert admin_trace.status_code == 200
    assert {item["outcome"] for item in admin_trace.json()} >= {"partial", "failure"}
    failure_admin = client.get(
        f"/api/v1/admin/intelligence/reports/{failure['report_id']}",
        headers=admin_headers,
    )
    assert failure_admin.status_code == 200
    assert failure_admin.json()["accuracy_state"] == "intentionally_misleading"
    forbidden_admin = client.get(
        f"/api/v1/admin/intelligence/reports/{failure['report_id']}",
        headers=target_headers,
    )
    assert forbidden_admin.status_code == 403

    with SessionLocal() as db:
        partial_report = db.get(IntelligenceReport, partial["report_id"])
        assert partial_report is not None
        assert partial_report.accuracy_state in {"incomplete", "outdated"}
        notification = db.scalar(
            select(Notification)
            .join(User, User.id == Notification.user_id)
            .where(User.email == "intel-detected@example.com")
            .order_by(Notification.created_at.desc())
        )
        assert notification is not None
        assert notification.event_type == "intelligence.activity_detected"
        assert admin_id not in notification.body
        expired = IntelligenceReport(
            world_id=partial_report.world_id,
            owner_profile_id=admin_id,
            target_type="profile",
            target_id=target_id,
            information_type="public",
            category="reputation",
            statement="An expired public assessment.",
            confidence_bps=5_000,
            accuracy_state="outdated",
            source_category="public_registry",
            snapshot_json={},
            tradable=True,
            observed_at=datetime.now(UTC) - timedelta(days=2),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.add(expired)
        db.commit()
        expired_id = expired.id
    rejected = client.post(
        f"/api/v1/intelligence/reports/{expired_id}/sell",
        headers={**admin_headers, "Idempotency-Key": "expired-report-offer"},
        json={"price_cents": 10_000, "expires_in_hours": 24},
    )
    assert rejected.status_code == 409
    assert rejected.json()["error"]["code"] == "intelligence.report_not_tradable"


def test_report_trade_creates_balanced_immutable_buyer_copy(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seller_id, seller_headers = _create_player(
        client, email="intel-seller@example.com", codename="Intel Seller"
    )
    buyer_id, buyer_headers = _create_player(
        client, email="intel-buyer@example.com", codename="Intel Buyer"
    )
    target_id, _ = _create_player(
        client, email="intel-trade-target@example.com", codename="Trade Target"
    )
    specialist_id = _specialist(seller_id)
    monkeypatch.setattr(
        "shadowgrid.intelligence._rolls",
        lambda *_: ("d" * 64, 100, 9_999, 0),
    )
    operation = _operation(
        client,
        seller_headers,
        target_profile_id=target_id,
        specialist_id=specialist_id,
        key="intelligence-trade-source",
        information_type="analyzed",
        category="exchange",
    )
    report_id = str(operation["report_id"])
    offer_response = client.post(
        f"/api/v1/intelligence/reports/{report_id}/sell",
        headers={**seller_headers, "Idempotency-Key": "intelligence-offer-0001"},
        json={"price_cents": 123_400, "expires_in_hours": 12},
    )
    assert offer_response.status_code == 201, offer_response.text
    offer_id = offer_response.json()["id"]
    purchase = client.post(
        f"/api/v1/intelligence/offers/{offer_id}/buy",
        headers={**buyer_headers, "Idempotency-Key": "intelligence-purchase-0001"},
    )
    assert purchase.status_code == 200, purchase.text
    copied = purchase.json()
    assert copied["source_report_id"] == report_id
    assert copied["owner_profile_id"] == buyer_id
    assert copied["tradable"] is False
    duplicate = client.post(
        f"/api/v1/intelligence/offers/{offer_id}/buy",
        headers={**buyer_headers, "Idempotency-Key": "intelligence-purchase-0001"},
    )
    assert duplicate.status_code == 200
    assert duplicate.json()["id"] == copied["id"]
    cannot_resell = client.post(
        f"/api/v1/intelligence/reports/{copied['id']}/sell",
        headers={**buyer_headers, "Idempotency-Key": "buyer-resell-forbidden"},
        json={"price_cents": 200_000, "expires_in_hours": 12},
    )
    assert cannot_resell.status_code == 409

    with SessionLocal() as db:
        seller_balance = db.get(ResourceBalance, seller_id)
        buyer_balance = db.get(ResourceBalance, buyer_id)
        source = db.get(IntelligenceReport, report_id)
        stored_copy = db.get(IntelligenceReport, copied["id"])
        offer = db.get(IntelligenceReportOffer, offer_id)
        assert seller_balance is not None and buyer_balance is not None
        assert seller_balance.cash == Decimal("500984.00")
        assert buyer_balance.cash == Decimal("498766.00")
        assert source is not None and stored_copy is not None and offer is not None
        assert stored_copy.statement == source.statement
        assert stored_copy.snapshot_json == source.snapshot_json
        assert offer.status == "sold"
        stored_copy.confidence_bps = 1
        with pytest.raises(ValueError, match="immutable"):
            db.flush()


def test_strategic_action_effect_detection_idempotency_and_cooldown(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    actor_id, actor_headers = _create_player(
        client, email="strategy-actor@example.com", codename="Strategy Actor"
    )
    target_id, target_headers = _create_player(
        client, email="strategy-target@example.com", codename="Strategy Target"
    )
    specialist_id = _specialist(actor_id)
    monkeypatch.setattr(
        "shadowgrid.intelligence._rolls",
        lambda *_: ("e" * 64, 100, 0, 0),
    )
    payload = {
        "target_profile_id": target_id,
        "specialist_id": specialist_id,
        "action_type": "make_information_unreliable",
        "target_id": target_id,
    }
    created = client.post(
        "/api/v1/strategic-actions",
        headers={**actor_headers, "Idempotency-Key": "strategic-action-0001"},
        json=payload,
    )
    assert created.status_code == 201, created.text
    assert created.json()["outcome"] == "success"
    assert created.json()["detected"] is True
    duplicate = client.post(
        "/api/v1/strategic-actions",
        headers={**actor_headers, "Idempotency-Key": "strategic-action-0001"},
        json=payload,
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == created.json()["id"]
    cooldown = client.post(
        "/api/v1/strategic-actions",
        headers={**actor_headers, "Idempotency-Key": "strategic-action-0002"},
        json=payload,
    )
    assert cooldown.status_code == 409
    assert cooldown.json()["error"]["code"] == "strategic.cooldown"
    victim_effects = client.get(
        "/api/v1/strategic-actions/effects/me",
        headers=target_headers,
    )
    assert victim_effects.status_code == 200
    assert victim_effects.json()[0]["effect_type"] == "information_reliability_penalty"
    assert "source_profile_id" not in victim_effects.json()[0]

    with SessionLocal() as db:
        action = db.get(StrategicAction, created.json()["id"])
        effect = db.get(StrategicEffect, created.json()["effect_id"])
        assert action is not None and effect is not None
        assert effect.target_profile_id == target_id
        assert effect.magnitude == 1_500
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "strategic.action_resolved")
            )
            == 1
        )
        action.outcome = "failure"
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
