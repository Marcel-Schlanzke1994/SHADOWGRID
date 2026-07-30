from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.ai import run_ai_tick
from shadowgrid.bootstrap import bootstrap_world
from shadowgrid.cartels import ensure_cartel_account
from shadowgrid.companies import create_company
from shadowgrid.config import PROJECT_ROOT, get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.domain import apply_profile_resource, create_player_profile
from shadowgrid.economy import run_economy_tick
from shadowgrid.exchange import create_ipo, place_order
from shadowgrid.game_config import (
    AI_STRATEGIES,
    CARTEL_PROJECT_TEMPLATES,
    START_RESOURCES,
    WORLD_EVENTS,
)
from shadowgrid.models import (
    CartelDistrictInfluence,
    CartelProject,
    Company,
    District,
    Evidence,
    IntelligenceReport,
    IntelligenceReportOffer,
    IntelReport,
    LedgerEntry,
    Operation,
    Organization,
    OrganizationMembership,
    PlayerProfile,
    ResourceBalance,
    SeedRun,
    Treaty,
    User,
    WorldEvent,
    as_utc,
)
from shadowgrid.security import hash_password
from shadowgrid.specialists import refresh_specialist_market
from shadowgrid.world_events import activate_event

DEMO_ACCOUNTS = {
    "new-player@example.com": ("New Player", False, False),
    "advanced@example.com": ("Advanced Player", False, False),
    "member@example.com": ("Organization Member", False, False),
    "director@example.com": ("Organization Director", False, False),
    "moderator@example.com": ("Moderator", False, True),
    "admin@example.com": ("Administrator", True, True),
}

_RESOURCE_FIELDS = (
    "cash",
    "capital",
    "influence",
    "intelligence",
    "logistics_capacity",
    "personnel_capacity",
)


def ensure_demo_resource_balance(
    db: Session,
    profile: PlayerProfile,
    *,
    starting_cash_cents: int,
) -> None:
    if db.get(ResourceBalance, profile.id) is not None:
        return
    totals = {
        resource_type: Decimal(total)
        for resource_type, total in db.execute(
            select(
                LedgerEntry.resource_type,
                func.coalesce(func.sum(LedgerEntry.amount), 0),
            )
            .where(
                LedgerEntry.owner_type == "profile",
                LedgerEntry.owner_id == profile.id,
            )
            .group_by(LedgerEntry.resource_type)
        )
    }
    balance = ResourceBalance(
        profile_id=profile.id,
        **{field: totals.get(field, Decimal(0)) for field in _RESOURCE_FIELDS},
    )
    db.add(balance)
    db.flush()
    if totals:
        return
    starting_resources: dict[str, Decimal | int] = {
        **START_RESOURCES,
        "cash": Decimal(starting_cash_cents) / Decimal(100),
    }
    for resource_type, amount in starting_resources.items():
        apply_profile_resource(
            db,
            profile.id,
            resource_type,
            amount,
            reason="demo_seed_recovery",
            reference_type="profile",
            reference_id=profile.id,
            idempotency_key=f"seed:{profile.id}:resource-recovery",
        )


def load_or_create_credentials() -> dict[str, str]:
    local = PROJECT_ROOT / ".local"
    local.mkdir(mode=0o700, exist_ok=True)
    path = local / "demo-credentials.txt"
    if path.exists():
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                email, password = line.split("=", 1)
                values[email.strip()] = password.strip()
        if set(DEMO_ACCOUNTS).issubset(values):
            return values
    values = {email: f"Sg!{secrets.token_urlsafe(15)}9a" for email in DEMO_ACCOUNTS}
    body = "# Generated local demo credentials. Never commit or share this file.\n" + "\n".join(
        f"{email}={password}" for email, password in values.items()
    )
    path.write_text(body + "\n", encoding="utf-8")
    return values


def seed() -> None:
    settings = get_settings()
    if not settings.demo_mode_enabled:
        raise RuntimeError("Demo seed is disabled outside local development")
    credentials = load_or_create_credentials()
    db = SessionLocal()
    try:
        prior_seed = db.scalar(
            select(SeedRun).where(
                SeedRun.seed_key == "demo",
                SeedRun.version == settings.seed_version,
            )
        )
        if prior_seed is not None and prior_seed.random_seed != settings.demo_random_seed:
            raise RuntimeError("Configured demo seed inputs differ from the recorded seed version")
        world = bootstrap_world(db, settings)
        db.flush()
        districts = list(
            db.scalars(
                select(District)
                .where(District.world_id == world.id, District.city_id.is_not(None))
                .order_by(District.slug)
            )
        )
        demo_users: dict[str, User] = {}
        for email, (name, is_admin, is_moderator) in DEMO_ACCOUNTS.items():
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    password_hash=hash_password(credentials[email]),
                    display_name=name,
                    locale="de" if "director" in email else "en",
                    email_verified=True,
                    is_admin=is_admin,
                    is_moderator=is_moderator,
                )
                db.add(user)
                db.flush()
            demo_users[email] = user
        npc_users: list[User] = []
        for index in range(20):
            email = f"npc-{index + 1:02d}@shadowgrid.invalid"
            user = db.scalar(select(User).where(User.email == email))
            if user is None:
                user = User(
                    email=email,
                    password_hash=hash_password(secrets.token_urlsafe(32)),
                    display_name=f"Köln Contact {index + 1:02d}",
                    email_verified=True,
                )
                db.add(user)
                db.flush()
            npc_users.append(user)
        profiles = []
        ai_user_strategies = {
            user.id: AI_STRATEGIES[index]
            for index, user in enumerate(npc_users[: len(AI_STRATEGIES)])
        }
        all_users = list(demo_users.values()) + npc_users
        archetypes = (
            "family_network",
            "street_alliance",
            "business_consortium",
            "cyber_collective",
        )
        for index, user in enumerate(all_users):
            profile = create_player_profile(
                db,
                user,
                world,
                f"Network {index + 1:02d}",
                archetypes[index % 4],
                districts[index % len(districts)],
                f"seed:{user.id}",
                settings,
            )
            ensure_demo_resource_balance(
                db,
                profile,
                starting_cash_cents=settings.starting_cash_cents,
            )
            profile.tutorial_step = 7 if index else 0
            if user.id in ai_user_strategies:
                profile.is_local_ai = True
                profile.ai_strategy = ai_user_strategies[user.id]
                profile.ai_paused = False
                profile.ai_seed = 10_001 + list(ai_user_strategies).index(user.id)
            if index > 0:
                apply_profile_resource(
                    db,
                    profile.id,
                    "cash",
                    Decimal(index * 1_250),
                    reason="demo_seed_adjustment",
                    reference_type="profile",
                    reference_id=profile.id,
                    idempotency_key=f"seed:{user.id}:cash-adjustment",
                )
                apply_profile_resource(
                    db,
                    profile.id,
                    "capital",
                    Decimal(index * 700),
                    reason="demo_seed_adjustment",
                    reference_type="profile",
                    reference_id=profile.id,
                    idempotency_key=f"seed:{user.id}:capital-adjustment",
                )
                profile.investigation_pressure = min(90, index * 3)
            profiles.append(profile)
        db.commit()

        ai_profiles = [
            profile
            for profile in profiles
            if profile.is_local_ai and profile.ai_strategy is not None
        ]
        ai_company_specs = (
            (0, "Rheinwerk Gastro", "gastronomy"),
            (0, "Rheinwerk Logistik", "logistics"),
            (1, "Domlinie Logistik", "logistics"),
            (1, "Domlinie Technologie", "technology"),
            (2, "Silberstrom Technologie", "technology"),
            (2, "Silberstrom Gastro", "gastronomy"),
            (3, "Westhafen Logistik", "logistics"),
            (3, "Westhafen Gastro", "gastronomy"),
            (4, "Kranhaus Systeme", "technology"),
        )
        for spec_index, (profile_index, name, industry) in enumerate(ai_company_specs):
            ai_profile = ai_profiles[profile_index]
            if ai_profile.home_district_id is None:
                raise RuntimeError("Demo AI profile has no home district")
            create_company(
                db,
                ai_profile,
                name=name,
                industry=industry,
                district_id=ai_profile.home_district_id,
                idempotency_key=f"seed:ai-company:{spec_index}",
                settings=settings,
                request_id="demo-seed",
            )

        city_id = districts[0].city_id
        if city_id is None:
            raise RuntimeError("Demo city is missing")
        refresh_specialist_market(db, world.id, city_id)
        db.commit()
        simulation_start = as_utc(world.starts_at) - timedelta(hours=3)
        for offset in range(3):
            tick_at = simulation_start + timedelta(hours=offset)
            run_economy_tick(db, world.id, at=tick_at)
            run_ai_tick(db, world.id, settings=settings, at=tick_at)

        exchange_specs = (
            ("Rheinwerk Logistik", "RWL", 100_000, 4_000),
            ("Domlinie Logistik", "DOML", 100_000, 3_000),
            ("Westhafen Logistik", "WHL", 100_000, 2_000),
        )
        demo_listings = []
        for company_name, symbol, total_shares, offered_shares in exchange_specs:
            company = db.scalar(
                select(Company).where(
                    Company.world_id == world.id,
                    Company.name == company_name,
                )
            )
            if company is None:
                raise RuntimeError(f"Demo exchange company is missing: {company_name}")
            founder = db.get(PlayerProfile, company.founder_profile_id)
            if founder is None:
                raise RuntimeError(f"Demo exchange founder is missing: {company_name}")
            demo_listings.append(
                create_ipo(
                    db,
                    founder,
                    company_id=company.id,
                    symbol=symbol,
                    total_shares=total_shares,
                    offered_shares=offered_shares,
                    idempotency_key=f"seed:ipo:{symbol.lower()}",
                    request_id="demo-seed",
                    settings=settings,
                )
            )

        advanced_profile = next(
            profile
            for profile in profiles
            if profile.user_id == demo_users["advanced@example.com"].id
        )
        member_profile = next(
            profile
            for profile in profiles
            if profile.user_id == demo_users["member@example.com"].id
        )
        director_profile = next(
            profile
            for profile in profiles
            if profile.user_id == demo_users["director@example.com"].id
        )
        featured_listing = demo_listings[0]
        place_order(
            db,
            advanced_profile,
            listing_id=featured_listing.id,
            side="buy",
            order_type="limit",
            quantity=featured_listing.offered_shares,
            limit_price_cents=featured_listing.initial_price_cents,
            expires_at=None,
            idempotency_key="seed:exchange:rwl-primary-buy",
            request_id="demo-seed",
            settings=settings,
        )
        place_order(
            db,
            advanced_profile,
            listing_id=featured_listing.id,
            side="sell",
            order_type="limit",
            quantity=500,
            limit_price_cents=featured_listing.initial_price_cents + 5,
            expires_at=None,
            idempotency_key="seed:exchange:rwl-secondary-sell",
            request_id="demo-seed",
            settings=settings,
        )
        place_order(
            db,
            director_profile,
            listing_id=featured_listing.id,
            side="buy",
            order_type="market",
            quantity=500,
            limit_price_cents=None,
            expires_at=None,
            idempotency_key="seed:exchange:rwl-secondary-buy",
            request_id="demo-seed",
            settings=settings,
        )
        second_listing = demo_listings[1]
        place_order(
            db,
            member_profile,
            listing_id=second_listing.id,
            side="buy",
            order_type="limit",
            quantity=1_000,
            limit_price_cents=second_listing.initial_price_cents,
            expires_at=None,
            idempotency_key="seed:exchange:doml-primary-buy",
            request_id="demo-seed",
            settings=settings,
        )

        organizations: list[Organization] = []
        for index, name in enumerate(
            ("Aurelian Compact", "Northstar Assembly", "Glass Meridian", "Quiet Signal")
        ):
            org = db.scalar(
                select(Organization).where(
                    Organization.world_id == world.id, Organization.name == name
                )
            )
            if org is None:
                org = Organization(
                    world_id=world.id,
                    name=name,
                    tag=("AUR", "NST", "GLM", "QSG")[index],
                    archetype=archetypes[index],
                    description="A fictional player organization in the Cologne game world.",
                    stability=64 + index * 6,
                    treasury_cash=Decimal(20_000 + index * 8_000),
                    treasury_capital=Decimal(10_000 + index * 5_000),
                )
                db.add(org)
                db.flush()
            ensure_cartel_account(db, org)
            organizations.append(org)
        project_types = tuple(CARTEL_PROJECT_TEMPLATES)
        for index, org in enumerate(organizations):
            project = db.scalar(
                select(CartelProject).where(
                    CartelProject.organization_id == org.id,
                    CartelProject.idempotency_key == f"seed:cartel-project:{index}",
                )
            )
            if project is None:
                template = CARTEL_PROJECT_TEMPLATES[project_types[index]]
                project = CartelProject(
                    world_id=world.id,
                    organization_id=org.id,
                    district_id=districts[index % len(districts)].id,
                    project_type=project_types[index],
                    title=template["title"],
                    required_cash_cents=template["cash_cents"],
                    required_influence=template["influence"],
                    required_intelligence=template["intelligence"],
                    influence_kind=template["influence_kind"],
                    influence_reward=template["influence_reward"],
                    idempotency_key=f"seed:cartel-project:{index}",
                    created_by_profile_id=profiles[index + 2].id,
                    starts_at=datetime.now(UTC),
                    ends_at=datetime.now(UTC) + timedelta(hours=template["duration_hours"]),
                )
                db.add(project)
            influence = db.scalar(
                select(CartelDistrictInfluence).where(
                    CartelDistrictInfluence.organization_id == org.id,
                    CartelDistrictInfluence.district_id == districts[index % len(districts)].id,
                    CartelDistrictInfluence.kind == "economic",
                )
            )
            if influence is None:
                db.add(
                    CartelDistrictInfluence(
                        world_id=world.id,
                        organization_id=org.id,
                        district_id=districts[index % len(districts)].id,
                        kind="economic",
                        points=55 + index * 15,
                    )
                )
        for index, profile in enumerate(profiles[2:22]):
            org = organizations[index % 4]
            membership = db.scalar(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == org.id,
                    OrganizationMembership.profile_id == profile.id,
                )
            )
            if membership is None:
                db.add(
                    OrganizationMembership(
                        organization_id=org.id,
                        profile_id=profile.id,
                        role="director" if index < 4 else "member",
                    )
                )
        director_membership = db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.profile_id == director_profile.id
            )
        )
        if director_membership is None:
            db.add(
                OrganizationMembership(
                    organization_id=organizations[0].id,
                    profile_id=director_profile.id,
                    role="director",
                )
            )
        if db.scalar(select(Treaty).limit(1)) is None:
            now = datetime.now(UTC)
            db.add(
                Treaty(
                    world_id=world.id,
                    proposer_org_id=organizations[0].id,
                    recipient_org_id=organizations[1].id,
                    treaty_type="non_aggression",
                    terms_json={"scope": "Iron Harbor", "penalty": 5},
                    visibility="public",
                    status="active",
                    starts_at=now,
                    expires_at=now + timedelta(days=7),
                )
            )
        if (
            db.scalar(select(IntelReport).where(IntelReport.profile_id == advanced_profile.id))
            is None
        ):
            now = datetime.now(UTC)
            db.add(
                IntelReport(
                    profile_id=advanced_profile.id,
                    title="Harbor relationship shift",
                    summary="Sources indicate a probable change in fictional logistics partnerships. Confidence is limited.",
                    target_type="district",
                    target_id=districts[1].id,
                    visible_confidence=62,
                    actual_accuracy=71,
                    source="commercial observer",
                    observed_at=now - timedelta(hours=19),
                    expires_at=now + timedelta(days=2),
                )
            )
            db.add(
                Evidence(
                    profile_id=advanced_profile.id,
                    evidence_type="financial_anomaly",
                    strength=24,
                    source_reference="seed-case",
                )
            )
            from shadowgrid.models import Specialist

            lead = db.scalar(select(Specialist).where(Specialist.profile_id == advanced_profile.id))
            if lead:
                db.add(
                    Operation(
                        profile_id=advanced_profile.id,
                        operation_type="business_expansion",
                        district_id=districts[2].id,
                        specialist_id=lead.id,
                        target="Neon Mile market presence",
                        budget=Decimal("5000"),
                        intelligence_spend=Decimal("2"),
                        risk_posture="balanced",
                        secrecy=60,
                        status="completed",
                        result="success",
                        outcome_json={"effects": {"influence": 2}},
                        started_at=now - timedelta(hours=2),
                        finishes_at=now - timedelta(hours=1),
                        resolved_at=now - timedelta(hours=1),
                    )
                )
                db.add(
                    Operation(
                        profile_id=advanced_profile.id,
                        operation_type="intelligence_gathering",
                        district_id=districts[1].id,
                        specialist_id=lead.id,
                        target="Harbor activity",
                        budget=Decimal("3000"),
                        intelligence_spend=Decimal("1"),
                        risk_posture="cautious",
                        secrecy=75,
                        status="running",
                        started_at=now,
                        finishes_at=now + timedelta(minutes=20),
                    )
                )
        phase_seven_report = db.scalar(
            select(IntelligenceReport).where(
                IntelligenceReport.owner_profile_id == advanced_profile.id,
                IntelligenceReport.source_category == "seeded_market_analysis",
            )
        )
        if phase_seven_report is None:
            phase_seven_report = IntelligenceReport(
                world_id=world.id,
                owner_profile_id=advanced_profile.id,
                target_type="profile",
                target_id=member_profile.id,
                information_type="analyzed",
                category="exchange",
                statement=(
                    "Assessment for exchange: public and commercial signals suggest "
                    "a developing market posture."
                ),
                confidence_bps=6_800,
                accuracy_state="incomplete",
                source_category="seeded_market_analysis",
                snapshot_json={
                    "target_codename": member_profile.codename,
                    "category": "exchange",
                    "cash_band": "developing",
                },
                tradable=True,
                observed_at=as_utc(world.starts_at),
                expires_at=as_utc(world.ends_at),
            )
            db.add(phase_seven_report)
            db.flush()
        phase_seven_offer = db.scalar(
            select(IntelligenceReportOffer).where(
                IntelligenceReportOffer.seller_profile_id == advanced_profile.id,
                IntelligenceReportOffer.idempotency_key == "seed:intelligence-offer:advanced",
            )
        )
        if phase_seven_offer is None:
            db.add(
                IntelligenceReportOffer(
                    world_id=world.id,
                    report_id=phase_seven_report.id,
                    seller_profile_id=advanced_profile.id,
                    price_cents=125_000,
                    status="open",
                    idempotency_key="seed:intelligence-offer:advanced",
                    expires_at=as_utc(world.ends_at),
                )
            )
        activate_event(
            db,
            admin=demo_users["admin@example.com"],
            world_id=world.id,
            event_key="technology_boom",
            version=1,
            scope_type="industry",
            scope_id="technology",
            starts_at=datetime.now(UTC) - timedelta(hours=1),
            duration_minutes=720,
            effect_overrides=None,
            idempotency_key="seed:world-event:technology-boom",
            request_id="demo-seed",
        )
        existing_event_keys = set(
            db.scalars(select(WorldEvent.event_key).where(WorldEvent.world_id == world.id))
        )
        now = datetime.now(UTC)
        for index, (key, effects) in enumerate(WORLD_EVENTS.items()):
            if key not in existing_event_keys:
                start = now - timedelta(hours=2) if index == 0 else now + timedelta(hours=index * 6)
                db.add(
                    WorldEvent(
                        world_id=world.id,
                        event_key=key,
                        title=key.replace("_", " ").title(),
                        status="active" if index == 0 else "scheduled",
                        effects_json=effects,
                        starts_at=start,
                        ends_at=start + timedelta(hours=12),
                    )
                )
        if prior_seed is None:
            db.add(
                SeedRun(
                    seed_key="demo",
                    version=settings.seed_version,
                    random_seed=settings.demo_random_seed,
                )
            )
        db.commit()
        print(
            f"Seed complete. Demo credential path: {PROJECT_ROOT / '.local' / 'demo-credentials.txt'}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
