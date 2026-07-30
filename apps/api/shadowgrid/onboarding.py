from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.domain import (
    create_player_profile,
    get_idempotent,
    remember_idempotent,
)
from shadowgrid.models import City, District, PlayerProfile, User, World


def list_active_cities(db: Session) -> list[City]:
    return list(
        db.scalars(
            select(City)
            .join(World, World.id == City.world_id)
            .where(City.status == "active", World.status == "active")
            .order_by(City.name)
        )
    )


def list_city_districts(db: Session, city_id: str) -> list[District]:
    city = db.scalar(
        select(City)
        .join(World, World.id == City.world_id)
        .where(City.id == city_id, City.status == "active", World.status == "active")
    )
    if city is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "city.not_found", "message": "Active city not found"},
        )
    return list(
        db.scalars(
            select(District)
            .where(District.city_id == city.id, District.world_id == city.world_id)
            .order_by(District.name)
        )
    )


def join_world(
    db: Session,
    user: User,
    *,
    world_id: str,
    codename: str,
    archetype: str,
    home_district_id: str,
    idempotency_key: str,
    settings: Settings,
) -> PlayerProfile:
    locked_user = db.scalar(select(User).where(User.id == user.id).with_for_update())
    if locked_user is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "auth.required", "message": "Authentication required"},
        )
    user = locked_user
    existing_command = get_idempotent(db, user.id, idempotency_key, "world.join")
    if existing_command:
        profile = db.get(PlayerProfile, existing_command.resource_id)
        if profile:
            return profile

    world = db.get(World, world_id)
    district = db.get(District, home_district_id)
    if (
        world is None
        or world.status != "active"
        or district is None
        or district.world_id != world.id
        or district.city_id is None
    ):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "world.not_found",
                "message": "Active world, city or district not found",
            },
        )

    existing_profile = db.scalar(
        select(PlayerProfile).where(
            PlayerProfile.user_id == user.id,
            PlayerProfile.world_id == world.id,
        )
    )
    if existing_profile is not None and existing_profile.home_district_id != district.id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "player.city_already_selected",
                "message": "The starting city can only be selected once",
            },
        )

    profile = existing_profile or create_player_profile(
        db,
        user,
        world,
        codename,
        archetype,
        district,
        idempotency_key,
        settings,
    )
    remember_idempotent(
        db,
        user.id,
        idempotency_key,
        "world.join",
        profile.id,
        {"profile_id": profile.id},
    )
    db.commit()
    db.refresh(profile)
    return profile


def select_city(
    db: Session,
    user: User,
    *,
    city_id: str,
    codename: str,
    archetype: str,
    home_district_id: str,
    idempotency_key: str,
    settings: Settings,
) -> PlayerProfile:
    city = db.get(City, city_id)
    district = db.get(District, home_district_id)
    if (
        city is None
        or city.status != "active"
        or district is None
        or district.city_id != city.id
        or district.world_id != city.world_id
    ):
        raise HTTPException(
            status_code=404,
            detail={"code": "city.not_found", "message": "Active city or district not found"},
        )
    return join_world(
        db,
        user,
        world_id=city.world_id,
        codename=codename,
        archetype=archetype,
        home_district_id=home_district_id,
        idempotency_key=idempotency_key,
        settings=settings,
    )
