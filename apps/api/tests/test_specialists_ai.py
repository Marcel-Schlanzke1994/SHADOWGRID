from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from shadowgrid.ai import run_ai_tick
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.economy import run_economy_tick
from shadowgrid.finance import pay_company_expense, transaction_balance_cents
from shadowgrid.game_config import AI_STRATEGIES, SPECIALIST_ROLES
from shadowgrid.models import (
    AiDecision,
    AiDecisionTick,
    City,
    Company,
    CompanyInvestment,
    LedgerTransaction,
    PlayerProfile,
    Specialist,
    SpecialistMarketCandidate,
    SpecialistPayrollReport,
    SpecialistPayrollTick,
    User,
    World,
)
from shadowgrid.specialists import (
    refresh_specialist_market,
    run_specialist_payroll,
    specialist_effects,
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


def _make_admin(user_id: str) -> None:
    with SessionLocal() as db:
        user = db.get(User, user_id)
        assert user is not None
        user.is_admin = True
        db.commit()


def _hire_market_candidate(
    client: TestClient,
    headers: dict[str, str],
    company_id: str,
    *,
    role: str = "market_analyst",
) -> tuple[dict[str, object], dict[str, object]]:
    market_response = client.get("/api/v1/specialist-market", headers=headers)
    assert market_response.status_code == 200
    candidate = next(item for item in market_response.json() if item["role"] == role)
    hire_response = client.post(
        f"/api/v1/specialist-market/{candidate['id']}/hire",
        headers={**headers, "Idempotency-Key": f"hire-{role}"},
        json={"company_id": company_id},
    )
    assert hire_response.status_code == 201
    return candidate, hire_response.json()


def test_specialist_market_is_deterministic_and_covers_all_roles(
    joined_profile: dict[str, object],
) -> None:
    fixed_time = datetime(2026, 7, 26, 10, tzinfo=UTC)
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, str(joined_profile["id"]))
        assert profile is not None and profile.city_id is not None
        first = refresh_specialist_market(
            db,
            profile.world_id,
            profile.city_id,
            at=fixed_time,
        )
        db.commit()
        first_snapshot = [
            (
                item.id,
                item.role,
                item.level,
                item.salary_cents,
                item.skills_json,
                item.deterministic_seed,
            )
            for item in first
        ]
        repeated = refresh_specialist_market(
            db,
            profile.world_id,
            profile.city_id,
            at=fixed_time,
        )
        repeated_snapshot = [
            (
                item.id,
                item.role,
                item.level,
                item.salary_cents,
                item.skills_json,
                item.deterministic_seed,
            )
            for item in repeated
        ]

    assert len(first_snapshot) == 12
    assert first_snapshot == repeated_snapshot
    assert set(item[1] for item in first_snapshot) == set(SPECIALIST_ROLES)


def test_specialist_effects_ignore_inactive_and_cap_modifiers() -> None:
    active = Specialist(
        profile_id="profile",
        name="Active Finance",
        role="finance_director",
        level=10,
        energy=100,
        skills_json={"financial_control": 100},
        competence=100,
        loyalty=100,
        ambition=50,
        stress=0,
        exposure=0,
        salary_cents=1,
        status="hired",
    )
    inactive = Specialist(
        profile_id="profile",
        name="Inactive Market",
        role="market_analyst",
        level=10,
        energy=0,
        skills_json={"market_intelligence": 100},
        competence=100,
        loyalty=100,
        ambition=50,
        stress=0,
        exposure=0,
        salary_cents=1,
        status="hired",
    )

    effects = specialist_effects([active, inactive])

    assert effects.active_specialists == 1
    assert effects.cost_reduction_bps == 1_500
    assert effects.revenue_bonus_bps == 0


def test_hire_assign_release_is_owned_idempotent_and_exposes_effects(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    first_company = _create_company(
        client,
        auth_headers,
        name="Specialist One",
        key="specialist-company-one",
    )
    second_company = _create_company(
        client,
        auth_headers,
        name="Specialist Two",
        key="specialist-company-two",
    )
    market = client.get("/api/v1/specialist-market", headers=auth_headers).json()
    candidate = next(item for item in market if item["role"] == "logistics_expert")
    hire_headers = {**auth_headers, "Idempotency-Key": "specialist-hire-idempotent"}

    first_hire = client.post(
        f"/api/v1/specialist-market/{candidate['id']}/hire",
        headers=hire_headers,
        json={"company_id": first_company["id"]},
    )
    repeated_hire = client.post(
        f"/api/v1/specialist-market/{candidate['id']}/hire",
        headers=hire_headers,
        json={"company_id": first_company["id"]},
    )

    assert first_hire.status_code == repeated_hire.status_code == 201
    assert first_hire.json()["id"] == repeated_hire.json()["id"]
    specialist_id = first_hire.json()["id"]
    effects = client.get(
        f"/api/v1/companies/{first_company['id']}/specialist-effects",
        headers=auth_headers,
    )
    assert effects.status_code == 200
    assert effects.json()["active_specialists"] == 1
    assert effects.json()["capacity_bonus_units"] > 0

    unavailable_candidate = next(item for item in market if item["id"] != candidate["id"])
    forbidden = client.post(
        f"/api/v1/specialist-market/{unavailable_candidate['id']}/hire",
        headers={**auth_headers, "Idempotency-Key": "specialist-foreign-company"},
        json={"company_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "company.not_owner"

    assigned = client.post(
        f"/api/v1/specialists/{specialist_id}/assign",
        headers={**auth_headers, "Idempotency-Key": "specialist-assign"},
        json={"company_id": second_company["id"]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["employer_company_id"] == second_company["id"]
    released = client.post(
        f"/api/v1/specialists/{specialist_id}/release",
        headers={**auth_headers, "Idempotency-Key": "specialist-release"},
    )
    assert released.status_code == 200
    assert released.json()["status"] == "released"
    assert released.json()["employer_company_id"] is None

    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count(Specialist.id)).where(
                    Specialist.id == specialist_id,
                )
            )
            == 1
        )
        candidate_row = db.get(SpecialistMarketCandidate, str(candidate["id"]))
        assert candidate_row is not None
        assert candidate_row.status == "hired"


def test_payroll_is_idempotent_balanced_and_updates_specialist(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    company_data = _create_company(
        client,
        auth_headers,
        name="Payroll Logistics",
        key="payroll-company",
    )
    candidate, specialist_data = _hire_market_candidate(
        client,
        auth_headers,
        str(company_data["id"]),
    )
    period = datetime.now(UTC) - timedelta(hours=8)
    world_id = str(joined_profile["world_id"])

    with SessionLocal() as db:
        run_economy_tick(db, world_id, at=period)
        company = db.get(Company, str(company_data["id"]))
        specialist = db.get(Specialist, str(specialist_data["id"]))
        assert company is not None and specialist is not None
        balance_before = company.account.balance_cents
        loyalty_before = specialist.loyalty
        first = run_specialist_payroll(db, world_id, at=period)
        repeated = run_specialist_payroll(db, world_id, at=period)
        db.refresh(company)
        db.refresh(specialist)

        assert first.id == repeated.id
        assert first.specialist_count == 1
        assert company.account.balance_cents == balance_before - int(candidate["salary_cents"])
        assert specialist.loyalty == loyalty_before + 1
        assert specialist.experience_points == 10
        report = db.scalar(
            select(SpecialistPayrollReport).where(
                SpecialistPayrollReport.payroll_tick_id == first.id,
            )
        )
        assert report is not None and report.transaction_id is not None
        assert report.salary_due_cents == report.salary_paid_cents
        assert report.unpaid_cents == 0
        assert transaction_balance_cents(db, report.transaction_id) == 0
        report.salary_paid_cents = 0
        with pytest.raises(ValueError, match="immutable"):
            db.commit()
        db.rollback()

    reports = client.get(
        f"/api/v1/specialists/{specialist_data['id']}/payroll-reports",
        headers=auth_headers,
    )
    assert reports.status_code == 200
    assert len(reports.json()) == 1


def test_unpaid_payroll_creates_debt_and_reduces_loyalty(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    company_data = _create_company(
        client,
        auth_headers,
        name="Debt Payroll Logistics",
        key="debt-payroll-company",
    )
    _, specialist_data = _hire_market_candidate(
        client,
        auth_headers,
        str(company_data["id"]),
        role="compliance_officer",
    )
    period = datetime.now(UTC) - timedelta(hours=9)
    world_id = str(joined_profile["world_id"])

    with SessionLocal() as db:
        run_economy_tick(db, world_id, at=period)
        company = db.get(Company, str(company_data["id"]))
        specialist = db.get(Specialist, str(specialist_data["id"]))
        assert company is not None and specialist is not None
        pay_company_expense(
            db,
            world_id=world_id,
            company_id=company.id,
            company_account=company.account,
            expense_cents=company.account.balance_cents,
            transaction_type="test_authorized_drain",
            idempotency_key=f"test-drain:{company.id}",
            reference_type="test",
            reference_id=company.id,
        )
        db.commit()
        loyalty_before = specialist.loyalty
        debt_before = company.debt_cents
        tick = run_specialist_payroll(db, world_id, at=period)
        db.refresh(company)
        db.refresh(specialist)
        report = db.scalar(
            select(SpecialistPayrollReport).where(
                SpecialistPayrollReport.payroll_tick_id == tick.id,
            )
        )

        assert report is not None
        assert report.salary_paid_cents == 0
        assert report.unpaid_cents == specialist.salary_cents
        assert company.account.balance_cents == 0
        assert company.debt_cents == debt_before + specialist.salary_cents
        assert specialist.loyalty == loyalty_before - 10


def test_concurrent_payroll_triggers_return_one_committed_period(
    joined_profile: dict[str, object],
) -> None:
    world_id = str(joined_profile["world_id"])
    period = datetime.now(UTC) - timedelta(hours=11)
    with SessionLocal() as db:
        run_economy_tick(db, world_id, at=period)

    def trigger() -> str:
        with SessionLocal() as db:
            return run_specialist_payroll(db, world_id, at=period).id

    with ThreadPoolExecutor(max_workers=2) as executor:
        tick_ids = list(executor.map(lambda _: trigger(), range(2)))

    assert len(set(tick_ids)) == 1
    with SessionLocal() as db:
        assert db.scalar(select(func.count(SpecialistPayrollTick.id))) == 1


def test_ai_uses_company_services_is_deterministic_and_can_be_paused(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
    verified_user: User,
) -> None:
    profile_id = str(joined_profile["id"])
    world_id = str(joined_profile["world_id"])
    base_period = datetime.now(UTC) - timedelta(hours=12)
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        assert profile is not None
        profile.is_local_ai = True
        profile.ai_strategy = "growth"
        profile.ai_seed = 42
        db.commit()

        tick_ids = []
        for offset in range(3):
            tick = run_ai_tick(
                db,
                world_id,
                settings=get_settings(),
                at=base_period + timedelta(hours=offset),
            )
            tick_ids.append(tick.id)
        repeated = run_ai_tick(
            db,
            world_id,
            settings=get_settings(),
            at=base_period + timedelta(hours=2),
        )
        assert repeated.id == tick_ids[-1]

        decisions = list(
            db.scalars(
                select(AiDecision)
                .where(AiDecision.profile_id == profile_id)
                .order_by(AiDecision.created_at)
            )
        )
        assert [decision.action_type for decision in decisions] == [
            "found_company",
            "found_company",
            "invest",
        ]
        assert len({decision.deterministic_seed for decision in decisions}) == 3
        assert (
            db.scalar(
                select(func.count(Company.id)).where(
                    Company.founder_profile_id == profile_id,
                )
            )
            == 2
        )
        assert db.scalar(select(func.count(CompanyInvestment.id))) == 1
        transactions = list(
            db.scalars(
                select(LedgerTransaction).where(
                    LedgerTransaction.actor_profile_id == profile_id,
                )
            )
        )
        assert transactions
        assert all(transaction_balance_cents(db, item.id) == 0 for item in transactions)

    _make_admin(verified_user.id)
    ai_profiles = client.get("/api/v1/admin/ai/players", headers=auth_headers)
    assert ai_profiles.status_code == 200
    assert ai_profiles.json()[0]["ai_strategy"] in AI_STRATEGIES
    paused = client.patch(
        f"/api/v1/admin/ai/players/{profile_id}",
        headers=auth_headers,
        json={"paused": True},
    )
    assert paused.status_code == 200
    assert paused.json()["ai_paused"] is True
    manual = client.post(
        "/api/v1/admin/ai/ticks",
        headers=auth_headers,
        json={
            "world_id": world_id,
            "period_start": (base_period + timedelta(hours=4)).isoformat(),
        },
    )
    assert manual.status_code == 200
    assert manual.json()["profile_count"] == 0

    competitors = client.get("/api/v1/economy/competitors", headers=auth_headers)
    assert competitors.status_code == 200
    assert len(competitors.json()) == 2
    assert all(item["is_local_simulation"] is True for item in competitors.json())


def test_specialist_and_ai_admin_actions_require_admin(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    world_id = str(joined_profile["world_id"])
    period = datetime.now(UTC) - timedelta(hours=10)
    payroll = client.post(
        "/api/v1/admin/specialists/payroll",
        headers=auth_headers,
        json={"world_id": world_id, "period_start": period.isoformat()},
    )
    ai = client.post(
        "/api/v1/admin/ai/ticks",
        headers=auth_headers,
        json={"world_id": world_id, "period_start": period.isoformat()},
    )

    assert payroll.status_code == ai.status_code == 403
    assert payroll.json()["error"]["code"] == "auth.forbidden"
    assert ai.json()["error"]["code"] == "auth.forbidden"


def test_phase_four_seed_shape_is_reproducible_in_local_database() -> None:
    with SessionLocal() as db:
        world = db.scalar(select(World))
        city = db.scalar(select(City))
        assert world is not None and city is not None
        fixed_time = datetime(2026, 7, 26, 12, tzinfo=UTC)
        first = refresh_specialist_market(db, world.id, city.id, at=fixed_time)
        db.commit()
        repeated = refresh_specialist_market(db, world.id, city.id, at=fixed_time)

        assert [item.id for item in first] == [item.id for item in repeated]
        assert len(first) == 12
        assert set(item.role for item in first) == set(SPECIALIST_ROLES)
        assert (
            db.scalar(
                select(func.count(SpecialistMarketCandidate.id)).where(
                    SpecialistMarketCandidate.market_cycle_key == "2026-07-26",
                )
            )
            == 12
        )
        assert db.scalar(select(func.count(SpecialistPayrollTick.id))) == 0
        assert db.scalar(select(func.count(AiDecisionTick.id))) == 0
