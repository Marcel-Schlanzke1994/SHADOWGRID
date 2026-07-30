from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from shadowgrid.companies import create_company
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.economy import run_economy_tick
from shadowgrid.models import (
    AuditLog,
    City,
    CompanyEconomyReport,
    District,
    PlayerProfile,
    RealtimeEvent,
    ResourceBalance,
    User,
    World,
    WorldEventDefinition,
    WorldEventInstance,
)
from shadowgrid.security import hash_password
from shadowgrid.world_events import (
    activate_event,
    advance_world_events,
    market_event_modifiers,
    seed_event_definitions,
)
from sqlalchemy import func, select

PASSWORD = "StrongPassword123"


def _create_player(
    client: TestClient,
    *,
    email: str,
    codename: str,
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
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    return profile_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _seed_definitions() -> tuple[str, str]:
    with SessionLocal() as db:
        definitions = seed_event_definitions(db)
        world = db.scalar(select(World))
        city = db.scalar(select(City))
        assert world is not None and city is not None
        assert len(definitions) == 5
        db.commit()
        return world.id, city.id


def test_admin_preview_activation_safe_end_rbac_and_immutability(
    client: TestClient,
) -> None:
    _, admin_headers = _create_player(
        client,
        email="events-admin@example.com",
        codename="Event Admin",
        is_admin=True,
    )
    _, player_headers = _create_player(
        client,
        email="events-player@example.com",
        codename="Event Player",
    )
    world_id, city_id = _seed_definitions()
    payload = {
        "world_id": world_id,
        "event_key": "port_strike",
        "version": 1,
        "scope_type": "city",
        "scope_id": city_id,
        "starts_at": (datetime.now(UTC) - timedelta(minutes=1)).isoformat(),
        "duration_minutes": 120,
        "effect_overrides": {"cost_multiplier_bps": 12_000},
    }
    preview = client.post(
        "/api/v1/admin/world-events/preview",
        headers=admin_headers,
        json=payload,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["affected_companies"] == 0
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(WorldEventInstance)) == 0

    forbidden = client.post(
        "/api/v1/admin/world-events/activate",
        headers={**player_headers, "Idempotency-Key": "event-forbidden-0001"},
        json=payload,
    )
    assert forbidden.status_code == 403
    activated = client.post(
        "/api/v1/admin/world-events/activate",
        headers={**admin_headers, "Idempotency-Key": "event-activate-0001"},
        json=payload,
    )
    assert activated.status_code == 201, activated.text
    assert activated.json()["status"] == "active"
    duplicate = client.post(
        "/api/v1/admin/world-events/activate",
        headers={**admin_headers, "Idempotency-Key": "event-activate-0001"},
        json=payload,
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == activated.json()["id"]
    feed = client.get("/api/v1/world-events/current", headers=player_headers)
    assert feed.status_code == 200
    assert feed.json()[0]["event_key"] == "port_strike"

    ended = client.post(
        f"/api/v1/admin/world-events/{activated.json()['id']}/end",
        headers={**admin_headers, "Idempotency-Key": "event-end-0001"},
        json={"reason": "Local administrator ended the simulation."},
    )
    assert ended.status_code == 200
    assert ended.json()["status"] == "ended"
    repeated_end = client.post(
        f"/api/v1/admin/world-events/{activated.json()['id']}/end",
        headers={**admin_headers, "Idempotency-Key": "event-end-0001"},
        json={"reason": "Local administrator ended the simulation."},
    )
    assert repeated_end.status_code == 200
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(RealtimeEvent.world_id == world_id)
            )
            == 2
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action.in_(("world_event.activated", "world_event.ended")))
            )
            == 2
        )
        instance = db.get(WorldEventInstance, activated.json()["id"])
        definition = db.scalar(
            select(WorldEventDefinition).where(WorldEventDefinition.event_key == "port_strike")
        )
        assert instance is not None and definition is not None
        instance.effect_config_json = {"cost_multiplier_bps": 30_000}
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()
        definition = db.scalar(
            select(WorldEventDefinition).where(WorldEventDefinition.event_key == "port_strike")
        )
        assert definition is not None
        definition.enabled = False
        db.commit()
    disabled = client.post(
        "/api/v1/admin/world-events/activate",
        headers={**admin_headers, "Idempotency-Key": "event-disabled-0002"},
        json=payload,
    )
    assert disabled.status_code == 409
    assert disabled.json()["error"]["code"] == "world_event.definition_disabled"


def test_overlapping_events_compose_in_order_and_clamp_hard_bounds(
    client: TestClient,
) -> None:
    admin_profile_id, _ = _create_player(
        client,
        email="events-overlap@example.com",
        codename="Overlap Admin",
        is_admin=True,
    )
    world_id, city_id = _seed_definitions()
    now = datetime.now(UTC)
    with SessionLocal() as db:
        admin_profile = db.get(PlayerProfile, admin_profile_id)
        assert admin_profile is not None
        admin = db.get(User, admin_profile.user_id)
        assert admin is not None
        common = {
            "revenue_multiplier_bps": 30_000,
            "cost_multiplier_bps": 2_500,
            "reputation_delta_bps": 4_000,
            "investigation_pressure_delta": 80,
        }
        first = activate_event(
            db,
            admin=admin,
            world_id=world_id,
            event_key="technology_boom",
            version=1,
            scope_type="world",
            scope_id=None,
            starts_at=now - timedelta(minutes=2),
            duration_minutes=120,
            effect_overrides=common,
            idempotency_key="event-overlap-first",
            request_id="overlap-first",
        )
        second = activate_event(
            db,
            admin=admin,
            world_id=world_id,
            event_key="data_leak",
            version=1,
            scope_type="world",
            scope_id=None,
            starts_at=now - timedelta(minutes=1),
            duration_minutes=120,
            effect_overrides=common,
            idempotency_key="event-overlap-second",
            request_id="overlap-second",
        )
        db.commit()
        modifiers = market_event_modifiers(
            db,
            world_id=world_id,
            city_id=city_id,
            industry="technology",
            at=now,
        )
        assert modifiers.event_instance_ids == (first.id, second.id)
        assert modifiers.revenue_multiplier_bps == 30_000
        assert modifiers.cost_multiplier_bps == 2_500
        assert modifiers.reputation_delta_bps == 5_000
        assert modifiers.investigation_pressure_delta == 100

    invalid = client.post(
        "/api/v1/admin/world-events/preview",
        headers=_login_headers(client, "events-overlap@example.com"),
        json={
            "world_id": world_id,
            "event_key": "data_leak",
            "scope_type": "world",
            "starts_at": now.isoformat(),
            "duration_minutes": 60,
            "effect_overrides": {"revenue_multiplier_bps": 30_001},
        },
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "world_event.effect_out_of_bounds"


def _login_headers(client: TestClient, email: str) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_event_scheduler_start_expiry_and_repeated_run_are_idempotent(
    client: TestClient,
) -> None:
    profile_id, _ = _create_player(
        client,
        email="events-scheduler@example.com",
        codename="Scheduler Admin",
        is_admin=True,
    )
    world_id, _ = _seed_definitions()
    now = datetime.now(UTC)
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        assert profile is not None
        admin = db.get(User, profile.user_id)
        assert admin is not None
        instance = activate_event(
            db,
            admin=admin,
            world_id=world_id,
            event_key="data_leak",
            version=1,
            scope_type="world",
            scope_id=None,
            starts_at=now + timedelta(minutes=5),
            duration_minutes=10,
            effect_overrides=None,
            idempotency_key="event-scheduler-0001",
            request_id="scheduler-create",
        )
        db.commit()
        assert instance.status == "scheduled"
        assert advance_world_events(db, now + timedelta(minutes=6)) == {
            "started": 1,
            "ended": 0,
        }
        assert advance_world_events(db, now + timedelta(minutes=6)) == {
            "started": 0,
            "ended": 0,
        }
        assert advance_world_events(db, now + timedelta(minutes=16)) == {
            "started": 0,
            "ended": 1,
        }
        assert advance_world_events(db, now + timedelta(minutes=16)) == {
            "started": 0,
            "ended": 0,
        }
        stored = db.get(WorldEventInstance, instance.id)
        assert stored is not None and stored.status == "ended"
        assert (
            db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(RealtimeEvent.world_id == world_id)
            )
            == 2
        )


def test_active_event_modifiers_are_recorded_in_company_economy_report(
    client: TestClient,
) -> None:
    profile_id, _ = _create_player(
        client,
        email="events-economy@example.com",
        codename="Economy Admin",
        is_admin=True,
    )
    world_id, _ = _seed_definitions()
    now = datetime.now(UTC)
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        district = db.scalar(select(District))
        assert profile is not None and district is not None
        company = create_company(
            db,
            profile,
            name="Event Systems GmbH",
            industry="technology",
            district_id=district.id,
            idempotency_key="event-company-create",
            settings=get_settings(),
            request_id="event-company-create",
        )
        admin = db.get(User, profile.user_id)
        assert admin is not None
        activate_event(
            db,
            admin=admin,
            world_id=world_id,
            event_key="technology_boom",
            version=1,
            scope_type="industry",
            scope_id="technology",
            starts_at=now - timedelta(minutes=5),
            duration_minutes=120,
            effect_overrides={
                "revenue_multiplier_bps": 12_000,
                "cost_multiplier_bps": 13_000,
                "demand_multiplier_bps": 11_000,
            },
            idempotency_key="event-economy-active",
            request_id="event-economy-active",
        )
        db.commit()
        run_economy_tick(db, world_id, at=now)
        report = db.scalar(
            select(CompanyEconomyReport).where(CompanyEconomyReport.company_id == company.id)
        )
        assert report is not None
        assert report.modifiers_json["event_instance_count"] == 1
        assert report.modifiers_json["event_revenue_multiplier_bps"] == 12_000
        assert report.modifiers_json["event_cost_multiplier_bps"] == 13_000
        assert report.modifiers_json["event_demand_multiplier_bps"] == 11_000
