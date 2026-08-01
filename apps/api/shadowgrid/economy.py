from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shadowgrid.companies import snapshot_company
from shadowgrid.engagement import record_engagement_event
from shadowgrid.errors import DomainError
from shadowgrid.finance import settle_company_operating_result
from shadowgrid.game_config import ECONOMY_MARKETS
from shadowgrid.intelligence import active_company_cost_increase_bps
from shadowgrid.models import (
    City,
    CitySectorMarket,
    Company,
    CompanyEconomyReport,
    District,
    EconomyTick,
    MarketEconomyReport,
    PlayerProfile,
    World,
    as_utc,
    uuid_str,
)
from shadowgrid.realtime import emit_realtime_event
from shadowgrid.specialists import SpecialistEffects, company_specialist_effects
from shadowgrid.tick_time import period_key_for, period_start_for
from shadowgrid.world_events import (
    EventModifiers,
    company_event_modifiers,
    market_event_modifiers,
)

MAX_BIGINT = 9_223_372_036_854_775_807
_local_tick_lock = Lock()


@dataclass(frozen=True)
class MarketParticipant:
    company_id: str
    capacity_units: int
    attractiveness_points: int


@dataclass(frozen=True)
class CompanyFactors:
    quality_bps: int
    reputation_bps: int
    compliance_bps: int
    innovation_bps: int
    risk_bps: int
    investigation_pressure_bps: int
    district_economic_activity: int
    district_prosperity: int


def attractiveness_breakdown(factors: CompanyFactors) -> tuple[int, dict[str, int]]:
    values = (
        factors.quality_bps,
        factors.reputation_bps,
        factors.compliance_bps,
        factors.innovation_bps,
        factors.risk_bps,
        factors.investigation_pressure_bps,
    )
    if any(value < 0 or value > 10_000 for value in values):
        raise ValueError("company factors must be between 0 and 10,000 basis points")
    if not 0 <= factors.district_economic_activity <= 100:
        raise ValueError("district economic activity must be between 0 and 100")
    if not 0 <= factors.district_prosperity <= 100:
        raise ValueError("district prosperity must be between 0 and 100")

    modifiers = {
        "base": 1_000,
        "quality": factors.quality_bps * 4,
        "reputation": factors.reputation_bps * 2,
        "compliance": factors.compliance_bps,
        "innovation": factors.innovation_bps * 2,
        "district_economic_activity": factors.district_economic_activity * 50,
        "district_prosperity": factors.district_prosperity * 25,
        "risk": -(factors.risk_bps * 2),
        "investigation_pressure": -(factors.investigation_pressure_bps * 3),
    }
    return max(1, sum(modifiers.values())), modifiers


def allocate_market(
    demand_units: int,
    participants: list[MarketParticipant],
) -> dict[str, int]:
    if demand_units <= 0:
        raise ValueError("market demand must be positive")
    if len({participant.company_id for participant in participants}) != len(participants):
        raise ValueError("market participant ids must be unique")
    if any(participant.capacity_units < 0 for participant in participants):
        raise ValueError("market capacity cannot be negative")
    if any(participant.attractiveness_points <= 0 for participant in participants):
        raise ValueError("market attractiveness must be positive")

    allocations = {participant.company_id: 0 for participant in participants}
    ordered = sorted(participants, key=lambda participant: participant.company_id)
    remaining_demand = demand_units
    while remaining_demand > 0:
        active = [
            participant
            for participant in ordered
            if allocations[participant.company_id] < participant.capacity_units
        ]
        if not active:
            break
        total_weight = sum(participant.attractiveness_points for participant in active)
        round_demand = remaining_demand
        used = 0
        for participant in active:
            available = participant.capacity_units - allocations[participant.company_id]
            proportional = (round_demand * participant.attractiveness_points) // total_weight
            awarded = min(available, proportional)
            allocations[participant.company_id] += awarded
            used += awarded
        remaining_demand -= used
        if remaining_demand == 0:
            break

        ranked = sorted(
            active,
            key=lambda participant: (
                -((round_demand * participant.attractiveness_points) % total_weight),
                participant.company_id,
            ),
        )
        remainder_used = 0
        for participant in ranked:
            if remaining_demand == 0:
                break
            if allocations[participant.company_id] >= participant.capacity_units:
                continue
            allocations[participant.company_id] += 1
            remaining_demand -= 1
            remainder_used += 1
        if used == 0 and remainder_used == 0:
            break
    return allocations


def market_share_bps(demand_units: int, allocated_units: int) -> int:
    if demand_units <= 0:
        raise ValueError("market demand must be positive")
    if allocated_units < 0 or allocated_units > demand_units:
        raise ValueError("allocated units must be within market demand")
    return (allocated_units * 10_000) // demand_units


def enterprise_value_v1(
    *,
    capacity: int,
    quality: int,
    innovation_bps: int,
    profit_cents: int,
    account_balance_cents: int,
    debt_cents: int,
) -> int:
    if min(capacity, quality, innovation_bps, account_balance_cents, debt_cents) < 0:
        raise ValueError("valuation inputs cannot be negative")
    value = (
        capacity * 4_000
        + quality * 1_000
        + innovation_bps * 500
        + max(profit_cents, 0) * 6
        + account_balance_cents
        - debt_cents
    )
    return min(MAX_BIGINT, max(0, value))


def ensure_city_sector_markets(db: Session, world_id: str) -> list[CitySectorMarket]:
    cities = list(
        db.scalars(
            select(City).where(City.world_id == world_id, City.status == "active").order_by(City.id)
        )
    )
    existing = {
        (market.city_id, market.industry): market
        for market in db.scalars(
            select(CitySectorMarket).where(CitySectorMarket.world_id == world_id)
        )
    }
    for city in cities:
        for industry, definition in ECONOMY_MARKETS.items():
            key = (city.id, industry)
            if key in existing:
                continue
            market = CitySectorMarket(
                world_id=world_id,
                city_id=city.id,
                industry=industry,
                **definition,
            )
            db.add(market)
            existing[key] = market
    db.flush()
    return sorted(existing.values(), key=lambda market: (market.city_id, market.industry))


def _company_factors(company: Company, district: District) -> CompanyFactors:
    return CompanyFactors(
        quality_bps=company.quality,
        reputation_bps=company.reputation_bps,
        compliance_bps=company.compliance_bps,
        innovation_bps=company.innovation_bps,
        risk_bps=company.risk_bps,
        investigation_pressure_bps=company.investigation_pressure_bps,
        district_economic_activity=district.economic_activity,
        district_prosperity=district.prosperity,
    )


def _checked_money(value: int) -> int:
    if value < -MAX_BIGINT or value > MAX_BIGINT:
        raise OverflowError("economy money calculation exceeds database range")
    return value


def run_economy_tick(
    db: Session,
    world_id: str,
    *,
    at: datetime | None = None,
) -> EconomyTick:
    with _local_tick_lock:
        return _run_economy_tick_locked(db, world_id, at=at)


def _run_economy_tick_locked(
    db: Session,
    world_id: str,
    *,
    at: datetime | None = None,
) -> EconomyTick:
    now = (at or datetime.now(UTC)).astimezone(UTC)
    period_start = period_start_for(now)
    if period_start > period_start_for(datetime.now(UTC)):
        raise DomainError(422, "economy.future_period", "Future economy ticks are not allowed")
    period_end = period_start + timedelta(hours=1)
    period_key = period_key_for(period_start)

    try:
        world = db.scalar(select(World).where(World.id == world_id).with_for_update())
        if world is None:
            raise DomainError(404, "world.not_found", "World not found")
        existing = db.scalar(
            select(EconomyTick).where(
                EconomyTick.world_id == world_id,
                EconomyTick.period_key == period_key,
            )
        )
        if existing is not None:
            return existing

        tick = EconomyTick(
            world_id=world_id,
            period_key=period_key,
            period_start=period_start,
            period_end=period_end,
            status="processing",
        )
        db.add(tick)
        db.flush()
        markets = ensure_city_sector_markets(db, world_id)
        company_count = 0

        for market in markets:
            market_events = market_event_modifiers(
                db,
                world_id=world_id,
                city_id=market.city_id,
                industry=market.industry,
                at=now,
            )
            effective_demand_units = max(
                0,
                market.demand_units * market_events.demand_multiplier_bps // 10_000,
            )
            company_rows = list(
                db.execute(
                    select(Company, District)
                    .join(District, District.id == Company.district_id)
                    .where(
                        Company.world_id == world_id,
                        Company.industry == market.industry,
                        District.city_id == market.city_id,
                    )
                    .order_by(Company.id)
                    .with_for_update()
                ).all()
            )
            breakdowns: dict[
                str,
                tuple[int, dict[str, int], SpecialistEffects],
            ] = {}
            company_event_breakdowns: dict[str, EventModifiers] = {}
            participants: list[MarketParticipant] = []
            for company, district in company_rows:
                points, modifiers = attractiveness_breakdown(_company_factors(company, district))
                effects = company_specialist_effects(db, company.id)
                event_effects = company_event_modifiers(db, company, district, now)
                points += effects.attractiveness_bonus_points
                modifiers["specialist_attractiveness"] = effects.attractiveness_bonus_points
                breakdowns[company.id] = (points, modifiers, effects)
                company_event_breakdowns[company.id] = event_effects
                participants.append(
                    MarketParticipant(
                        company_id=company.id,
                        capacity_units=(company.capacity + effects.capacity_bonus_units),
                        attractiveness_points=points,
                    )
                )
            allocations = allocate_market(effective_demand_units, participants)
            total_allocated = sum(allocations.values())
            financials: dict[str, tuple[int, int, int]] = {}
            strategic_cost_bps: dict[str, int] = {}
            for company, _ in company_rows:
                allocated_units = allocations[company.id]
                _, _, effects = breakdowns[company.id]
                event_effects = company_event_breakdowns[company.id]
                base_revenue_cents = _checked_money(allocated_units * market.unit_revenue_cents)
                revenue_cents = _checked_money(
                    base_revenue_cents * (10_000 + effects.revenue_bonus_bps) // 10_000
                )
                revenue_cents = _checked_money(
                    revenue_cents * event_effects.revenue_multiplier_bps // 10_000
                )
                base_cost_cents = _checked_money(
                    market.fixed_cost_cents + allocated_units * market.variable_cost_per_unit_cents
                )
                cost_cents = _checked_money(
                    base_cost_cents * (10_000 - effects.cost_reduction_bps) // 10_000
                )
                disruption_bps = active_company_cost_increase_bps(db, company.id, now)
                strategic_cost_bps[company.id] = disruption_bps
                cost_cents = _checked_money(cost_cents * (10_000 + disruption_bps) // 10_000)
                cost_cents = _checked_money(
                    cost_cents * event_effects.cost_multiplier_bps // 10_000
                )
                financials[company.id] = (
                    revenue_cents,
                    cost_cents,
                    _checked_money(revenue_cents - cost_cents),
                )
            market_report = MarketEconomyReport(
                tick_id=tick.id,
                market_id=market.id,
                demand_units=effective_demand_units,
                allocated_units=total_allocated,
                unfilled_units=effective_demand_units - total_allocated,
                allocated_share_bps=market_share_bps(effective_demand_units, total_allocated),
                company_count=len(company_rows),
                total_revenue_cents=sum(item[0] for item in financials.values()),
                total_cost_cents=sum(item[1] for item in financials.values()),
                total_profit_cents=sum(item[2] for item in financials.values()),
                inputs_json={
                    "market_version": market.version,
                    "unit_revenue_cents": market.unit_revenue_cents,
                    "variable_cost_per_unit_cents": market.variable_cost_per_unit_cents,
                    "fixed_cost_cents": market.fixed_cost_cents,
                    "base_demand_units": market.demand_units,
                    "event_demand_multiplier_bps": (market_events.demand_multiplier_bps),
                    "event_instance_count": len(market_events.event_instance_ids),
                },
            )
            db.add(market_report)
            db.flush()
            emit_realtime_event(
                db,
                world_id=world_id,
                event_type="market.snapshot.created",
                payload={
                    "tick_id": tick.id,
                    "market_id": market.id,
                    "city_id": market.city_id,
                    "industry": market.industry,
                },
                audience_type="city",
                audience_id=market.city_id,
                dedupe_key=f"market-snapshot:{tick.id}:{market.id}",
                at=now,
            )

            for company, district in company_rows:
                allocated_units = allocations[company.id]
                revenue_cents, cost_cents, profit_cents = financials[company.id]
                report_id = uuid_str()
                value_before_cents = company.enterprise_value_cents
                settlement = settle_company_operating_result(
                    db,
                    world_id=world_id,
                    company_id=company.id,
                    company_account=company.account,
                    profit_cents=profit_cents,
                    idempotency_key=f"economy:{period_key}:{company.id}",
                    reference_id=report_id,
                )
                company.debt_cents = _checked_money(
                    company.debt_cents + settlement.debt_delta_cents
                )
                company.revenue_cents = revenue_cents
                company.cost_cents = cost_cents
                company.profit_cents = profit_cents
                company.market_share_bps = market_share_bps(effective_demand_units, allocated_units)
                company.enterprise_value_cents = enterprise_value_v1(
                    capacity=company.capacity,
                    quality=company.quality,
                    innovation_bps=company.innovation_bps,
                    profit_cents=company.profit_cents,
                    account_balance_cents=company.account.balance_cents,
                    debt_cents=company.debt_cents,
                )
                company.version += 1
                points, modifiers, effects = breakdowns[company.id]
                event_effects = company_event_breakdowns[company.id]
                modifiers.update(
                    {
                        "specialist_capacity": effects.capacity_bonus_units,
                        "specialist_revenue_bps": effects.revenue_bonus_bps,
                        "specialist_cost_reduction_bps": (effects.cost_reduction_bps),
                        "strategic_cost_increase_bps": strategic_cost_bps[company.id],
                        "event_instance_count": len(event_effects.event_instance_ids),
                        "event_revenue_multiplier_bps": (event_effects.revenue_multiplier_bps),
                        "event_cost_multiplier_bps": (event_effects.cost_multiplier_bps),
                        "event_demand_multiplier_bps": (event_effects.demand_multiplier_bps),
                        "event_specialist_salary_multiplier_bps": (
                            event_effects.specialist_salary_multiplier_bps
                        ),
                        "event_real_estate_cost_multiplier_bps": (
                            event_effects.real_estate_cost_multiplier_bps
                        ),
                        "event_reputation_delta_bps": (event_effects.reputation_delta_bps),
                        "event_investigation_pressure_delta": (
                            event_effects.investigation_pressure_delta
                        ),
                        "event_stock_risk_delta_bps": (event_effects.stock_risk_delta_bps),
                        "event_contract_probability_delta_bps": (
                            event_effects.contract_probability_delta_bps
                        ),
                    }
                )
                db.add(
                    CompanyEconomyReport(
                        id=report_id,
                        tick_id=tick.id,
                        market_report_id=market_report.id,
                        company_id=company.id,
                        settlement_transaction_id=(
                            settlement.transaction.id
                            if settlement.transaction is not None
                            else None
                        ),
                        attractiveness_points=points,
                        allocated_units=allocated_units,
                        market_share_bps=company.market_share_bps,
                        revenue_cents=revenue_cents,
                        cost_cents=cost_cents,
                        profit_cents=profit_cents,
                        cash_delta_cents=settlement.cash_delta_cents,
                        debt_delta_cents=settlement.debt_delta_cents,
                        enterprise_value_before_cents=value_before_cents,
                        enterprise_value_after_cents=company.enterprise_value_cents,
                        inputs_json={
                            "capacity_units": (company.capacity + effects.capacity_bonus_units),
                            "quality_bps": company.quality,
                            "reputation_bps": company.reputation_bps,
                            "compliance_bps": company.compliance_bps,
                            "innovation_bps": company.innovation_bps,
                            "risk_bps": company.risk_bps,
                            "investigation_pressure_bps": (company.investigation_pressure_bps),
                            "district_economic_activity": (district.economic_activity),
                            "district_prosperity": district.prosperity,
                        },
                        modifiers_json=modifiers,
                    )
                )
                if profit_cents > 0:
                    record_engagement_event(
                        db,
                        profile_id=company.founder_profile_id,
                        event_type="company.first_profit",
                        source_type="company",
                        source_id=company.id,
                        idempotency_key=f"company.first_profit:{company.id}",
                        payload={"tick_id": tick.id, "profit_cents": profit_cents},
                        occurred_at=now,
                    )
                db.add(
                    snapshot_company(
                        company,
                        reason="economy_tick",
                        reference_id=tick.id,
                    )
                )
                emit_realtime_event(
                    db,
                    world_id=world_id,
                    event_type="company.metrics.updated",
                    payload={
                        "company_id": company.id,
                        "version": company.version,
                        "tick_id": tick.id,
                    },
                    audience_type="city",
                    audience_id=market.city_id,
                    dedupe_key=f"company-metrics:{tick.id}:{company.id}",
                    at=now,
                )
                company_count += 1

        tick.company_count = company_count
        tick.market_count = len(markets)
        tick.status = "completed"
        tick.completed_at = datetime.now(UTC)
        db.commit()
        db.refresh(tick)
        return tick
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(EconomyTick).where(
                EconomyTick.world_id == world_id,
                EconomyTick.period_key == period_key,
            )
        )
        if existing is not None:
            return existing
        raise
    except Exception:
        db.rollback()
        raise


def run_due_economy_ticks(db: Session, *, at: datetime | None = None) -> int:
    world_ids = list(
        db.scalars(select(World.id).where(World.status == "active").order_by(World.id))
    )
    for world_id in world_ids:
        run_economy_tick(db, world_id, at=at)
    return len(world_ids)


def latest_economy_tick(db: Session, world_id: str) -> EconomyTick | None:
    return db.scalar(
        select(EconomyTick)
        .where(EconomyTick.world_id == world_id, EconomyTick.status == "completed")
        .order_by(EconomyTick.period_start.desc())
        .limit(1)
    )


def next_economy_tick_at(last_tick: EconomyTick | None, *, now: datetime | None = None) -> datetime:
    current = now or datetime.now(UTC)
    if last_tick is not None:
        return as_utc(last_tick.period_end)
    return period_start_for(current) + timedelta(hours=1)


def list_company_economy_reports(
    db: Session,
    profile: PlayerProfile,
    company_id: str,
    *,
    limit: int = 24,
) -> list[CompanyEconomyReport]:
    company = db.scalar(
        select(Company.id).where(
            Company.id == company_id,
            Company.world_id == profile.world_id,
        )
    )
    if company is None:
        raise DomainError(404, "company.not_found", "Company not found")
    return list(
        db.scalars(
            select(CompanyEconomyReport)
            .where(CompanyEconomyReport.company_id == company_id)
            .order_by(CompanyEconomyReport.created_at.desc())
            .limit(limit)
        )
    )


def list_city_sector_markets(
    db: Session,
    profile: PlayerProfile,
) -> list[CitySectorMarket]:
    if profile.city_id is None:
        raise DomainError(409, "profile.city_required", "Select a city first")
    return list(
        db.scalars(
            select(CitySectorMarket)
            .where(
                CitySectorMarket.world_id == profile.world_id,
                CitySectorMarket.city_id == profile.city_id,
            )
            .order_by(CitySectorMarket.industry)
        )
    )


def list_market_economy_reports(
    db: Session,
    profile: PlayerProfile,
    market_id: str,
    *,
    limit: int = 24,
) -> list[MarketEconomyReport]:
    market = db.scalar(
        select(CitySectorMarket.id).where(
            CitySectorMarket.id == market_id,
            CitySectorMarket.world_id == profile.world_id,
            CitySectorMarket.city_id == profile.city_id,
        )
    )
    if market is None:
        raise DomainError(404, "economy.market_not_found", "Economy market not found")
    return list(
        db.scalars(
            select(MarketEconomyReport)
            .join(EconomyTick, EconomyTick.id == MarketEconomyReport.tick_id)
            .where(MarketEconomyReport.market_id == market_id)
            .order_by(EconomyTick.period_start.desc())
            .limit(limit)
        )
    )
