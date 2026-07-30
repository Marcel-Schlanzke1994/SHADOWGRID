from __future__ import annotations

import threading
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any, Final

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.bonds import archive_world_bonds
from shadowgrid.cartels import cartel_rankings
from shadowgrid.config import Settings
from shadowgrid.domain import apply_profile_resource, audit
from shadowgrid.errors import DomainError
from shadowgrid.exchange import archive_world_exchange
from shadowgrid.finance import money_to_cents
from shadowgrid.game_config import (
    ECONOMY_MARKETS,
    SEASON_SCORING_CATEGORIES,
    SEASON_TEMPLATE_V1,
    START_RESOURCES,
)
from shadowgrid.models import (
    Account,
    AccountReward,
    CartelDistrictInfluence,
    CartelProject,
    CitySectorMarket,
    CommercialContract,
    Company,
    CompanyLoan,
    CompanyOwnership,
    ContractTender,
    DividendEntitlement,
    ExchangeListing,
    ExchangeTrade,
    HallOfFameEntry,
    IntelligenceReport,
    LedgerTransaction,
    LoanApplication,
    Organization,
    OrganizationMembership,
    PlayerProfile,
    ResourceBalance,
    Season,
    SeasonArchiveSnapshot,
    SeasonScoreSnapshot,
    SeasonTemplate,
    ShareClass,
    ShareHolding,
    Treaty,
    User,
    World,
    as_utc,
)
from shadowgrid.real_estate import archive_real_estate_company_use
from shadowgrid.realtime import emit_realtime_event

PHASES: Final = ("setup", "early", "mid", "late", "scoring")
_LOCK = threading.RLock()


@dataclass(frozen=True)
class ScoreCandidate:
    entity_type: str
    entity_id: str
    entity_name: str
    score_value: int
    metrics: dict[str, int | str]


@dataclass(frozen=True)
class SeasonCloseResult:
    season: Season
    score_count: int
    hall_of_fame_count: int
    reward_count: int
    archive_count: int


def _error(status: int, code: str, message: str) -> DomainError:
    return DomainError(status, code, message)


def _iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def _phase_schedule(
    starts_at: datetime,
    duration_minutes: int,
    weights: dict[str, int],
) -> list[dict[str, str]]:
    if tuple(weights) != PHASES or sum(weights.values()) != 10_000:
        raise ValueError("season phase weights must contain all phases and sum to 10000")
    if duration_minutes < 5:
        raise ValueError("season duration must be at least five minutes")
    total_seconds = duration_minutes * 60
    schedule: list[dict[str, str]] = []
    cumulative = 0
    previous_end = starts_at
    for index, phase in enumerate(PHASES):
        cumulative += weights[phase]
        phase_end = (
            starts_at + timedelta(seconds=total_seconds)
            if index == len(PHASES) - 1
            else starts_at + timedelta(seconds=(total_seconds * cumulative) // 10_000)
        )
        if phase_end <= previous_end:
            phase_end = previous_end + timedelta(seconds=1)
        schedule.append({"phase": phase, "ends_at": _iso(phase_end)})
        previous_end = phase_end
    return schedule


def _phase_at(season: Season, at: datetime) -> str:
    normalized = as_utc(at)
    for item in season.phase_schedule_json:
        if normalized < datetime.fromisoformat(str(item["ends_at"])).astimezone(UTC):
            return str(item["phase"])
    return "archived" if season.status == "archived" else "scoring"


def seed_season_template(db: Session, settings: Settings) -> SeasonTemplate:
    template = db.scalar(
        select(SeasonTemplate).where(
            SeasonTemplate.template_key == "cologne_standard",
            SeasonTemplate.version == 1,
        )
    )
    if template is None:
        template = SeasonTemplate(
            template_key="cologne_standard",
            version=1,
            name=SEASON_TEMPLATE_V1["name"],
            duration_minutes=settings.season_days * 24 * 60,
            phase_weights_json=dict(SEASON_TEMPLATE_V1["phase_weights_bps"]),
            goals_json=[dict(goal) for goal in SEASON_TEMPLATE_V1["goals"]],
            scoring_categories_json=list(SEASON_TEMPLATE_V1["scoring_categories"]),
            starting_cash_cents=settings.starting_cash_cents,
        )
        db.add(template)
        db.flush()
    return template


def create_season_from_template(
    db: Session,
    *,
    world: World,
    template: SeasonTemplate,
    starts_at: datetime,
    idempotency_key: str,
    admin: User | None = None,
    request_id: str = "system",
) -> Season:
    with _LOCK:
        existing = db.scalar(
            select(Season).where(
                Season.world_id == world.id,
                Season.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        active = db.scalar(
            select(Season).where(
                Season.world_id == world.id,
                Season.status.in_(("active", "scoring")),
            )
        )
        if active is not None:
            raise _error(409, "season.active_exists", "The world already has an active season")
        if not template.enabled:
            raise _error(409, "season.template_disabled", "Season template is disabled")
        locked_world = db.scalar(select(World).where(World.id == world.id).with_for_update())
        if locked_world is None:
            raise _error(404, "world.not_found", "World not found")
        next_number = int(
            db.scalar(
                select(func.coalesce(func.max(Season.season_number), -1)).where(
                    Season.world_id == world.id
                )
            )
            or 0
        )
        if db.scalar(select(func.count()).select_from(Season).where(Season.world_id == world.id)):
            next_number += 1
        else:
            next_number = max(0, locked_world.season_number)
        normalized_start = as_utc(starts_at)
        schedule = _phase_schedule(
            normalized_start,
            template.duration_minutes,
            {key: int(value) for key, value in template.phase_weights_json.items()},
        )
        season = Season(
            world_id=world.id,
            template_id=template.id,
            season_number=next_number,
            name=f"{template.name} {next_number}",
            phase="setup",
            status="active",
            goals_json=[dict(goal) for goal in template.goals_json],
            scoring_categories_json=list(template.scoring_categories_json),
            phase_schedule_json=schedule,
            starting_cash_cents=template.starting_cash_cents,
            idempotency_key=idempotency_key,
            starts_at=normalized_start,
            ends_at=datetime.fromisoformat(schedule[-1]["ends_at"]).astimezone(UTC),
            phase_changed_at=normalized_start,
        )
        db.add(season)
        db.flush()
        locked_world.season_number = next_number
        locked_world.starts_at = normalized_start
        locked_world.ends_at = season.ends_at
        locked_world.status = "active"
        emit_realtime_event(
            db,
            world_id=world.id,
            event_type="season.created",
            payload={
                "season_id": season.id,
                "season_number": next_number,
                "phase": season.phase,
            },
            dedupe_key=f"season-created:{season.id}",
            at=normalized_start,
            ttl=timedelta(days=30),
        )
        audit(
            db,
            admin.id if admin else None,
            "season.created",
            "season",
            season.id,
            request_id,
            {"template_id": template.id, "season_number": next_number},
        )
        db.commit()
        db.refresh(season)
        return season


def ensure_current_season(
    db: Session,
    world: World,
    settings: Settings,
) -> Season:
    current = db.scalar(
        select(Season)
        .where(
            Season.world_id == world.id,
            Season.status.in_(("active", "scoring")),
        )
        .order_by(Season.season_number.desc())
    )
    if current is not None:
        return current
    template = seed_season_template(db, settings)
    db.flush()
    return create_season_from_template(
        db,
        world=world,
        template=template,
        starts_at=as_utc(world.starts_at),
        idempotency_key=f"bootstrap:{world.id}:season:{world.season_number}",
    )


def current_season(db: Session, world_id: str) -> Season:
    season = db.scalar(
        select(Season)
        .where(
            Season.world_id == world_id,
            Season.status.in_(("active", "scoring")),
        )
        .order_by(Season.season_number.desc())
    )
    if season is None:
        season = db.scalar(
            select(Season).where(Season.world_id == world_id).order_by(Season.season_number.desc())
        )
    if season is None:
        raise _error(404, "season.not_found", "No season exists")
    return season


def _profiles(db: Session, world_id: str) -> list[PlayerProfile]:
    return list(
        db.scalars(
            select(PlayerProfile)
            .where(PlayerProfile.world_id == world_id)
            .order_by(PlayerProfile.codename, PlayerProfile.id)
        )
    )


def _profile_candidates(
    profiles: list[PlayerProfile],
    values: dict[str, int],
    metric_name: str,
) -> list[ScoreCandidate]:
    return [
        ScoreCandidate(
            "profile",
            profile.id,
            profile.codename,
            max(0, values.get(profile.id, 0)),
            {metric_name: max(0, values.get(profile.id, 0))},
        )
        for profile in profiles
    ]


def _score_candidates(
    db: Session,
    season: Season,
) -> dict[str, list[ScoreCandidate]]:
    world_id = season.world_id
    profiles = _profiles(db, world_id)
    profile_ids = [profile.id for profile in profiles]
    cash_values = {
        balance.profile_id: money_to_cents(balance.cash)
        for balance in db.scalars(
            select(ResourceBalance).where(ResourceBalance.profile_id.in_(profile_ids))
        )
    }

    portfolio_values: defaultdict[str, int] = defaultdict(int)
    portfolio_costs: defaultdict[str, int] = defaultdict(int)
    if profile_ids:
        for profile_id, quantity, average_cost, last_price in db.execute(
            select(
                ShareHolding.profile_id,
                ShareHolding.quantity,
                ShareHolding.average_cost_cents,
                ExchangeListing.last_price_cents,
            )
            .join(ShareClass, ShareClass.id == ShareHolding.share_class_id)
            .join(ExchangeListing, ExchangeListing.id == ShareClass.listing_id)
            .where(
                ShareHolding.profile_id.in_(profile_ids),
                ExchangeListing.world_id == world_id,
            )
        ):
            if profile_id is None:
                continue
            portfolio_values[str(profile_id)] += int(quantity) * int(last_price)
            portfolio_costs[str(profile_id)] += int(quantity) * int(average_cost)

    entrepreneur_values: defaultdict[str, int] = defaultdict(int)
    for profile_id, ownership_bps, value_cents in db.execute(
        select(
            CompanyOwnership.owner_profile_id,
            CompanyOwnership.ownership_bps,
            Company.enterprise_value_cents,
        )
        .join(Company, Company.id == CompanyOwnership.company_id)
        .where(Company.world_id == world_id, Company.status != "archived")
    ):
        entrepreneur_values[str(profile_id)] += int(value_cents) * int(ownership_bps) // 10_000

    companies = list(
        db.scalars(
            select(Company)
            .where(Company.world_id == world_id, Company.status != "archived")
            .order_by(Company.name, Company.id)
        )
    )
    company_candidates = [
        ScoreCandidate(
            "company",
            company.id,
            company.name,
            company.enterprise_value_cents,
            {
                "enterprise_value_cents": company.enterprise_value_cents,
                "profit_cents": company.profit_cents,
            },
        )
        for company in companies
    ]
    public_company_candidates = [
        candidate
        for candidate, company in zip(company_candidates, companies, strict=True)
        if company.status == "public"
    ]

    cartel_rows = cartel_rankings(db, world_id)
    cartel_candidates = [
        ScoreCandidate(
            "cartel",
            str(item["cartel_id"]),
            str(item["name"]),
            int(item["score"]),
            {
                "treasury_cents": int(item["treasury_cents"]),
                "member_count": int(item["member_count"]),
                "completed_projects": int(item["completed_projects"]),
                "influence": int(item["influence"]),
            },
        )
        for item in cartel_rows
    ]
    organizations = {
        organization.id: organization
        for organization in db.scalars(
            select(Organization).where(
                Organization.world_id == world_id,
                Organization.status == "active",
            )
        )
    }
    district_values: defaultdict[str, int] = defaultdict(int)
    for organization_id, points in db.execute(
        select(
            CartelDistrictInfluence.organization_id,
            func.coalesce(func.sum(CartelDistrictInfluence.points), 0),
        )
        .where(CartelDistrictInfluence.world_id == world_id)
        .group_by(CartelDistrictInfluence.organization_id)
    ):
        district_values[str(organization_id)] = int(points)
    district_candidates = [
        ScoreCandidate(
            "cartel",
            organization.id,
            organization.name,
            district_values[organization.id],
            {"district_influence_points": district_values[organization.id]},
        )
        for organization in organizations.values()
    ]

    profile_org: dict[str, str] = {}
    if profile_ids:
        for profile_id, organization_id in db.execute(
            select(
                OrganizationMembership.profile_id,
                OrganizationMembership.organization_id,
            ).where(
                OrganizationMembership.profile_id.in_(profile_ids),
                OrganizationMembership.status == "active",
            )
        ):
            profile_org[str(profile_id)] = str(organization_id)
    treaty_counts: Counter[str] = Counter()
    if organizations:
        for proposer, recipient in db.execute(
            select(Treaty.proposer_org_id, Treaty.recipient_org_id).where(
                Treaty.world_id == world_id,
                Treaty.status == "active",
            )
        ):
            treaty_counts[str(proposer)] += 1
            treaty_counts[str(recipient)] += 1
    diplomacy_values = {
        profile.id: profile.legitimacy * 100
        + treaty_counts[profile_org.get(profile.id, "")] * 1_000
        for profile in profiles
    }
    report_counts = {
        str(profile_id): int(count)
        for profile_id, count in db.execute(
            select(
                IntelligenceReport.owner_profile_id,
                func.count(IntelligenceReport.id),
            )
            .where(IntelligenceReport.world_id == world_id)
            .group_by(IntelligenceReport.owner_profile_id)
        )
    }
    information_values = {
        profile.id: int(profile.resources.intelligence * Decimal(100))
        + report_counts.get(profile.id, 0) * 500
        for profile in profiles
    }
    stability_values = {profile.id: profile.stability * 100 for profile in profiles}
    recovery_values = {
        profile.id: max(
            0,
            profile.stability * 100
            + (100 - profile.stress) * 25
            - profile.investigation_pressure * 50,
        )
        for profile in profiles
    }
    dividend_totals = {
        str(profile_id): int(total)
        for profile_id, total in db.execute(
            select(
                DividendEntitlement.recipient_profile_id,
                func.coalesce(func.sum(DividendEntitlement.amount_cents), 0),
            ).group_by(DividendEntitlement.recipient_profile_id)
        )
    }
    dividend_yields = {
        profile.id: (
            dividend_totals.get(profile.id, 0)
            * 10_000
            // max(1, portfolio_costs.get(profile.id, 0))
        )
        for profile in profiles
    }

    return {
        "wealthiest_player": _profile_candidates(profiles, cash_values, "cash_cents"),
        "portfolio_value": _profile_candidates(
            profiles, dict(portfolio_values), "portfolio_value_cents"
        ),
        "entrepreneur": _profile_candidates(
            profiles, dict(entrepreneur_values), "owned_company_value_cents"
        ),
        "largest_company": company_candidates,
        "strongest_cartel": cartel_candidates,
        "largest_public_company": public_company_candidates,
        "dividend_yield": _profile_candidates(profiles, dividend_yields, "dividend_yield_bps"),
        "district_control": district_candidates,
        "diplomacy": _profile_candidates(profiles, diplomacy_values, "diplomacy_points"),
        "information_network": _profile_candidates(
            profiles, information_values, "information_points"
        ),
        "stability": _profile_candidates(profiles, stability_values, "stability_points"),
        "crisis_recovery": _profile_candidates(profiles, recovery_values, "recovery_points"),
    }


def _capture_scores(
    db: Session, season: Season, captured_at: datetime
) -> list[SeasonScoreSnapshot]:
    existing = list(
        db.scalars(select(SeasonScoreSnapshot).where(SeasonScoreSnapshot.season_id == season.id))
    )
    if existing:
        return existing
    candidates_by_category = _score_candidates(db, season)
    snapshots: list[SeasonScoreSnapshot] = []
    for category in season.scoring_categories_json:
        if category not in SEASON_SCORING_CATEGORIES:
            raise RuntimeError(f"unsupported season score category: {category}")
        candidates = sorted(
            candidates_by_category.get(category, []),
            key=lambda item: (
                -item.score_value,
                item.entity_name.casefold(),
                item.entity_id,
            ),
        )
        score_counts = Counter(item.score_value for item in candidates)
        previous_score: int | None = None
        rank = 0
        for position, candidate in enumerate(candidates, start=1):
            if candidate.score_value != previous_score:
                rank = position
                previous_score = candidate.score_value
            snapshots.append(
                SeasonScoreSnapshot(
                    season_id=season.id,
                    category=category,
                    entity_type=candidate.entity_type,
                    entity_id=candidate.entity_id,
                    entity_name=candidate.entity_name,
                    score_value=candidate.score_value,
                    rank=rank,
                    tied=score_counts[candidate.score_value] > 1,
                    metrics_json=dict(candidate.metrics),
                    tie_break_json={
                        "rule": "competition_rank_equal_score",
                        "display_order": "entity_name_then_uuid",
                        "position": position,
                        "tie_size": score_counts[candidate.score_value],
                    },
                    captured_at=captured_at,
                )
            )
    db.add_all(snapshots)
    db.flush()
    return snapshots


def _hall_of_fame(
    db: Session,
    season: Season,
    scores: list[SeasonScoreSnapshot],
    captured_at: datetime,
) -> list[HallOfFameEntry]:
    existing = list(
        db.scalars(select(HallOfFameEntry).where(HallOfFameEntry.season_id == season.id))
    )
    if existing:
        return existing
    entries = [
        HallOfFameEntry(
            season_id=season.id,
            season_number=season.season_number,
            category=score.category,
            entity_type=score.entity_type,
            entity_id=score.entity_id,
            entity_name=score.entity_name,
            score_value=score.score_value,
            rank=score.rank,
            tied=score.tied,
            metrics_json=dict(score.metrics_json),
            awarded_at=captured_at,
        )
        for score in scores
        if score.rank <= 3
    ]
    db.add_all(entries)
    db.flush()
    return entries


def _reward_user_ids(
    db: Session,
    score: SeasonScoreSnapshot,
) -> set[str]:
    if score.entity_type == "profile":
        profile = db.get(PlayerProfile, score.entity_id)
        return {profile.user_id} if profile is not None else set()
    if score.entity_type == "company":
        company = db.get(Company, score.entity_id)
        if company is None:
            return set()
        profile = db.get(PlayerProfile, company.founder_profile_id)
        return {profile.user_id} if profile is not None else set()
    if score.entity_type == "cartel":
        return set(
            db.scalars(
                select(PlayerProfile.user_id)
                .join(
                    OrganizationMembership,
                    OrganizationMembership.profile_id == PlayerProfile.id,
                )
                .where(
                    OrganizationMembership.organization_id == score.entity_id,
                    OrganizationMembership.status == "active",
                )
            )
        )
    return set()


def _award_rewards(
    db: Session,
    season: Season,
    scores: list[SeasonScoreSnapshot],
    captured_at: datetime,
) -> list[AccountReward]:
    existing = list(db.scalars(select(AccountReward).where(AccountReward.season_id == season.id)))
    if existing:
        return existing
    rewards: list[AccountReward] = []
    awarded_keys: set[tuple[str, str, str]] = set()
    for score in scores:
        if score.rank != 1:
            continue
        for user_id in sorted(_reward_user_ids(db, score)):
            for reward_type, suffix, label in (
                (
                    "achievement",
                    "winner",
                    f"Season {season.season_number} {score.category} winner",
                ),
                ("title", "champion", f"{score.category.replace('_', ' ').title()} Champion"),
                ("cosmetic", "badge", f"Season {season.season_number} champion badge"),
            ):
                reward_key = f"season:{season.season_number}:{score.category}:{suffix}"
                unique_key = (user_id, reward_type, reward_key)
                if unique_key in awarded_keys:
                    continue
                awarded_keys.add(unique_key)
                rewards.append(
                    AccountReward(
                        user_id=user_id,
                        season_id=season.id,
                        reward_type=reward_type,
                        reward_key=reward_key,
                        label=label,
                        metadata_json={
                            "category": score.category,
                            "rank": score.rank,
                            "tied": score.tied,
                        },
                        awarded_at=captured_at,
                    )
                )
    db.add_all(rewards)
    db.flush()
    return rewards


def _archive_snapshot(
    db: Session,
    season: Season,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
    archived_at: datetime,
) -> SeasonArchiveSnapshot:
    snapshot = SeasonArchiveSnapshot(
        season_id=season.id,
        entity_type=entity_type,
        entity_id=entity_id,
        snapshot_json=payload,
        archived_at=archived_at,
    )
    db.add(snapshot)
    return snapshot


def _archive_seasonal_state(
    db: Session,
    season: Season,
    archived_at: datetime,
) -> list[SeasonArchiveSnapshot]:
    existing = list(
        db.scalars(
            select(SeasonArchiveSnapshot).where(SeasonArchiveSnapshot.season_id == season.id)
        )
    )
    if existing:
        return existing
    snapshots: list[SeasonArchiveSnapshot] = []
    contracts = list(
        db.scalars(
            select(CommercialContract)
            .where(
                CommercialContract.world_id == season.world_id,
                CommercialContract.status == "active",
            )
            .order_by(CommercialContract.id)
            .with_for_update()
        )
    )
    for contract in contracts:
        snapshots.append(
            _archive_snapshot(
                db,
                season,
                "commercial_contract",
                contract.id,
                {
                    "title": contract.title,
                    "contract_type": contract.contract_type,
                    "issuer_company_id": contract.issuer_company_id,
                    "provider_company_id": contract.provider_company_id,
                    "price_cents_per_period": contract.price_cents_per_period,
                    "duration_periods": contract.duration_periods,
                    "periods_settled": contract.periods_settled,
                    "reserved_capacity_units": contract.reserved_capacity_units,
                    "status": contract.status,
                },
                archived_at,
            )
        )
        contract.status = "cancelled"
    for tender in db.scalars(
        select(ContractTender)
        .where(
            ContractTender.world_id == season.world_id,
            ContractTender.status == "open",
        )
        .order_by(ContractTender.id)
        .with_for_update()
    ):
        tender.status = "cancelled"
        tender.cancelled_at = archived_at

    loans = list(
        db.scalars(
            select(CompanyLoan)
            .where(
                CompanyLoan.world_id == season.world_id,
                CompanyLoan.status == "active",
            )
            .order_by(CompanyLoan.id)
            .with_for_update()
        )
    )
    for loan in loans:
        snapshots.append(
            _archive_snapshot(
                db,
                season,
                "company_loan",
                loan.id,
                {
                    "company_id": loan.company_id,
                    "principal_cents": loan.principal_cents,
                    "interest_rate_bps": loan.interest_rate_bps,
                    "total_repayment_cents": loan.total_repayment_cents,
                    "payments_made": loan.payments_made,
                    "outstanding_principal_cents": loan.outstanding_principal_cents,
                    "outstanding_interest_cents": loan.outstanding_interest_cents,
                    "collateral_score_bps": loan.collateral_score_bps,
                    "status": loan.status,
                },
                archived_at,
            )
        )
        loan.status = "cancelled"
        loan.cancelled_at = archived_at
    for application in db.scalars(
        select(LoanApplication)
        .where(
            LoanApplication.world_id == season.world_id,
            LoanApplication.status == "offered",
        )
        .order_by(LoanApplication.id)
        .with_for_update()
    ):
        application.status = "cancelled"
        application.cancelled_at = archived_at

    for issue, payload in archive_world_bonds(
        db,
        season.world_id,
        at=archived_at,
    ):
        snapshots.append(
            _archive_snapshot(
                db,
                season,
                "bond_issue",
                issue.id,
                payload,
                archived_at,
            )
        )

    for property_, property_payload in archive_real_estate_company_use(
        db,
        season.world_id,
        at=archived_at,
    ):
        snapshots.append(
            _archive_snapshot(
                db,
                season,
                "real_estate_property",
                property_.id,
                property_payload,
                archived_at,
            )
        )

    companies = list(
        db.scalars(
            select(Company)
            .where(Company.world_id == season.world_id, Company.status != "archived")
            .order_by(Company.id)
            .with_for_update()
        )
    )
    for company in companies:
        snapshots.append(
            _archive_snapshot(
                db,
                season,
                "company",
                company.id,
                {
                    "name": company.name,
                    "status": company.status,
                    "enterprise_value_cents": company.enterprise_value_cents,
                    "revenue_cents": company.revenue_cents,
                    "cost_cents": company.cost_cents,
                    "profit_cents": company.profit_cents,
                    "debt_cents": company.debt_cents,
                    "market_share_bps": company.market_share_bps,
                    "account_balance_cents": company.account.balance_cents,
                },
                archived_at,
            )
        )
        company.status = "archived"

    listings = list(
        db.scalars(
            select(ExchangeListing)
            .where(ExchangeListing.world_id == season.world_id)
            .order_by(ExchangeListing.id)
        )
    )
    for listing in listings:
        share_classes = list(
            db.scalars(select(ShareClass).where(ShareClass.listing_id == listing.id))
        )
        holdings = list(
            db.scalars(
                select(ShareHolding).where(
                    ShareHolding.share_class_id.in_(
                        [share_class.id for share_class in share_classes]
                    )
                )
            )
        )
        snapshots.append(
            _archive_snapshot(
                db,
                season,
                "exchange_listing",
                listing.id,
                {
                    "symbol": listing.symbol,
                    "status": listing.status,
                    "last_price_cents": listing.last_price_cents,
                    "total_shares": listing.total_shares,
                    "holdings": [
                        {
                            "owner_type": holding.owner_type,
                            "profile_id": holding.profile_id,
                            "company_id": holding.company_id,
                            "quantity": holding.quantity,
                        }
                        for holding in holdings
                    ],
                },
                archived_at,
            )
        )
    archive_world_exchange(db, season.world_id)

    markets = list(
        db.scalars(
            select(CitySectorMarket)
            .where(CitySectorMarket.world_id == season.world_id)
            .order_by(CitySectorMarket.id)
            .with_for_update()
        )
    )
    for market in markets:
        snapshots.append(
            _archive_snapshot(
                db,
                season,
                "market",
                market.id,
                {
                    "city_id": market.city_id,
                    "industry": market.industry,
                    "demand_units": market.demand_units,
                    "unit_revenue_cents": market.unit_revenue_cents,
                    "variable_cost_per_unit_cents": market.variable_cost_per_unit_cents,
                    "fixed_cost_cents": market.fixed_cost_cents,
                },
                archived_at,
            )
        )
        baseline = ECONOMY_MARKETS[market.industry]
        market.demand_units = baseline["demand_units"]
        market.unit_revenue_cents = baseline["unit_revenue_cents"]
        market.variable_cost_per_unit_cents = baseline["variable_cost_per_unit_cents"]
        market.fixed_cost_cents = baseline["fixed_cost_cents"]
        market.version += 1

    organizations = list(
        db.scalars(
            select(Organization)
            .where(
                Organization.world_id == season.world_id,
                Organization.status == "active",
            )
            .order_by(Organization.id)
            .with_for_update()
        )
    )
    for organization in organizations:
        treasury = db.scalar(
            select(Account).where(
                Account.world_id == season.world_id,
                Account.owner_type == "organization",
                Account.owner_id == organization.id,
            )
        )
        influence = int(
            db.scalar(
                select(func.coalesce(func.sum(CartelDistrictInfluence.points), 0)).where(
                    CartelDistrictInfluence.organization_id == organization.id
                )
            )
            or 0
        )
        snapshots.append(
            _archive_snapshot(
                db,
                season,
                "cartel",
                organization.id,
                {
                    "name": organization.name,
                    "tag": organization.tag,
                    "stability": organization.stability,
                    "reputation": organization.reputation,
                    "treasury_balance_cents": treasury.balance_cents if treasury else 0,
                    "district_influence_points": influence,
                },
                archived_at,
            )
        )
        organization.status = "dissolved"
        organization.dissolved_at = archived_at
        organization.version += 1
    organization_ids = [organization.id for organization in organizations]
    if organization_ids:
        for membership in db.scalars(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id.in_(organization_ids),
                OrganizationMembership.status == "active",
            )
            .with_for_update()
        ):
            membership.status = "left"
        for project in db.scalars(
            select(CartelProject)
            .where(
                CartelProject.organization_id.in_(organization_ids),
                CartelProject.status == "active",
            )
            .with_for_update()
        ):
            project.status = "cancelled"
    db.flush()
    return snapshots


def _reset_profiles(
    db: Session,
    season: Season,
) -> None:
    targets: dict[str, Decimal] = {
        **{key: Decimal(str(value)) for key, value in START_RESOURCES.items()},
        "cash": Decimal(season.starting_cash_cents) / Decimal(100),
    }
    for profile in _profiles(db, season.world_id):
        balance = db.scalar(
            select(ResourceBalance)
            .where(ResourceBalance.profile_id == profile.id)
            .with_for_update()
        )
        if balance is None:
            raise RuntimeError("profile resource balance is missing during season reset")
        for resource_type, target in targets.items():
            current = Decimal(str(getattr(balance, resource_type)))
            delta = target - current
            if delta == 0:
                continue
            apply_profile_resource(
                db,
                profile.id,
                resource_type,
                delta,
                reason="season_reset",
                reference_type="season",
                reference_id=season.id,
                idempotency_key=f"season-reset:{season.id}:{profile.id}:{resource_type}",
                metadata={"season_number": season.season_number},
            )
        profile.loyalty = 65
        profile.legitimacy = 60
        profile.fear = 5
        profile.investigation_pressure = 0
        profile.stress = 0
        profile.stability = 70
        profile.recovery_until = None


def close_season(
    db: Session,
    *,
    season_id: str,
    at: datetime,
    admin: User | None = None,
    request_id: str = "system",
) -> SeasonCloseResult:
    with _LOCK:
        season = db.scalar(select(Season).where(Season.id == season_id).with_for_update())
        if season is None:
            raise _error(404, "season.not_found", "Season not found")
        if season.status == "archived":
            return SeasonCloseResult(
                season=season,
                score_count=int(
                    db.scalar(
                        select(func.count())
                        .select_from(SeasonScoreSnapshot)
                        .where(SeasonScoreSnapshot.season_id == season.id)
                    )
                    or 0
                ),
                hall_of_fame_count=int(
                    db.scalar(
                        select(func.count())
                        .select_from(HallOfFameEntry)
                        .where(HallOfFameEntry.season_id == season.id)
                    )
                    or 0
                ),
                reward_count=int(
                    db.scalar(
                        select(func.count())
                        .select_from(AccountReward)
                        .where(AccountReward.season_id == season.id)
                    )
                    or 0
                ),
                archive_count=int(
                    db.scalar(
                        select(func.count())
                        .select_from(SeasonArchiveSnapshot)
                        .where(SeasonArchiveSnapshot.season_id == season.id)
                    )
                    or 0
                ),
            )
        now = as_utc(at)
        world = db.scalar(select(World).where(World.id == season.world_id).with_for_update())
        if world is None:
            raise _error(404, "world.not_found", "World not found")
        season.phase = "scoring"
        season.status = "scoring"
        season.scoring_started_at = season.scoring_started_at or now
        season.phase_changed_at = now
        scores = _capture_scores(db, season, now)
        hall_of_fame = _hall_of_fame(db, season, scores, now)
        rewards = _award_rewards(db, season, scores, now)
        archives = _archive_seasonal_state(db, season, now)
        _reset_profiles(db, season)
        season.phase = "archived"
        season.status = "archived"
        season.closed_at = now
        season.archived_at = now
        season.phase_changed_at = now
        world.status = "season_break"
        world.ends_at = now
        emit_realtime_event(
            db,
            world_id=world.id,
            event_type="season.archived",
            payload={
                "season_id": season.id,
                "season_number": season.season_number,
                "score_count": len(scores),
            },
            dedupe_key=f"season-archived:{season.id}",
            at=now,
            ttl=timedelta(days=30),
        )
        audit(
            db,
            admin.id if admin else None,
            "season.archived",
            "season",
            season.id,
            request_id,
            {
                "score_count": len(scores),
                "reward_count": len(rewards),
                "archive_count": len(archives),
            },
        )
        db.commit()
        db.refresh(season)
        return SeasonCloseResult(
            season=season,
            score_count=len(scores),
            hall_of_fame_count=len(hall_of_fame),
            reward_count=len(rewards),
            archive_count=len(archives),
        )


def shorten_season(
    db: Session,
    *,
    season_id: str,
    duration_minutes: int,
    admin: User,
    request_id: str,
    at: datetime,
) -> Season:
    with _LOCK:
        season = db.scalar(select(Season).where(Season.id == season_id).with_for_update())
        if season is None:
            raise _error(404, "season.not_found", "Season not found")
        if season.status == "archived":
            raise _error(409, "season.archived", "Archived seasons cannot be shortened")
        current_duration = int(
            (as_utc(season.ends_at) - as_utc(season.starts_at)).total_seconds() // 60
        )
        if duration_minutes >= current_duration:
            raise _error(
                422,
                "season.not_shorter",
                "The new duration must be shorter than the current duration",
            )
        template = db.get(SeasonTemplate, season.template_id)
        if template is None:
            raise RuntimeError("season template is missing")
        schedule = _phase_schedule(
            as_utc(season.starts_at),
            duration_minutes,
            {key: int(value) for key, value in template.phase_weights_json.items()},
        )
        season.phase_schedule_json = schedule
        season.ends_at = datetime.fromisoformat(schedule[-1]["ends_at"]).astimezone(UTC)
        phase = _phase_at(season, at)
        if phase != season.phase:
            season.phase = phase
            season.phase_changed_at = as_utc(at)
        season.status = "scoring" if season.phase == "scoring" else "active"
        if season.phase == "scoring":
            season.scoring_started_at = season.scoring_started_at or as_utc(at)
        audit(
            db,
            admin.id,
            "season.shortened",
            "season",
            season.id,
            request_id,
            {"duration_minutes": duration_minutes},
        )
        db.commit()
        db.refresh(season)
        return season


def simulate_season(
    db: Session,
    *,
    season_id: str,
    at: datetime,
    admin: User | None,
    request_id: str,
) -> SeasonCloseResult | Season:
    with _LOCK:
        season = db.scalar(select(Season).where(Season.id == season_id).with_for_update())
        if season is None:
            raise _error(404, "season.not_found", "Season not found")
        if season.status == "archived":
            return season
        now = as_utc(at)
        if now < as_utc(season.starts_at):
            raise _error(422, "season.simulation_before_start", "Simulation is before season start")
        if now >= as_utc(season.ends_at):
            db.rollback()
            return close_season(
                db,
                season_id=season_id,
                at=now,
                admin=admin,
                request_id=request_id,
            )
        phase = _phase_at(season, now)
        phase_changed = phase != season.phase
        if phase_changed:
            season.phase = phase
            season.phase_changed_at = now
            season.status = "scoring" if phase == "scoring" else "active"
            if phase == "scoring":
                season.scoring_started_at = season.scoring_started_at or now
            emit_realtime_event(
                db,
                world_id=season.world_id,
                event_type="season.phase.changed",
                payload={
                    "season_id": season.id,
                    "season_number": season.season_number,
                    "phase": phase,
                },
                dedupe_key=f"season-phase:{season.id}:{phase}",
                at=now,
                ttl=timedelta(days=7),
            )
        if admin is not None or phase_changed:
            audit(
                db,
                admin.id if admin else None,
                "season.simulated",
                "season",
                season.id,
                request_id,
                {"at": _iso(now), "phase": season.phase},
            )
        db.commit()
        db.refresh(season)
        return season


def advance_due_seasons(db: Session, *, at: datetime | None = None) -> dict[str, int]:
    now = as_utc(at or datetime.now(UTC))
    seasons = list(
        db.scalars(
            select(Season)
            .where(Season.status.in_(("active", "scoring")))
            .order_by(Season.world_id, Season.season_number)
        )
    )
    changed = 0
    archived = 0
    for season in seasons:
        before = season.phase
        result = simulate_season(
            db,
            season_id=season.id,
            at=now,
            admin=None,
            request_id=f"season-worker:{season.id}:{_iso(now)}",
        )
        if isinstance(result, SeasonCloseResult):
            archived += 1
        elif result.phase != before:
            changed += 1
    return {"phase_changes": changed, "archived": archived}


def leaderboard(
    db: Session,
    *,
    season_id: str,
    category: str,
) -> list[SeasonScoreSnapshot]:
    if category not in SEASON_SCORING_CATEGORIES:
        raise _error(422, "season.category_invalid", "Unknown scoring category")
    return list(
        db.scalars(
            select(SeasonScoreSnapshot)
            .where(
                SeasonScoreSnapshot.season_id == season_id,
                SeasonScoreSnapshot.category == category,
            )
            .order_by(
                SeasonScoreSnapshot.rank,
                SeasonScoreSnapshot.entity_name,
                SeasonScoreSnapshot.entity_id,
            )
        )
    )


def live_leaderboard(
    db: Session,
    *,
    season: Season,
    category: str,
) -> list[dict[str, Any]]:
    if category not in SEASON_SCORING_CATEGORIES:
        raise _error(422, "season.category_invalid", "Unknown scoring category")
    candidates = _score_candidates(db, season).get(category, [])
    ordered = sorted(
        candidates,
        key=lambda item: (-item.score_value, item.entity_name.casefold(), item.entity_id),
    )
    counts = Counter(item.score_value for item in ordered)
    result: list[dict[str, Any]] = []
    previous: int | None = None
    rank = 0
    for position, candidate in enumerate(ordered, start=1):
        if candidate.score_value != previous:
            rank = position
            previous = candidate.score_value
        result.append(
            {
                "category": category,
                "entity_type": candidate.entity_type,
                "entity_id": candidate.entity_id,
                "entity_name": candidate.entity_name,
                "score_value": candidate.score_value,
                "rank": rank,
                "tied": counts[candidate.score_value] > 1,
                "metrics_json": candidate.metrics,
                "captured_at": None,
            }
        )
    return result


def season_financial_history_counts(db: Session, world_id: str) -> dict[str, int]:
    """Small auditable boundary used by reset tests and admin diagnostics."""
    return {
        "ledger_transactions": int(
            db.scalar(
                select(func.count())
                .select_from(LedgerTransaction)
                .where(LedgerTransaction.world_id == world_id)
            )
            or 0
        ),
        "exchange_trades": int(
            db.scalar(
                select(func.count())
                .select_from(ExchangeTrade)
                .join(ExchangeListing, ExchangeListing.id == ExchangeTrade.listing_id)
                .where(ExchangeListing.world_id == world_id)
            )
            or 0
        ),
    }
