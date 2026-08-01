from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.engagement import record_engagement_event
from shadowgrid.models import (
    CartelChronicleEntry,
    City,
    District,
    MasteryEntry,
    MasteryProgress,
    PlayerProfile,
    ResourceBalance,
    User,
    World,
)
from shadowgrid.security import hash_password
from sqlalchemy import func, select

PASSWORD = "StrongPassword123"


def _create_player(client: TestClient, email: str, codename: str) -> tuple[str, dict[str, str]]:
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
            protected_until=datetime.now(UTC) + timedelta(days=3),
        )
        db.add(profile)
        db.flush()
        db.add(
            ResourceBalance(
                profile_id=profile.id,
                cash=Decimal("500000"),
                capital=Decimal("250000"),
                influence=Decimal("500"),
                intelligence=Decimal("500"),
                logistics_capacity=Decimal("100"),
                personnel_capacity=Decimal("100"),
            )
        )
        profile_id = profile.id
        db.commit()
    login = client.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert login.status_code == 200
    return profile_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _record(profile_id: str, event_type: str, suffix: str) -> None:
    with SessionLocal() as db:
        record_engagement_event(
            db,
            profile_id=profile_id,
            event_type=event_type,
            source_type="progression_test",
            source_id=suffix,
            idempotency_key=f"progression:{profile_id}:{suffix}",
        )
        db.commit()


def test_doctrine_is_reversible_and_learning_rewards_diverse_decisions(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    catalog = client.get("/api/v1/engagement/doctrines", headers=auth_headers)
    assert catalog.status_code == 200
    assert len(catalog.json()) == 7
    assert all(not item["economic_bonus"] and item["reversible"] for item in catalog.json())

    first = client.put(
        "/api/v1/engagement/doctrine",
        headers={**auth_headers, "Idempotency-Key": "doctrine-first"},
        json={"doctrine_key": "industrial_captain"},
    )
    changed = client.put(
        "/api/v1/engagement/doctrine",
        headers={**auth_headers, "Idempotency-Key": "doctrine-change"},
        json={"doctrine_key": "networker"},
    )
    assert first.status_code == changed.status_code == 200
    assert changed.json()["doctrine_key"] == "networker"
    assert changed.json()["version"] == 2

    profile_id = str(joined_profile["id"])
    _record(profile_id, "company.founded", "company-one")
    _record(profile_id, "company.founded", "company-two")
    _record(profile_id, "company.founded", "company-three")
    mastery = client.get("/api/v1/engagement/mastery", headers=auth_headers)
    assert mastery.status_code == 200
    company = next(item for item in mastery.json() if item["area_key"] == "company_management")
    assert company["points"] == 35
    with SessionLocal() as db:
        awarded = list(
            db.scalars(
                select(MasteryEntry)
                .where(MasteryEntry.profile_id == profile_id)
                .order_by(MasteryEntry.created_at)
            )
        )
        assert [item.diversity_bps for item in awarded] == [10_000, 5_000, 2_500]

    reports = client.get("/api/v1/engagement/outcome-reports", headers=auth_headers)
    assert reports.status_code == 200
    assert len(reports.json()) == 3
    assert reports.json()[0]["controllable_factors_json"]
    assert reports.json()[0]["external_factors_json"]


def test_adaptive_help_is_optional_and_success_chain_never_resets(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    offers = client.get("/api/v1/engagement/adaptive-help", headers=auth_headers)
    assert offers.status_code == 200
    if offers.json():
        dismissed = client.patch(
            f"/api/v1/engagement/adaptive-help/{offers.json()[0]['id']}",
            headers=auth_headers,
            json={"status": "dismissed"},
        )
        assert dismissed.status_code == 200
    disabled = client.put(
        "/api/v1/engagement/settings",
        headers=auth_headers,
        json={
            "adaptive_help_enabled": False,
            "session_summary_enabled": True,
            "ranking_visible": True,
            "information_density": "standard",
        },
    )
    assert disabled.status_code == 200
    assert client.get("/api/v1/engagement/adaptive-help", headers=auth_headers).json() == []

    profile_id = str(joined_profile["id"])
    for event_type, suffix in zip(
        ("company.founded", "company.first_profit", "specialist.assigned"),
        ("founded", "profit", "specialist"),
        strict=True,
    ):
        _record(profile_id, event_type, suffix)
    chain = client.get("/api/v1/engagement/success-chain", headers=auth_headers)
    assert chain.status_code == 200
    assert chain.json()["status"] == "completed"
    assert chain.json()["completed_steps"] == chain.json()["total_steps"] == 3


def test_mentoring_rewards_verified_learning_not_recruitment(client: TestClient) -> None:
    mentor_id, mentor_headers = _create_player(client, "mentor@example.com", "Verified Mentor")
    mentee_id, mentee_headers = _create_player(client, "mentee@example.com", "Independent Mentee")
    _record(mentor_id, "company.founded", "mentor-experience")
    proposed = client.post(
        "/api/v1/engagement/mentorships",
        headers={**mentor_headers, "Idempotency-Key": "mentorship-proposal"},
        json={"mentee_profile_id": mentee_id},
    )
    assert proposed.status_code == 200, proposed.text
    mentorship_id = proposed.json()["id"]
    with SessionLocal() as db:
        before = int(
            db.scalar(
                select(func.coalesce(func.sum(MasteryProgress.points), 0)).where(
                    MasteryProgress.profile_id == mentor_id
                )
            )
            or 0
        )
    accepted = client.post(
        f"/api/v1/engagement/mentorships/{mentorship_id}/answer",
        headers=mentee_headers,
        json={"accept": True},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "active"
    with SessionLocal() as db:
        after_recruitment = int(
            db.scalar(
                select(func.coalesce(func.sum(MasteryProgress.points), 0)).where(
                    MasteryProgress.profile_id == mentor_id
                )
            )
            or 0
        )
    assert after_recruitment == before

    _record(mentee_id, "company.founded", "mentee-company")
    _record(mentee_id, "specialist.assigned", "mentee-specialist")
    _record(mentee_id, "intelligence.report_acquired", "mentee-intelligence")
    completed = client.post(
        f"/api/v1/engagement/mentorships/{mentorship_id}/refresh",
        headers=mentee_headers,
        json={"positive_feedback": True},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert set(completed.json()["milestones"]) == {
        "system_understood",
        "independent_decision",
        "positive_feedback",
    }


def test_cartel_delegation_private_pause_and_shared_chronicle(client: TestClient) -> None:
    leader_id, leader_headers = _create_player(client, "social-leader@example.com", "Social Leader")
    member_id, member_headers = _create_player(client, "social-member@example.com", "Social Member")
    created = client.post(
        "/api/v1/cartels",
        headers={**leader_headers, "Idempotency-Key": "social-cartel"},
        json={
            "name": "Async Collective",
            "tag": "ASY",
            "archetype": "business_consortium",
            "description": "Flexible collaboration",
            "governance_model": "directorate",
        },
    )
    assert created.status_code == 201, created.text
    cartel_id = created.json()["id"]
    invitation = client.post(
        f"/api/v1/cartels/{cartel_id}/invitations",
        headers={**leader_headers, "Idempotency-Key": "social-invite"},
        json={"email": "social-member@example.com"},
    )
    joined = client.post(
        f"/api/v1/cartels/{cartel_id}/join",
        headers={**member_headers, "Idempotency-Key": "social-join"},
        json={"invitation_id": invitation.json()["id"]},
    )
    assert invitation.status_code == 201 and joined.status_code == 200

    delegation = client.post(
        f"/api/v1/engagement/social/cartels/{cartel_id}/delegations",
        headers={**leader_headers, "Idempotency-Key": "social-delegation"},
        json={
            "delegate_profile_id": member_id,
            "role_key": "project_manager",
            "duration_days": 7,
        },
    )
    assert delegation.status_code == 200, delegation.text
    assert "projects.create" in delegation.json()["permissions_json"]

    paused = client.post(
        f"/api/v1/engagement/social/cartels/{cartel_id}/pause",
        headers={**member_headers, "Idempotency-Key": "social-pause"},
        json={"duration_days": 30, "private_reason": "Private life"},
    )
    assert paused.status_code == 200
    members = client.get(f"/api/v1/cartels/{cartel_id}/members", headers=leader_headers)
    member = next(item for item in members.json() if item["profile_id"] == member_id)
    assert member["status"] == "active"
    chronicle = client.get(
        f"/api/v1/engagement/social/cartels/{cartel_id}/chronicle",
        headers=member_headers,
    )
    assert chronicle.status_code == 200
    assert any(item["entry_type"] == "delegation_created" for item in chronicle.json())
    assert all("pause" not in item["entry_type"] for item in chronicle.json())
    with SessionLocal() as db:
        entry = db.scalar(select(CartelChronicleEntry))
        assert entry is not None
        entry.title_key = "tampered"
        try:
            db.commit()
        except ValueError:
            db.rollback()
        else:
            raise AssertionError("Cartel chronicle mutation unexpectedly succeeded")
    resumed = client.post(
        f"/api/v1/engagement/social/cartels/{cartel_id}/resume",
        headers=member_headers,
    )
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "completed"
    assert leader_id != member_id


def test_mastery_entries_are_immutable(
    client: TestClient,
    joined_profile: dict[str, object],
) -> None:
    _record(str(joined_profile["id"]), "company.founded", "immutable-mastery")
    with SessionLocal() as db:
        entry = db.scalar(select(MasteryEntry))
        assert entry is not None
        entry.points += 1
        try:
            db.commit()
        except ValueError:
            db.rollback()
        else:
            raise AssertionError("Mastery entry mutation unexpectedly succeeded")
