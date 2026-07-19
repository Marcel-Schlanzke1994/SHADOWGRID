from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings, get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.game_config import DISTRICTS, WORLD_EVENTS
from shadowgrid.models import District, User, World, WorldEvent
from shadowgrid.security import hash_password


def bootstrap_world(db: Session, settings: Settings) -> World:
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

    for data in DISTRICTS:
        district = db.scalar(
            select(District).where(District.world_id == world.id, District.slug == data[0])
        )
        if district is None:
            db.add(
                District(
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
            )

    existing_event_keys = set(
        db.scalars(select(WorldEvent.event_key).where(WorldEvent.world_id == world.id))
    )
    now = datetime.now(UTC)
    for index, (key, effects) in enumerate(WORLD_EVENTS.items()):
        if key in existing_event_keys:
            continue
        starts_at = now - timedelta(hours=2) if index == 0 else now + timedelta(hours=index * 6)
        db.add(
            WorldEvent(
                world_id=world.id,
                event_key=key,
                title=key.replace("_", " ").title(),
                status="active" if index == 0 else "scheduled",
                effects_json=effects,
                starts_at=starts_at,
                ends_at=starts_at + timedelta(hours=12),
            )
        )
    return world


def bootstrap_admin(db: Session, settings: Settings) -> None:
    email = settings.bootstrap_admin_email
    password = settings.bootstrap_admin_password
    if email is None and password is None:
        return
    if email is None or password is None:
        raise RuntimeError(
            "BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be configured together"
        )
    normalized_email = str(email).strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None:
        db.add(
            User(
                email=normalized_email,
                password_hash=hash_password(password.get_secret_value()),
                display_name="SHADOWGRID Administrator",
                locale="de",
                email_verified=True,
                is_admin=True,
                is_moderator=True,
            )
        )
        return

    user.email_verified = True
    user.is_admin = True
    user.is_moderator = True


def bootstrap() -> None:
    settings = get_settings()
    with SessionLocal() as db:
        bootstrap_world(db, settings)
        bootstrap_admin(db, settings)
        db.commit()
    print("Production bootstrap complete.")


if __name__ == "__main__":
    bootstrap()
