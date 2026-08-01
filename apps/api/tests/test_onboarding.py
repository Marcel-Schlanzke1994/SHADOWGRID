from __future__ import annotations

from decimal import Decimal

from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.models import LedgerEntry, PlayerProfile
from sqlalchemy import func, select


def test_cologne_selection_grants_starting_cash_exactly_once(
    client: TestClient,
    auth_headers: dict[str, str],
) -> None:
    cities = client.get("/api/v1/world/cities", headers=auth_headers)
    assert cities.status_code == 200
    assert [city["name"] for city in cities.json()] == ["Köln"]
    city = cities.json()[0]

    districts = client.get(
        f"/api/v1/world/cities/{city['id']}/districts",
        headers=auth_headers,
    )
    assert districts.status_code == 200
    assert {district["name"] for district in districts.json()} == {
        "Innenstadt",
        "Hafenbezirk",
        "Technologiepark",
        "Gewerbering",
        "Medienquartier",
    }
    first_district, second_district = districts.json()[:2]
    request = {
        "city_id": city["id"],
        "codename": "Rhein Network",
        "archetype": "business_consortium",
        "home_district_id": first_district["id"],
    }
    headers = {**auth_headers, "Idempotency-Key": "select-cologne-0001"}

    selected = client.post("/api/v1/players/me/select-city", headers=headers, json=request)
    repeated = client.post("/api/v1/players/me/select-city", headers=headers, json=request)

    assert selected.status_code == 200
    assert repeated.status_code == 200
    assert selected.json()["id"] == repeated.json()["id"]
    assert Decimal(str(selected.json()["resources"]["cash"])) == Decimal("80000.00")

    with SessionLocal() as db:
        assert db.scalar(select(func.count(PlayerProfile.id))) == 1
        cash_entries = list(
            db.scalars(
                select(LedgerEntry).where(
                    LedgerEntry.owner_id == selected.json()["id"],
                    LedgerEntry.resource_type == "cash",
                    LedgerEntry.reason == "initial_grant",
                )
            )
        )
        assert len(cash_entries) == 1
        assert cash_entries[0].amount == Decimal("80000.00")

    changed = client.post(
        "/api/v1/players/me/select-city",
        headers={**auth_headers, "Idempotency-Key": "select-cologne-0002"},
        json={**request, "home_district_id": second_district["id"]},
    )
    assert changed.status_code == 409
    assert changed.json()["error"]["code"] == "player.city_already_selected"


def test_city_selection_contract_requires_authentication(client: TestClient) -> None:
    response = client.get("/api/v1/world/cities")

    assert response.status_code == 401
