from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shadowgrid.companies import (
    create_company,
    invest_in_company,
    list_owned_companies,
)
from shadowgrid.config import Settings
from shadowgrid.domain import audit
from shadowgrid.errors import DomainError
from shadowgrid.game_config import COMPANY_INDUSTRIES
from shadowgrid.models import (
    AiDecision,
    AiDecisionTick,
    Company,
    CompanyEconomyReport,
    District,
    EconomyTick,
    PlayerProfile,
    World,
)
from shadowgrid.tick_time import period_key_for

_local_ai_lock = Lock()
_AI_COMPANY_NAMES = (
    "Rheinwerk",
    "Domlinie",
    "Nordkai",
    "Silberstrom",
    "Mediapark",
    "Brückenfeld",
    "Westhafen",
    "Kranhaus",
    "Stadtbogen",
    "Ufernetz",
)


def _decision_seed(profile: PlayerProfile, period_key: str) -> str:
    return hashlib.sha256(f"{profile.ai_seed or 0}:{profile.id}:{period_key}".encode()).hexdigest()


def _investment_for(
    strategy: str,
    company: Company,
    latest_report: CompanyEconomyReport | None,
    seed: str,
) -> str:
    if latest_report is not None and latest_report.profit_cents < 0:
        return "quality" if strategy in {"efficiency", "growth"} else "compliance"
    if (
        strategy == "market_share"
        and latest_report is not None
        and latest_report.market_share_bps < 2_000
    ):
        return "capacity"
    choices = {
        "growth": ("capacity", "quality"),
        "efficiency": ("quality", "compliance"),
        "innovation": ("innovation", "quality"),
        "market_share": ("capacity", "quality"),
        "stability": ("compliance", "quality"),
    }
    options = choices[strategy]
    return options[int(seed[0:2], 16) % len(options)]


def _ai_action(
    db: Session,
    profile: PlayerProfile,
    tick: AiDecisionTick,
    *,
    settings: Settings,
) -> tuple[str, dict[str, object], dict[str, object]]:
    seed = _decision_seed(profile, tick.period_key)
    companies = list_owned_companies(db, profile)
    strategy = profile.ai_strategy or "growth"
    desired_companies = 2 if strategy in {"growth", "market_share"} else 1
    if len(companies) < desired_companies:
        if profile.home_district_id is None:
            return "hold", {"reason": "district_missing"}, {"status": "skipped"}
        industries = tuple(COMPANY_INDUSTRIES)
        industry = industries[int(seed[2:4], 16) % len(industries)]
        name_root = _AI_COMPANY_NAMES[
            ((profile.ai_seed or 0) + len(companies)) % len(_AI_COMPANY_NAMES)
        ]
        company = create_company(
            db,
            profile,
            name=f"{name_root} {profile.ai_seed or 0}-{len(companies) + 1}",
            industry=industry,
            district_id=profile.home_district_id,
            idempotency_key=f"ai:{tick.period_key}:{profile.id}:found:{len(companies)}",
            settings=settings,
            request_id=f"ai-tick:{tick.id}",
        )
        return (
            "found_company",
            {"strategy": strategy, "industry": industry},
            {"company_id": company.id},
        )

    company = companies[int(seed[4:6], 16) % len(companies)]
    latest_report = db.scalar(
        select(CompanyEconomyReport)
        .where(CompanyEconomyReport.company_id == company.id)
        .order_by(CompanyEconomyReport.created_at.desc())
        .limit(1)
    )
    investment_type = _investment_for(strategy, company, latest_report, seed)
    invested = invest_in_company(
        db,
        profile,
        company_id=company.id,
        investment_type=investment_type,
        idempotency_key=(
            f"ai:{tick.period_key}:{profile.id}:invest:{company.id}:{investment_type}"
        ),
        request_id=f"ai-tick:{tick.id}",
    )
    return (
        "invest",
        {
            "strategy": strategy,
            "company_id": company.id,
            "latest_report_id": latest_report.id if latest_report is not None else None,
            "latest_profit_cents": (
                latest_report.profit_cents if latest_report is not None else None
            ),
            "latest_market_share_bps": (
                latest_report.market_share_bps if latest_report is not None else None
            ),
        },
        {
            "company_id": invested.id,
            "investment_type": investment_type,
            "company_version": invested.version,
        },
    )


def run_ai_tick(
    db: Session,
    world_id: str,
    *,
    settings: Settings,
    at: datetime | None = None,
) -> AiDecisionTick:
    with _local_ai_lock:
        return _run_ai_tick_locked(db, world_id, settings=settings, at=at)


def _run_ai_tick_locked(
    db: Session,
    world_id: str,
    *,
    settings: Settings,
    at: datetime | None,
) -> AiDecisionTick:
    current = at or datetime.now(UTC)
    period_key = period_key_for(current)
    world = db.scalar(select(World).where(World.id == world_id).with_for_update())
    if world is None:
        raise DomainError(404, "world.not_found", "World not found")
    tick = db.scalar(
        select(AiDecisionTick).where(
            AiDecisionTick.world_id == world_id,
            AiDecisionTick.period_key == period_key,
        )
    )
    if tick is not None and tick.status == "completed":
        return tick
    if tick is None:
        economy_tick = db.scalar(
            select(EconomyTick).where(
                EconomyTick.world_id == world_id,
                EconomyTick.period_key == period_key,
                EconomyTick.status == "completed",
            )
        )
        tick = AiDecisionTick(
            world_id=world_id,
            economy_tick_id=economy_tick.id if economy_tick is not None else None,
            period_key=period_key,
        )
        db.add(tick)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            tick = db.scalar(
                select(AiDecisionTick).where(
                    AiDecisionTick.world_id == world_id,
                    AiDecisionTick.period_key == period_key,
                )
            )
            if tick is None:
                raise

    profiles = list(
        db.scalars(
            select(PlayerProfile)
            .where(
                PlayerProfile.world_id == world_id,
                PlayerProfile.is_local_ai.is_(True),
                PlayerProfile.ai_paused.is_(False),
            )
            .order_by(PlayerProfile.ai_seed, PlayerProfile.id)
        )
    )
    for profile in profiles:
        existing_decision = db.scalar(
            select(AiDecision).where(
                AiDecision.tick_id == tick.id,
                AiDecision.profile_id == profile.id,
            )
        )
        if existing_decision is not None:
            continue
        seed = _decision_seed(profile, period_key)
        try:
            action_type, input_data, result_data = _ai_action(
                db,
                profile,
                tick,
                settings=settings,
            )
            status = "completed"
        except DomainError as exc:
            db.rollback()
            tick = db.scalar(
                select(AiDecisionTick).where(
                    AiDecisionTick.world_id == world_id,
                    AiDecisionTick.period_key == period_key,
                )
            )
            if tick is None:
                raise RuntimeError("AI decision tick disappeared after rollback") from exc
            action_type = "hold"
            status = "skipped"
            input_data = {
                "strategy": profile.ai_strategy,
                "error_code": exc.code,
            }
            result_data = {"message": exc.message}
        db.add(
            AiDecision(
                tick_id=tick.id,
                profile_id=profile.id,
                action_type=action_type,
                status=status,
                deterministic_seed=seed,
                input_json=input_data,
                result_json=result_data,
            )
        )
        db.commit()

    tick = db.get(AiDecisionTick, tick.id)
    if tick is None:
        raise RuntimeError("AI decision tick is missing")
    tick.profile_count = len(profiles)
    tick.status = "completed"
    tick.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(tick)
    return tick


def run_due_ai_ticks(
    db: Session,
    *,
    settings: Settings,
    at: datetime | None = None,
) -> int:
    world_ids = list(
        db.scalars(select(World.id).where(World.status == "active").order_by(World.id))
    )
    for world_id in world_ids:
        run_ai_tick(db, world_id, settings=settings, at=at)
    return len(world_ids)


def list_ai_profiles(db: Session, world_id: str | None = None) -> list[PlayerProfile]:
    statement = select(PlayerProfile).where(PlayerProfile.is_local_ai.is_(True))
    if world_id is not None:
        statement = statement.where(PlayerProfile.world_id == world_id)
    return list(db.scalars(statement.order_by(PlayerProfile.ai_seed, PlayerProfile.id)))


def set_ai_paused(
    db: Session,
    profile_id: str,
    *,
    paused: bool,
    actor_user_id: str,
    request_id: str,
) -> PlayerProfile:
    profile = db.scalar(
        select(PlayerProfile)
        .where(
            PlayerProfile.id == profile_id,
            PlayerProfile.is_local_ai.is_(True),
        )
        .with_for_update()
    )
    if profile is None:
        raise DomainError(404, "ai.profile_not_found", "Local AI profile not found")
    profile.ai_paused = paused
    audit(
        db,
        actor_user_id,
        "ai.pause" if paused else "ai.resume",
        "player_profile",
        profile.id,
        request_id,
        {"paused": paused},
    )
    db.commit()
    db.refresh(profile)
    return profile


def list_local_companies(
    db: Session,
    profile: PlayerProfile,
) -> list[Company]:
    if profile.city_id is None:
        return []
    return list(
        db.scalars(
            select(Company)
            .join(PlayerProfile, PlayerProfile.id == Company.founder_profile_id)
            .join(District, District.id == Company.district_id)
            .where(
                Company.world_id == profile.world_id,
                PlayerProfile.is_local_ai.is_(True),
                District.city_id == profile.city_id,
            )
            .order_by(Company.market_share_bps.desc(), Company.name)
        )
    )
