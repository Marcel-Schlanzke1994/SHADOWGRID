from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.engagement import record_engagement_event
from shadowgrid.models import (
    CollectionItem,
    EngagementEvent,
    NarrativeChronicleEntry,
    PlayerProfile,
    ReturnContract,
    Season,
    World,
    WorldEventDefinition,
    WorldEventInstance,
)
from shadowgrid.seasons import create_season_from_template, seed_season_template
from sqlalchemy import func, select


def _record(
    profile_id: str,
    event_type: str,
    source_id: str,
    *,
    payload: dict[str, object] | None = None,
) -> None:
    with SessionLocal() as db:
        record_engagement_event(
            db,
            profile_id=profile_id,
            event_type=event_type,
            source_type="legacy_test",
            source_id=source_id,
            idempotency_key=f"legacy:{profile_id}:{event_type}:{source_id}",
            payload=payload,
        )
        db.commit()


def _create_company(client: TestClient, headers: dict[str, str], suffix: str) -> dict[str, object]:
    district = client.get("/api/v1/districts", headers=headers).json()[0]
    response = client.post(
        "/api/v1/companies",
        headers={**headers, "Idempotency-Key": f"legacy-company-{suffix}"},
        json={
            "name": f"Legacy Works {suffix}",
            "industry": "technology",
            "district_id": district["id"],
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _seed_world_event(profile_id: str) -> str:
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        assert profile is not None
        definition = WorldEventDefinition(
            event_key="legacy_signal",
            version=1,
            title="Legacy signal",
            description="A persistent city signal",
            default_scope_type="world",
            default_duration_minutes=60,
        )
        db.add(definition)
        db.flush()
        now = datetime.now(UTC)
        instance = WorldEventInstance(
            world_id=profile.world_id,
            definition_id=definition.id,
            event_key=definition.event_key,
            template_version=definition.version,
            title=definition.title,
            description=definition.description,
            status="active",
            scope_type="world",
            scope_id=profile.world_id,
            idempotency_key="legacy-world-event",
            activated_by_user_id=profile.user_id,
            starts_at=now,
            ends_at=now + timedelta(hours=1),
            activated_at=now,
        )
        db.add(instance)
        db.commit()
        return instance.id


def _seed_season() -> str:
    with SessionLocal() as db:
        world = db.scalar(select(World))
        assert world is not None
        template = seed_season_template(db, get_settings())
        season = create_season_from_template(
            db,
            world=world,
            template=template,
            starts_at=datetime.now(UTC),
            idempotency_key="legacy-season",
        )
        return season.id


def test_company_history_actors_collection_and_identity_are_persistent(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    company = _create_company(client, auth_headers, "one")
    actors = client.get("/api/v1/engagement/legacy/actors", headers=auth_headers)
    assert actors.status_code == 200
    entrepreneur = next(item for item in actors.json() if item["actor_key"] == "mara_voss")
    assert entrepreneur["interaction_count"] == 1
    assert entrepreneur["trust"] > 0
    assert entrepreneur["information_access"] > 0

    chronicle = client.get(
        f"/api/v1/engagement/legacy/chronicles/company/{company['id']}",
        headers=auth_headers,
    )
    assert chronicle.status_code == 200
    assert chronicle.json()[0]["entry_type"] == "foundation"
    assert chronicle.json()[0]["cause_keys_json"]
    assert chronicle.json()[0]["impact_keys_json"]

    collection = client.get("/api/v1/engagement/legacy/collection", headers=auth_headers)
    founder_title = next(
        item for item in collection.json() if item["item_key"] == "company_founder_title"
    )
    identity = client.put(
        "/api/v1/engagement/legacy/identity",
        headers=auth_headers,
        json={
            "title_item_id": founder_title["item_id"],
            "emblem_item_id": None,
            "hq_cosmetic_item_id": None,
            "profile_card_public": False,
        },
    )
    assert identity.status_code == 200
    assert identity.json()["active_title_item_id"] == founder_title["item_id"]
    assert identity.json()["profile_card_public"] is False

    with SessionLocal() as db:
        unowned = CollectionItem(
            item_key="unowned_test_title",
            item_type="title",
            title_key="testTitle",
            description_key="testDescription",
        )
        db.add(unowned)
        db.commit()
        unowned_id = unowned.id
    rejected = client.put(
        "/api/v1/engagement/legacy/identity",
        headers=auth_headers,
        json={
            "title_item_id": unowned_id,
            "emblem_item_id": None,
            "hq_cosmetic_item_id": None,
            "profile_card_public": True,
        },
    )
    assert rejected.status_code == 403

    with SessionLocal() as db:
        entry = db.scalar(select(NarrativeChronicleEntry))
        assert entry is not None
        entry.title_key = "tampered"
        try:
            db.commit()
        except ValueError:
            db.rollback()
        else:
            raise AssertionError("Narrative chronicle mutation unexpectedly succeeded")
    assert str(joined_profile["id"])


def test_dossier_investigation_is_idempotent_and_guarantees_rare_clue(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    _seed_world_event(str(joined_profile["id"]))
    dossier_response = client.get("/api/v1/engagement/legacy/dossiers", headers=auth_headers)
    assert dossier_response.status_code == 200
    dossier = dossier_response.json()[0]
    first = client.post(
        f"/api/v1/engagement/legacy/dossiers/{dossier['id']}/investigate",
        headers={**auth_headers, "Idempotency-Key": "dossier-investigation-1"},
    )
    repeated = client.post(
        f"/api/v1/engagement/legacy/dossiers/{dossier['id']}/investigate",
        headers={**auth_headers, "Idempotency-Key": "dossier-investigation-1"},
    )
    assert first.status_code == repeated.status_code == 200
    assert repeated.json()["investigation_count"] == 1
    result = repeated
    for attempt in range(2, 6):
        result = client.post(
            f"/api/v1/engagement/legacy/dossiers/{dossier['id']}/investigate",
            headers={**auth_headers, "Idempotency-Key": f"dossier-investigation-{attempt}"},
        )
        assert result.status_code == 200, result.text
    assert result.json()["investigation_count"] == 5
    assert any(clue["rare"] and clue["discovered"] for clue in result.json()["clues"])
    assert result.json()["completed_at"] is not None
    after_completion = client.post(
        f"/api/v1/engagement/legacy/dossiers/{dossier['id']}/investigate",
        headers={**auth_headers, "Idempotency-Key": "dossier-investigation-after-complete"},
    )
    assert after_completion.status_code == 200
    assert after_completion.json()["investigation_count"] == 5
    collection = client.get("/api/v1/engagement/legacy/collection", headers=auth_headers).json()
    assert any(item["item_key"] == "rare_city_signal" for item in collection)


def test_optional_season_goals_are_limited_and_progress_server_side(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    season_id = _seed_season()
    offered = client.get("/api/v1/engagement/legacy/season-goals", headers=auth_headers)
    assert offered.status_code == 200
    assert len(offered.json()) == 5
    selected = []
    for goal in offered.json()[:3]:
        response = client.post(
            f"/api/v1/engagement/legacy/season-goals/{goal['id']}/select",
            headers=auth_headers,
        )
        assert response.status_code == 200
        selected.append(response.json())
    fourth = client.post(
        f"/api/v1/engagement/legacy/season-goals/{offered.json()[3]['id']}/select",
        headers=auth_headers,
    )
    assert fourth.status_code == 409

    economic = next(item for item in selected if item["goal_key"] == "economic_resilience")
    for index in range(3):
        _record(str(joined_profile["id"]), "company.first_profit", f"profit-{index}")
    refreshed = client.get("/api/v1/engagement/legacy/season-goals", headers=auth_headers).json()
    completed = next(item for item in refreshed if item["id"] == economic["id"])
    assert completed["status"] == "completed"
    assert completed["progress_value"] == completed["target_value"] == 3
    with SessionLocal() as db:
        season = db.get(Season, season_id)
        assert season is not None and season.status == "active"


def test_return_contracts_and_parallel_rankings_add_no_economic_reward(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    profile_id = str(joined_profile["id"])
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        assert profile is not None
        profile.created_at = datetime.now(UTC) - timedelta(days=12)
        assert (
            db.scalar(
                select(func.count())
                .select_from(EngagementEvent)
                .where(EngagementEvent.profile_id == profile_id)
            )
            == 0
        )
        db.commit()
    contracts = client.post("/api/v1/engagement/legacy/return-contracts", headers=auth_headers)
    assert contracts.status_code == 200
    assert len(contracts.json()) == 3
    chosen = next(item for item in contracts.json() if item["contract_key"] == "stabilize_company")
    selected = client.post(
        f"/api/v1/engagement/legacy/return-contracts/{chosen['id']}/select",
        headers=auth_headers,
    )
    assert selected.status_code == 200
    assert selected.json()["status"] == "active"
    _record(profile_id, "company.first_profit", "return-profit")
    with SessionLocal() as db:
        completed = db.get(ReturnContract, chosen["id"])
        count = db.scalar(
            select(func.count())
            .select_from(EngagementEvent)
            .where(
                EngagementEvent.profile_id == profile_id,
                EngagementEvent.event_type == "company.first_profit",
            )
        )
        assert count == 1
        assert completed is not None
        assert completed.status == "completed"
        assert completed.progress_value == completed.target_value == 1

    rankings = client.get("/api/v1/engagement/legacy/rankings", headers=auth_headers)
    assert rankings.status_code == 200
    assert rankings.json()["economic_rewards"] is False
    assert len(rankings.json()["categories"]) == 12
    assert all(
        entry["historical_best_score"] >= entry["score"]
        for category in rankings.json()["categories"]
        for entry in category["entries"]
    )
    assert all(
        entry["bracket"] in ("newcomer", "veteran")
        for category in rankings.json()["categories"]
        for entry in category["entries"]
    )


@pytest.mark.parametrize("absence_days", [7, 14, 30])
def test_return_contracts_support_each_planned_pause_window(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
    absence_days: int,
) -> None:
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, str(joined_profile["id"]))
        assert profile is not None
        profile.created_at = datetime.now(UTC) - timedelta(days=absence_days, minutes=5)
        db.commit()
    contracts = client.post("/api/v1/engagement/legacy/return-contracts", headers=auth_headers)
    assert contracts.status_code == 200
    assert len(contracts.json()) == 3
    assert all(item["absence_days"] >= absence_days for item in contracts.json())
