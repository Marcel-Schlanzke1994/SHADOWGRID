from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from shadowgrid.config import PROJECT_ROOT, get_settings
from shadowgrid.database import Base, SessionLocal, engine
from shadowgrid.domain import create_player_profile
from shadowgrid.game_config import DISTRICTS, WORLD_EVENTS
from shadowgrid.models import (
    District,
    Evidence,
    IntelReport,
    Operation,
    Organization,
    OrganizationMembership,
    Treaty,
    User,
    World,
    WorldEvent,
)
from shadowgrid.security import hash_password

DEMO_ACCOUNTS = {
    "new-player@example.com": ("New Player", False, False),
    "advanced@example.com": ("Advanced Player", False, False),
    "member@example.com": ("Organization Member", False, False),
    "director@example.com": ("Organization Director", False, False),
    "moderator@example.com": ("Moderator", False, True),
    "admin@example.com": ("Administrator", True, True),
}


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
    Base.metadata.create_all(bind=engine)
    credentials = load_or_create_credentials()
    db = SessionLocal()
    try:
        world = db.scalar(select(World).where(World.slug == "vesper-season-0"))
        if world is None:
            now = datetime.now(UTC)
            world = World(
                slug="vesper-season-0",
                name="Vesper Metropolitan Zone — Season 0",
                status="active",
                starts_at=now,
                ends_at=now + timedelta(days=settings.season_days),
                season_number=0,
            )
            db.add(world)
            db.flush()
        districts: list[District] = []
        for data in DISTRICTS:
            district = db.scalar(
                select(District).where(District.world_id == world.id, District.slug == data[0])
            )
            if district is None:
                district = District(
                    world_id=world.id,
                    slug=data[0],
                    name=data[1],
                    prosperity=data[2],
                    employment=data[3],
                    safety=data[4],
                    authority_presence=data[5],
                    digital_infrastructure=data[6],
                    property_value=data[7],
                    public_trust=data[8],
                    media_attention=data[9],
                    economic_activity=data[10],
                    social_stability=data[11],
                    map_x=data[12],
                    map_y=data[13],
                    map_points=data[14],
                )
                db.add(district)
                db.flush()
            districts.append(district)
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
                    display_name=f"Vesper Contact {index + 1:02d}",
                    email_verified=True,
                )
                db.add(user)
                db.flush()
            npc_users.append(user)
        profiles = []
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
            )
            profile.tutorial_step = 7 if index else 0
            if index > 0:
                profile.resources.cash += Decimal(index * 1_250)
                profile.resources.capital += Decimal(index * 700)
                profile.investigation_pressure = min(90, index * 3)
            profiles.append(profile)
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
                    description="A fictional Vesper player organization.",
                    stability=64 + index * 6,
                    treasury_cash=Decimal(20_000 + index * 8_000),
                    treasury_capital=Decimal(10_000 + index * 5_000),
                )
                db.add(org)
                db.flush()
            organizations.append(org)
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
        director_profile = next(
            p for p in profiles if p.user_id == demo_users["director@example.com"].id
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
        advanced_profile = next(
            p for p in profiles if p.user_id == demo_users["advanced@example.com"].id
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
        db.commit()
        print(
            f"Seed complete. Demo credential path: {PROJECT_ROOT / '.local' / 'demo-credentials.txt'}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed()
