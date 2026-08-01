from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shadowgrid.companies import snapshot_company
from shadowgrid.domain import audit, get_idempotent, remember_idempotent
from shadowgrid.engagement import record_engagement_event
from shadowgrid.errors import DomainError
from shadowgrid.finance import cents_to_money, pay_company_expense
from shadowgrid.game_config import SPECIALIST_DEFINITIONS, SPECIALIST_ROLES
from shadowgrid.models import (
    City,
    Company,
    CompanyOwnership,
    District,
    EconomyTick,
    PlayerProfile,
    Specialist,
    SpecialistMarketCandidate,
    SpecialistPayrollReport,
    SpecialistPayrollTick,
    World,
    as_utc,
    uuid_str,
)
from shadowgrid.tick_time import period_key_for
from shadowgrid.world_events import company_event_modifiers

_CANDIDATE_NAMES = (
    "Leonie Adler",
    "Samir Berg",
    "Mika Conrad",
    "Nia Dietrich",
    "Tarin Engel",
    "Avery Falk",
    "Noa Gerber",
    "Remy Hartmann",
    "Ira Jansen",
    "Jun Keller",
    "Mara Lorenz",
    "Elias Maurer",
)
_local_market_lock = Lock()
_local_payroll_lock = Lock()


@dataclass(frozen=True)
class SpecialistEffects:
    active_specialists: int = 0
    capacity_bonus_units: int = 0
    revenue_bonus_bps: int = 0
    cost_reduction_bps: int = 0
    attractiveness_bonus_points: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "active_specialists": self.active_specialists,
            "capacity_bonus_units": self.capacity_bonus_units,
            "revenue_bonus_bps": self.revenue_bonus_bps,
            "cost_reduction_bps": self.cost_reduction_bps,
            "attractiveness_bonus_points": self.attractiveness_bonus_points,
        }


def specialist_effects(specialists: list[Specialist]) -> SpecialistEffects:
    capacity_bonus_units = 0
    revenue_bonus_bps = 0
    cost_reduction_bps = 0
    attractiveness_bonus_points = 0
    active_count = 0
    for specialist in specialists:
        if (
            specialist.status not in {"hired", "assigned"}
            or specialist.loyalty < 30
            or specialist.energy < 10
        ):
            continue
        definition = SPECIALIST_DEFINITIONS.get(specialist.role)
        if definition is None:
            continue
        skill = int(
            specialist.skills_json.get(
                definition["primary_skill"],
                specialist.competence,
            )
        )
        skill = min(100, max(0, skill))
        active_count += 1
        if specialist.role == "finance_director":
            cost_reduction_bps += specialist.level * 100 + skill * 5
        elif specialist.role == "technology_expert":
            attractiveness_bonus_points += specialist.level * 500 + skill * 20
        elif specialist.role == "market_analyst":
            revenue_bonus_bps += specialist.level * 100 + skill * 5
        elif specialist.role == "compliance_officer":
            attractiveness_bonus_points += specialist.level * 350 + skill * 15
        elif specialist.role == "logistics_expert":
            capacity_bonus_units += specialist.level * 150 + skill * 5
        elif specialist.role == "diplomat":
            attractiveness_bonus_points += specialist.level * 300 + skill * 15
    return SpecialistEffects(
        active_specialists=active_count,
        capacity_bonus_units=min(5_000, capacity_bonus_units),
        revenue_bonus_bps=min(1_500, revenue_bonus_bps),
        cost_reduction_bps=min(2_000, cost_reduction_bps),
        attractiveness_bonus_points=min(25_000, attractiveness_bonus_points),
    )


def company_specialist_effects(db: Session, company_id: str) -> SpecialistEffects:
    specialists = list(
        db.scalars(
            select(Specialist)
            .where(
                Specialist.employer_company_id == company_id,
                Specialist.status.in_(("hired", "assigned")),
            )
            .order_by(Specialist.id)
        )
    )
    return specialist_effects(specialists)


def _candidate_cycle(at: datetime) -> tuple[str, datetime]:
    current = at.astimezone(UTC)
    cycle_start = current.replace(hour=0, minute=0, second=0, microsecond=0)
    return cycle_start.strftime("%Y-%m-%d"), cycle_start + timedelta(days=1)


def refresh_specialist_market(
    db: Session,
    world_id: str,
    city_id: str,
    *,
    at: datetime | None = None,
) -> list[SpecialistMarketCandidate]:
    with _local_market_lock:
        return _refresh_specialist_market_locked(
            db,
            world_id,
            city_id,
            at=at,
        )


def _refresh_specialist_market_locked(
    db: Session,
    world_id: str,
    city_id: str,
    *,
    at: datetime | None,
) -> list[SpecialistMarketCandidate]:
    now = at or datetime.now(UTC)
    city = db.scalar(
        select(City).where(City.id == city_id, City.world_id == world_id).with_for_update()
    )
    if city is None:
        raise DomainError(404, "city.not_found", "City not found")
    cycle_key, available_until = _candidate_cycle(now)
    expired = list(
        db.scalars(
            select(SpecialistMarketCandidate).where(
                SpecialistMarketCandidate.world_id == world_id,
                SpecialistMarketCandidate.city_id == city_id,
                SpecialistMarketCandidate.status == "available",
                SpecialistMarketCandidate.available_until <= now,
            )
        )
    )
    for candidate in expired:
        candidate.status = "expired"

    existing = {
        candidate.slot_number: candidate
        for candidate in db.scalars(
            select(SpecialistMarketCandidate).where(
                SpecialistMarketCandidate.world_id == world_id,
                SpecialistMarketCandidate.city_id == city_id,
                SpecialistMarketCandidate.market_cycle_key == cycle_key,
            )
        )
    }
    for slot_number in range(12):
        if slot_number in existing:
            continue
        role = SPECIALIST_ROLES[slot_number % len(SPECIALIST_ROLES)]
        seed = hashlib.sha256(
            f"{world_id}:{city_id}:{cycle_key}:{slot_number}:{role}".encode()
        ).hexdigest()
        digest = bytes.fromhex(seed)
        definition = SPECIALIST_DEFINITIONS[role]
        level = 1 + digest[0] % 3
        primary_skill = definition["primary_skill"]
        skills = {
            primary_skill: 50 + digest[1] % 41,
            "leadership": 35 + digest[2] % 51,
            "resilience": 40 + digest[3] % 46,
        }
        candidate = SpecialistMarketCandidate(
            id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"shadowgrid:specialist:{world_id}:{city_id}:{cycle_key}:{slot_number}",
                )
            ),
            world_id=world_id,
            city_id=city_id,
            market_cycle_key=cycle_key,
            slot_number=slot_number,
            role=role,
            name=_CANDIDATE_NAMES[(digest[4] + slot_number) % len(_CANDIDATE_NAMES)],
            level=level,
            salary_cents=(
                definition["base_salary_cents"] + (level - 1) * 20_000 + (digest[5] % 10) * 2_500
            ),
            loyalty=55 + digest[6] % 31,
            energy=75 + digest[7] % 26,
            skills_json=skills,
            deterministic_seed=seed,
            available_until=available_until,
        )
        db.add(candidate)
        existing[slot_number] = candidate
    db.flush()
    return [existing[slot] for slot in sorted(existing) if existing[slot].status == "available"]


def list_market_candidates(
    db: Session,
    profile: PlayerProfile,
    *,
    at: datetime | None = None,
) -> list[SpecialistMarketCandidate]:
    if profile.city_id is None:
        raise DomainError(409, "profile.city_required", "Select a city first")
    return refresh_specialist_market(
        db,
        profile.world_id,
        profile.city_id,
        at=at,
    )


def run_due_specialist_market_refresh(
    db: Session,
    *,
    at: datetime | None = None,
) -> int:
    cities = list(
        db.execute(
            select(World.id, City.id)
            .join(City, City.world_id == World.id)
            .where(World.status == "active", City.status == "active")
            .order_by(World.id, City.id)
        ).all()
    )
    for world_id, city_id in cities:
        refresh_specialist_market(db, world_id, city_id, at=at)
    db.commit()
    return len(cities)


def list_profile_specialists(db: Session, profile: PlayerProfile) -> list[Specialist]:
    return list(
        db.scalars(
            select(Specialist)
            .where(
                Specialist.profile_id == profile.id,
                Specialist.status != "released",
            )
            .order_by(Specialist.created_at)
        )
    )


def _owned_company(
    db: Session,
    profile: PlayerProfile,
    company_id: str,
    *,
    lock: bool,
) -> Company:
    statement = (
        select(Company)
        .join(CompanyOwnership, CompanyOwnership.company_id == Company.id)
        .where(
            Company.id == company_id,
            Company.world_id == profile.world_id,
            CompanyOwnership.owner_profile_id == profile.id,
            CompanyOwnership.ownership_bps > 0,
        )
    )
    if lock:
        statement = statement.with_for_update()
    company = db.scalar(statement)
    if company is None:
        raise DomainError(403, "company.not_owner", "Company ownership is required")
    return company


def hire_specialist(
    db: Session,
    profile: PlayerProfile,
    *,
    candidate_id: str,
    company_id: str,
    idempotency_key: str,
    request_id: str,
) -> Specialist:
    locked_profile = db.scalar(
        select(PlayerProfile).where(PlayerProfile.id == profile.id).with_for_update()
    )
    if locked_profile is None:
        raise DomainError(409, "profile.missing", "Player profile does not exist")
    previous = get_idempotent(
        db,
        locked_profile.user_id,
        idempotency_key,
        "specialist.hire",
    )
    if previous is not None:
        existing = db.get(Specialist, previous.resource_id)
        if existing is not None:
            return existing

    candidate = db.scalar(
        select(SpecialistMarketCandidate)
        .where(
            SpecialistMarketCandidate.id == candidate_id,
            SpecialistMarketCandidate.world_id == locked_profile.world_id,
            SpecialistMarketCandidate.city_id == locked_profile.city_id,
        )
        .with_for_update()
    )
    if candidate is None or candidate.status != "available":
        raise DomainError(
            409,
            "specialist.candidate_unavailable",
            "Specialist candidate is no longer available",
        )
    if as_utc(candidate.available_until) <= datetime.now(UTC):
        raise DomainError(
            409,
            "specialist.candidate_expired",
            "Specialist candidate has expired",
        )
    company = _owned_company(db, locked_profile, company_id, lock=True)
    active_count = int(
        db.scalar(
            select(func.count(Specialist.id)).where(
                Specialist.profile_id == locked_profile.id,
                Specialist.status != "released",
            )
        )
        or 0
    )
    if active_count >= int(locked_profile.resources.personnel_capacity):
        raise DomainError(409, "specialist.capacity", "Personnel capacity reached")
    if company.account.balance_cents < candidate.salary_cents:
        raise DomainError(
            409,
            "specialist.salary_unaffordable",
            "Company cannot cover the first salary period",
        )

    primary_skill = SPECIALIST_DEFINITIONS[candidate.role]["primary_skill"]
    specialist = Specialist(
        profile_id=locked_profile.id,
        name=candidate.name,
        role=candidate.role,
        level=candidate.level,
        energy=candidate.energy,
        experience_points=0,
        skills_json=candidate.skills_json,
        competence=int(candidate.skills_json[primary_skill]),
        loyalty=candidate.loyalty,
        ambition=int(candidate.skills_json["leadership"]),
        stress=0,
        exposure=0,
        salary=cents_to_money(candidate.salary_cents),
        salary_cents=candidate.salary_cents,
        status="hired",
        employer_company_id=company.id,
        hired_at=datetime.now(UTC),
    )
    db.add(specialist)
    db.flush()
    candidate.status = "hired"
    candidate.hired_specialist_id = specialist.id
    remember_idempotent(
        db,
        locked_profile.user_id,
        idempotency_key,
        "specialist.hire",
        specialist.id,
        {"specialist_id": specialist.id, "company_id": company.id},
    )
    audit(
        db,
        locked_profile.user_id,
        "specialist.hire",
        "specialist",
        specialist.id,
        request_id,
        {
            "candidate_id": candidate.id,
            "company_id": company.id,
            "salary_cents": specialist.salary_cents,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(
            409,
            "specialist.hire_conflict",
            "Specialist hiring conflicts with current state",
        ) from exc
    db.refresh(specialist)
    return specialist


def assign_specialist(
    db: Session,
    profile: PlayerProfile,
    *,
    specialist_id: str,
    company_id: str,
    idempotency_key: str,
    request_id: str,
) -> Specialist:
    previous = get_idempotent(db, profile.user_id, idempotency_key, "specialist.assign")
    if previous is not None:
        existing = db.get(Specialist, previous.resource_id)
        if existing is not None:
            return existing
    specialist = db.scalar(
        select(Specialist)
        .where(
            Specialist.id == specialist_id,
            Specialist.profile_id == profile.id,
            Specialist.status.in_(("hired", "assigned")),
        )
        .with_for_update()
    )
    if specialist is None:
        raise DomainError(404, "specialist.not_found", "Hired specialist not found")
    now = datetime.now(UTC)
    if specialist.cooldown_until is not None and as_utc(specialist.cooldown_until) > now:
        raise DomainError(
            409,
            "specialist.cooldown",
            "Specialist reassignment is on cooldown",
        )
    company = _owned_company(db, profile, company_id, lock=True)
    specialist.employer_company_id = company.id
    specialist.status = "assigned" if specialist.assigned_operation_id else "hired"
    specialist.cooldown_until = now + timedelta(hours=1)
    record_engagement_event(
        db,
        profile_id=profile.id,
        event_type="specialist.assigned",
        source_type="specialist_assignment",
        source_id=f"{specialist.id}:{company.id}",
        idempotency_key=f"specialist.assigned:{specialist.id}:{company.id}",
        payload={"company_id": company.id, "role": specialist.role},
    )
    remember_idempotent(
        db,
        profile.user_id,
        idempotency_key,
        "specialist.assign",
        specialist.id,
        {"specialist_id": specialist.id, "company_id": company.id},
    )
    audit(
        db,
        profile.user_id,
        "specialist.assign",
        "specialist",
        specialist.id,
        request_id,
        {"company_id": company.id},
    )
    db.commit()
    db.refresh(specialist)
    return specialist


def release_specialist(
    db: Session,
    profile: PlayerProfile,
    *,
    specialist_id: str,
    idempotency_key: str,
    request_id: str,
) -> Specialist:
    previous = get_idempotent(db, profile.user_id, idempotency_key, "specialist.release")
    if previous is not None:
        existing = db.get(Specialist, previous.resource_id)
        if existing is not None:
            return existing
    specialist = db.scalar(
        select(Specialist)
        .where(
            Specialist.id == specialist_id,
            Specialist.profile_id == profile.id,
        )
        .with_for_update()
    )
    if specialist is None:
        raise DomainError(404, "specialist.not_found", "Specialist not found")
    if specialist.assigned_operation_id is not None:
        raise DomainError(
            409,
            "specialist.operation_active",
            "Specialist cannot be released during an operation",
        )
    specialist.status = "released"
    specialist.employer_company_id = None
    specialist.cooldown_until = datetime.now(UTC) + timedelta(hours=24)
    remember_idempotent(
        db,
        profile.user_id,
        idempotency_key,
        "specialist.release",
        specialist.id,
        {"specialist_id": specialist.id},
    )
    audit(
        db,
        profile.user_id,
        "specialist.release",
        "specialist",
        specialist.id,
        request_id,
        {},
    )
    db.commit()
    db.refresh(specialist)
    return specialist


def run_specialist_payroll(
    db: Session,
    world_id: str,
    *,
    at: datetime | None = None,
) -> SpecialistPayrollTick:
    with _local_payroll_lock:
        return _run_specialist_payroll_locked(db, world_id, at=at)


def _run_specialist_payroll_locked(
    db: Session,
    world_id: str,
    *,
    at: datetime | None,
) -> SpecialistPayrollTick:
    now = at or datetime.now(UTC)
    period_key = period_key_for(now)
    try:
        world = db.scalar(select(World).where(World.id == world_id).with_for_update())
        if world is None:
            raise DomainError(404, "world.not_found", "World not found")
        existing = db.scalar(
            select(SpecialistPayrollTick).where(
                SpecialistPayrollTick.world_id == world_id,
                SpecialistPayrollTick.period_key == period_key,
            )
        )
        if existing is not None:
            return existing
        economy_tick = db.scalar(
            select(EconomyTick).where(
                EconomyTick.world_id == world_id,
                EconomyTick.period_key == period_key,
                EconomyTick.status == "completed",
            )
        )
        if economy_tick is None:
            raise DomainError(
                409,
                "specialist.economy_tick_required",
                "Complete the economy tick before payroll",
            )
        payroll_tick = SpecialistPayrollTick(
            world_id=world_id,
            economy_tick_id=economy_tick.id,
            period_key=period_key,
        )
        db.add(payroll_tick)
        db.flush()
        rows = list(
            db.execute(
                select(Specialist, Company)
                .join(Company, Company.id == Specialist.employer_company_id)
                .where(
                    Company.world_id == world_id,
                    Specialist.status.in_(("hired", "assigned")),
                    Specialist.salary_cents > 0,
                )
                .order_by(Specialist.id)
                .with_for_update()
            ).all()
        )
        for specialist, company in rows:
            district = db.get(District, company.district_id)
            if district is None:
                raise DomainError(
                    409,
                    "specialist.company_district_missing",
                    "Company district is unavailable",
                )
            event_effects = company_event_modifiers(db, company, district, now)
            salary_due_cents = (
                specialist.salary_cents * event_effects.specialist_salary_multiplier_bps // 10_000
            )
            report_id = uuid_str()
            settlement = pay_company_expense(
                db,
                world_id=world_id,
                company_id=company.id,
                company_account=company.account,
                expense_cents=salary_due_cents,
                transaction_type="specialist_payroll",
                idempotency_key=f"payroll:{period_key}:{specialist.id}",
                reference_type="specialist_payroll",
                reference_id=report_id,
            )
            loyalty_before = specialist.loyalty
            energy_before = specialist.energy
            level_before = specialist.level
            paid_cents = abs(settlement.cash_delta_cents)
            if paid_cents == salary_due_cents:
                specialist.loyalty = min(100, specialist.loyalty + 1)
                experience_gain = 10
            elif paid_cents > 0:
                specialist.loyalty = max(0, specialist.loyalty - 5)
                experience_gain = 4
            else:
                specialist.loyalty = max(0, specialist.loyalty - 10)
                experience_gain = 0
            specialist.energy = (
                max(0, specialist.energy - 10)
                if specialist.assigned_operation_id is not None
                else min(100, specialist.energy + 8)
            )
            specialist.experience_points = min(
                100_000,
                specialist.experience_points + experience_gain,
            )
            specialist.level = min(10, 1 + specialist.experience_points // 100)
            company.debt_cents += settlement.debt_delta_cents
            company.version += 1
            db.add(
                SpecialistPayrollReport(
                    id=report_id,
                    payroll_tick_id=payroll_tick.id,
                    specialist_id=specialist.id,
                    company_id=company.id,
                    transaction_id=(
                        settlement.transaction.id if settlement.transaction is not None else None
                    ),
                    salary_due_cents=salary_due_cents,
                    salary_paid_cents=paid_cents,
                    unpaid_cents=settlement.debt_delta_cents,
                    loyalty_before=loyalty_before,
                    loyalty_after=specialist.loyalty,
                    energy_before=energy_before,
                    energy_after=specialist.energy,
                    level_before=level_before,
                    level_after=specialist.level,
                )
            )
            db.add(
                snapshot_company(
                    company,
                    reason="specialist_payroll",
                    reference_id=report_id,
                )
            )
        payroll_tick.specialist_count = len(rows)
        payroll_tick.status = "completed"
        payroll_tick.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(payroll_tick)
        return payroll_tick
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(SpecialistPayrollTick).where(
                SpecialistPayrollTick.world_id == world_id,
                SpecialistPayrollTick.period_key == period_key,
            )
        )
        if existing is not None:
            return existing
        raise
    except Exception:
        db.rollback()
        raise


def run_due_specialist_payrolls(
    db: Session,
    *,
    at: datetime | None = None,
) -> int:
    world_ids = list(
        db.scalars(select(World.id).where(World.status == "active").order_by(World.id))
    )
    for world_id in world_ids:
        run_specialist_payroll(db, world_id, at=at)
    return len(world_ids)


def list_specialist_payroll_reports(
    db: Session,
    profile: PlayerProfile,
    specialist_id: str,
    *,
    limit: int = 24,
) -> list[SpecialistPayrollReport]:
    specialist = db.scalar(
        select(Specialist.id).where(
            Specialist.id == specialist_id,
            Specialist.profile_id == profile.id,
        )
    )
    if specialist is None:
        raise DomainError(404, "specialist.not_found", "Specialist not found")
    return list(
        db.scalars(
            select(SpecialistPayrollReport)
            .where(SpecialistPayrollReport.specialist_id == specialist_id)
            .order_by(SpecialistPayrollReport.created_at.desc())
            .limit(limit)
        )
    )
