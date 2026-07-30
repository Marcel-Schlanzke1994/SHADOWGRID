from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from shadowgrid import economy
from shadowgrid.database import SessionLocal
from shadowgrid.economy import (
    CompanyFactors,
    MarketParticipant,
    allocate_market,
    attractiveness_breakdown,
    ensure_city_sector_markets,
    market_share_bps,
    run_economy_tick,
)
from shadowgrid.finance import transaction_balance_cents
from shadowgrid.models import (
    Company,
    CompanyEconomyReport,
    CompanyMetric,
    EconomyTick,
    LedgerTransaction,
    MarketEconomyReport,
    User,
    World,
)
from sqlalchemy import func, select


def _create_company(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str,
    key: str,
) -> dict[str, object]:
    district = client.get("/api/v1/districts", headers=headers).json()[0]
    response = client.post(
        "/api/v1/companies",
        headers={**headers, "Idempotency-Key": key},
        json={
            "name": name,
            "industry": "logistics",
            "district_id": district["id"],
        },
    )
    assert response.status_code == 201
    return response.json()


def _configure_logistics_market(world_id: str, demand_units: int) -> None:
    with SessionLocal() as db:
        markets = ensure_city_sector_markets(db, world_id)
        market = next(item for item in markets if item.industry == "logistics")
        market.demand_units = demand_units
        db.commit()


@given(
    demand_units=st.integers(min_value=1, max_value=50_000),
    raw_participants=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=20_000),
            st.integers(min_value=1, max_value=100_000),
        ),
        min_size=0,
        max_size=20,
    ),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
def test_market_allocation_preserves_capacity_and_demand_invariants(
    demand_units: int,
    raw_participants: list[tuple[int, int]],
) -> None:
    participants = [
        MarketParticipant(
            company_id=f"company-{index:02d}",
            capacity_units=capacity,
            attractiveness_points=attractiveness,
        )
        for index, (capacity, attractiveness) in enumerate(raw_participants)
    ]

    allocations = allocate_market(demand_units, participants)

    assert allocations == allocate_market(demand_units, list(reversed(participants)))
    assert sum(allocations.values()) <= demand_units
    assert all(
        0 <= allocations[participant.company_id] <= participant.capacity_units
        for participant in participants
    )
    assert (
        sum(market_share_bps(demand_units, allocated) for allocated in allocations.values())
        <= 10_000
    )


def test_market_allocation_is_fair_rewards_quality_and_redistributes_rest() -> None:
    equal = allocate_market(
        1_000,
        [
            MarketParticipant("alpha", 1_000, 10_000),
            MarketParticipant("beta", 1_000, 10_000),
        ],
    )
    assert equal == {"alpha": 500, "beta": 500}

    baseline = CompanyFactors(5_000, 5_000, 5_000, 5_000, 1_000, 0, 60, 60)
    improved = CompanyFactors(7_000, 5_000, 5_000, 5_000, 1_000, 0, 60, 60)
    baseline_points, _ = attractiveness_breakdown(baseline)
    improved_points, _ = attractiveness_breakdown(improved)
    quality_result = allocate_market(
        1_000,
        [
            MarketParticipant("baseline", 1_000, baseline_points),
            MarketParticipant("improved", 1_000, improved_points),
        ],
    )
    assert quality_result["improved"] > quality_result["baseline"]

    constrained = allocate_market(
        800,
        [
            MarketParticipant("limited", 100, 100_000),
            MarketParticipant("available", 1_000, 1),
        ],
    )
    assert constrained == {"limited": 100, "available": 700}


def test_economy_tick_is_idempotent_balanced_and_reported(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
    verified_user: User,
) -> None:
    first_company = _create_company(
        client,
        auth_headers,
        name="Rhein Marktlogistik",
        key="economy-company-one",
    )
    second_company = _create_company(
        client,
        auth_headers,
        name="Dom Kuriernetz",
        key="economy-company-two",
    )
    world_id = str(joined_profile["world_id"])
    _configure_logistics_market(world_id, 3_000)
    with SessionLocal() as db:
        user = db.get(User, verified_user.id)
        assert user is not None
        user.is_admin = True
        db.commit()

    period = datetime.now(UTC) - timedelta(hours=2)
    payload = {"world_id": world_id, "period_start": period.isoformat()}
    first = client.post("/api/v1/admin/economy/ticks", headers=auth_headers, json=payload)
    repeated = client.post(
        "/api/v1/admin/economy/ticks",
        headers=auth_headers,
        json=payload,
    )

    assert first.status_code == repeated.status_code == 200
    assert first.json()["id"] == repeated.json()["id"]
    assert first.json()["status"] == "completed"
    assert first.json()["company_count"] == 2
    assert first.json()["market_count"] == 3

    reports = client.get(
        f"/api/v1/companies/{first_company['id']}/economy-reports",
        headers=auth_headers,
    )
    assert reports.status_code == 200
    assert len(reports.json()) == 1
    assert reports.json()[0]["inputs_json"]["capacity_units"] == first_company["capacity"]
    assert reports.json()[0]["modifiers_json"]["quality"] > 0

    markets = client.get("/api/v1/economy/markets", headers=auth_headers)
    assert markets.status_code == 200
    logistics_market = next(item for item in markets.json() if item["industry"] == "logistics")
    market_reports = client.get(
        f"/api/v1/economy/markets/{logistics_market['id']}/reports",
        headers=auth_headers,
    )
    assert market_reports.status_code == 200
    assert market_reports.json()[0]["allocated_units"] == 3_000
    assert market_reports.json()[0]["unfilled_units"] == 0

    status = client.get("/api/v1/economy/status", headers=auth_headers)
    assert status.status_code == 200
    assert status.json()["last_tick"]["id"] == first.json()["id"]
    assert status.json()["next_scheduled_at"] == first.json()["period_end"]

    with SessionLocal() as db:
        assert db.scalar(select(func.count(EconomyTick.id))) == 1
        company_reports = list(
            db.scalars(
                select(CompanyEconomyReport).where(
                    CompanyEconomyReport.company_id.in_(
                        [str(first_company["id"]), str(second_company["id"])]
                    )
                )
            )
        )
        assert len(company_reports) == 2
        assert sum(report.market_share_bps for report in company_reports) == 10_000
        for report in company_reports:
            if report.settlement_transaction_id is not None:
                assert transaction_balance_cents(db, report.settlement_transaction_id) == 0
        assert (
            db.scalar(
                select(func.count(CompanyMetric.id)).where(CompanyMetric.reason == "economy_tick")
            )
            == 2
        )
        company_reports[0].profit_cents = 0
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()


def test_negative_result_reduces_cash_without_negative_balance(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    company_data = _create_company(
        client,
        auth_headers,
        name="Loss Test Logistics",
        key="economy-loss-company",
    )
    world_id = str(joined_profile["world_id"])
    _configure_logistics_market(world_id, 100)
    with SessionLocal() as db:
        tick = run_economy_tick(
            db,
            world_id,
            at=datetime.now(UTC) - timedelta(hours=3),
        )
        report = db.scalar(
            select(CompanyEconomyReport).where(
                CompanyEconomyReport.tick_id == tick.id,
                CompanyEconomyReport.company_id == company_data["id"],
            )
        )
        company = db.get(Company, str(company_data["id"]))
        assert report is not None and company is not None
        assert report.profit_cents < 0
        assert report.cash_delta_cents < 0
        assert company.account.balance_cents < int(company_data["account_balance_cents"])
        assert company.account.balance_cents >= 0
        assert company.debt_cents >= 0
        assert report.settlement_transaction_id is not None
        assert transaction_balance_cents(db, report.settlement_transaction_id) == 0


def test_failed_tick_rolls_back_every_company_and_financial_change(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _create_company(
        client,
        auth_headers,
        name="Atomic One",
        key="economy-atomic-one",
    )
    _create_company(
        client,
        auth_headers,
        name="Atomic Two",
        key="economy-atomic-two",
    )
    world_id = str(joined_profile["world_id"])
    _configure_logistics_market(world_id, 3_000)
    real_settlement = economy.settle_company_operating_result
    calls = 0

    def fail_second_settlement(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected settlement failure")
        return real_settlement(*args, **kwargs)

    monkeypatch.setattr(
        economy,
        "settle_company_operating_result",
        fail_second_settlement,
    )
    with SessionLocal() as db, pytest.raises(RuntimeError, match="injected"):
        run_economy_tick(
            db,
            world_id,
            at=datetime.now(UTC) - timedelta(hours=4),
        )

    with SessionLocal() as db:
        assert db.scalar(select(func.count(EconomyTick.id))) == 0
        assert db.scalar(select(func.count(MarketEconomyReport.id))) == 0
        assert db.scalar(select(func.count(CompanyEconomyReport.id))) == 0
        company = db.get(Company, str(first["id"]))
        assert company is not None
        assert company.version == first["version"]
        assert company.account.balance_cents == first["account_balance_cents"]
        assert (
            db.scalar(
                select(func.count(LedgerTransaction.id)).where(
                    LedgerTransaction.transaction_type.like("company_economy_%")
                )
            )
            == 0
        )


def test_concurrent_tick_triggers_return_one_committed_period() -> None:
    with SessionLocal() as db:
        world = db.scalar(select(World))
        assert world is not None
        world_id = world.id
    period = datetime.now(UTC) - timedelta(hours=5)

    def trigger() -> str:
        with SessionLocal() as db:
            return run_economy_tick(db, world_id, at=period).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        tick_ids = list(executor.map(lambda _: trigger(), range(2)))

    assert len(set(tick_ids)) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count(EconomyTick.id))) == 1


def test_manual_economy_tick_requires_admin(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    response = client.post(
        "/api/v1/admin/economy/ticks",
        headers=auth_headers,
        json={
            "world_id": joined_profile["world_id"],
            "period_start": (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        },
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "auth.forbidden"
