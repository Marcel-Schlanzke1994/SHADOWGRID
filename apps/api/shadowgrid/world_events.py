from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.domain import audit
from shadowgrid.game_config import WORLD_EVENT_TEMPLATES_V1
from shadowgrid.models import (
    City,
    Company,
    District,
    User,
    World,
    WorldEventDefinition,
    WorldEventInstance,
    as_utc,
)
from shadowgrid.realtime import emit_realtime_event

MULTIPLIER_KEYS: Final = (
    "revenue_multiplier_bps",
    "cost_multiplier_bps",
    "demand_multiplier_bps",
    "specialist_salary_multiplier_bps",
    "real_estate_cost_multiplier_bps",
)
DELTA_BOUNDS: Final[dict[str, tuple[int, int]]] = {
    "reputation_delta_bps": (-5_000, 5_000),
    "investigation_pressure_delta": (-100, 100),
    "stock_risk_delta_bps": (-5_000, 5_000),
    "contract_probability_delta_bps": (-5_000, 5_000),
}
ALL_EFFECT_KEYS: Final = frozenset((*MULTIPLIER_KEYS, *DELTA_BOUNDS))
SCOPE_TYPES: Final = {"world", "city", "district", "industry", "company"}
INDUSTRIES: Final = {"gastronomy", "logistics", "technology"}
_LOCK = threading.RLock()


@dataclass(frozen=True)
class EventModifiers:
    revenue_multiplier_bps: int = 10_000
    cost_multiplier_bps: int = 10_000
    demand_multiplier_bps: int = 10_000
    specialist_salary_multiplier_bps: int = 10_000
    real_estate_cost_multiplier_bps: int = 10_000
    reputation_delta_bps: int = 0
    investigation_pressure_delta: int = 0
    stock_risk_delta_bps: int = 0
    contract_probability_delta_bps: int = 0
    event_instance_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class EventPreview:
    definition_id: str
    event_key: str
    template_version: int
    title: str
    description: str
    scope_type: str
    scope_id: str
    starts_at: datetime
    ends_at: datetime
    effect_config: dict[str, int]
    affected_companies: int


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def normalize_effects(
    effects: dict[str, int],
    overrides: dict[str, int] | None = None,
) -> dict[str, int]:
    values = {key: 10_000 for key in MULTIPLIER_KEYS}
    values.update({key: 0 for key in DELTA_BOUNDS})
    provided = {**effects, **(overrides or {})}
    unknown = set(provided) - ALL_EFFECT_KEYS
    if unknown:
        raise _error(
            422,
            "world_event.effect_unknown",
            f"Unsupported event effect: {sorted(unknown)[0]}",
        )
    for key, value in provided.items():
        if isinstance(value, bool) or not isinstance(value, int):
            raise _error(422, "world_event.effect_invalid", "Event effects must be integers")
        if key in MULTIPLIER_KEYS:
            if not 2_500 <= value <= 30_000:
                raise _error(
                    422,
                    "world_event.effect_out_of_bounds",
                    "Event multiplier must be between 2500 and 30000 basis points",
                )
        else:
            lower, upper = DELTA_BOUNDS[key]
            if not lower <= value <= upper:
                raise _error(
                    422,
                    "world_event.effect_out_of_bounds",
                    f"{key} is outside its hard bounds",
                )
        values[key] = value
    return values


def seed_event_definitions(db: Session) -> list[WorldEventDefinition]:
    definitions: list[WorldEventDefinition] = []
    for event_key, template in WORLD_EVENT_TEMPLATES_V1.items():
        definition = db.scalar(
            select(WorldEventDefinition).where(
                WorldEventDefinition.event_key == event_key,
                WorldEventDefinition.version == 1,
            )
        )
        if definition is None:
            definition = WorldEventDefinition(
                event_key=event_key,
                version=1,
                title=template["title"],
                description=template["description"],
                default_scope_type=template["default_scope_type"],
                default_duration_minutes=template["default_duration_minutes"],
                effect_config_json=normalize_effects(template["effects"]),
                enabled=True,
            )
            db.add(definition)
            db.flush()
        definitions.append(definition)
    return definitions


def _definition(db: Session, event_key: str, version: int | None) -> WorldEventDefinition:
    query = select(WorldEventDefinition).where(WorldEventDefinition.event_key == event_key)
    if version is not None:
        query = query.where(WorldEventDefinition.version == version)
    definition = db.scalar(query.order_by(WorldEventDefinition.version.desc()).limit(1))
    if definition is None:
        raise _error(404, "world_event.definition_not_found", "Event definition not found")
    if not definition.enabled:
        raise _error(409, "world_event.definition_disabled", "Event definition is disabled")
    return definition


def _validate_scope(
    db: Session,
    world: World,
    scope_type: str,
    scope_id: str | None,
) -> tuple[str, int]:
    if scope_type not in SCOPE_TYPES:
        raise _error(422, "world_event.scope_invalid", "Unsupported event scope")
    if scope_type == "world":
        normalized_id = world.id
        affected = int(
            db.scalar(select(func.count()).select_from(Company).where(Company.world_id == world.id))
            or 0
        )
        return normalized_id, affected
    normalized_id = (scope_id or "").strip()
    if not normalized_id:
        raise _error(422, "world_event.scope_id_required", "Scope ID is required")
    if scope_type == "city":
        city = db.get(City, normalized_id)
        if city is None or city.world_id != world.id:
            raise _error(404, "world_event.scope_not_found", "City scope not found")
        affected = int(
            db.scalar(
                select(func.count())
                .select_from(Company)
                .join(District, District.id == Company.district_id)
                .where(Company.world_id == world.id, District.city_id == city.id)
            )
            or 0
        )
    elif scope_type == "district":
        district = db.get(District, normalized_id)
        if district is None or district.world_id != world.id:
            raise _error(404, "world_event.scope_not_found", "District scope not found")
        affected = int(
            db.scalar(
                select(func.count())
                .select_from(Company)
                .where(
                    Company.world_id == world.id,
                    Company.district_id == district.id,
                )
            )
            or 0
        )
    elif scope_type == "industry":
        if normalized_id not in INDUSTRIES:
            raise _error(404, "world_event.scope_not_found", "Industry scope not found")
        affected = int(
            db.scalar(
                select(func.count())
                .select_from(Company)
                .where(
                    Company.world_id == world.id,
                    Company.industry == normalized_id,
                )
            )
            or 0
        )
    else:
        company = db.get(Company, normalized_id)
        if company is None or company.world_id != world.id:
            raise _error(404, "world_event.scope_not_found", "Company scope not found")
        affected = 1
    return normalized_id, affected


def preview_event(
    db: Session,
    *,
    world_id: str,
    event_key: str,
    version: int | None,
    scope_type: str | None,
    scope_id: str | None,
    starts_at: datetime,
    duration_minutes: int | None,
    effect_overrides: dict[str, int] | None,
) -> EventPreview:
    world = db.get(World, world_id)
    if world is None:
        raise _error(404, "world.not_found", "World not found")
    definition = _definition(db, event_key, version)
    chosen_scope = scope_type or definition.default_scope_type
    normalized_scope_id, affected = _validate_scope(db, world, chosen_scope, scope_id)
    duration = duration_minutes or definition.default_duration_minutes
    if not 1 <= duration <= 43_200:
        raise _error(
            422,
            "world_event.duration_invalid",
            "Event duration must be between 1 and 43200 minutes",
        )
    normalized_start = as_utc(starts_at)
    effects = normalize_effects(
        {key: int(value) for key, value in definition.effect_config_json.items()},
        effect_overrides,
    )
    return EventPreview(
        definition_id=definition.id,
        event_key=definition.event_key,
        template_version=definition.version,
        title=definition.title,
        description=definition.description,
        scope_type=chosen_scope,
        scope_id=normalized_scope_id,
        starts_at=normalized_start,
        ends_at=normalized_start + timedelta(minutes=duration),
        effect_config=effects,
        affected_companies=affected,
    )


def _emit_event(
    db: Session,
    world_id: str,
    event_type: str,
    instance: WorldEventInstance,
    now: datetime,
) -> None:
    emit_realtime_event(
        db,
        world_id=world_id,
        event_type=event_type,
        payload={
            "event_id": instance.id,
            "event_key": instance.event_key,
            "title": instance.title,
            "scope_type": instance.scope_type,
            "scope_id": instance.scope_id,
            "status": instance.status,
        },
        dedupe_key=f"{event_type}:{instance.id}",
        at=now,
        ttl=timedelta(days=7),
    )


def activate_event(
    db: Session,
    *,
    admin: User,
    world_id: str,
    event_key: str,
    version: int | None,
    scope_type: str | None,
    scope_id: str | None,
    starts_at: datetime,
    duration_minutes: int | None,
    effect_overrides: dict[str, int] | None,
    idempotency_key: str,
    request_id: str,
) -> WorldEventInstance:
    with _LOCK:
        existing = db.scalar(
            select(WorldEventInstance).where(
                WorldEventInstance.world_id == world_id,
                WorldEventInstance.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        world = db.scalar(select(World).where(World.id == world_id).with_for_update())
        if world is None:
            raise _error(404, "world.not_found", "World not found")
        preview = preview_event(
            db,
            world_id=world_id,
            event_key=event_key,
            version=version,
            scope_type=scope_type,
            scope_id=scope_id,
            starts_at=starts_at,
            duration_minutes=duration_minutes,
            effect_overrides=effect_overrides,
        )
        now = datetime.now(UTC)
        is_active = preview.starts_at <= now < preview.ends_at
        instance = WorldEventInstance(
            world_id=world_id,
            definition_id=preview.definition_id,
            event_key=preview.event_key,
            template_version=preview.template_version,
            title=preview.title,
            description=preview.description,
            status="active" if is_active else "scheduled",
            scope_type=preview.scope_type,
            scope_id=preview.scope_id,
            effect_config_json=preview.effect_config,
            idempotency_key=idempotency_key,
            activated_by_user_id=admin.id,
            starts_at=preview.starts_at,
            ends_at=preview.ends_at,
            activated_at=now if is_active else None,
            created_at=now,
        )
        db.add(instance)
        db.flush()
        if is_active:
            _emit_event(db, world_id, "world.event.started", instance, now)
        audit(
            db,
            admin.id,
            "world_event.activated",
            "world_event_instance",
            instance.id,
            request_id,
            {
                "event_key": instance.event_key,
                "version": instance.template_version,
                "scope_type": instance.scope_type,
                "scope_id": instance.scope_id,
                "status": instance.status,
                "affected_companies": preview.affected_companies,
            },
        )
        return instance


def end_event(
    db: Session,
    *,
    admin: User,
    instance_id: str,
    reason: str,
    request_id: str,
) -> WorldEventInstance:
    with _LOCK:
        instance = db.scalar(
            select(WorldEventInstance).where(WorldEventInstance.id == instance_id).with_for_update()
        )
        if instance is None:
            raise _error(404, "world_event.instance_not_found", "Event instance not found")
        if instance.status in {"ended", "cancelled"}:
            return instance
        now = datetime.now(UTC)
        instance.status = "ended" if instance.status == "active" else "cancelled"
        instance.ended_at = now
        instance.end_reason = reason
        _emit_event(db, instance.world_id, "world.event.ended", instance, now)
        audit(
            db,
            admin.id,
            "world_event.ended",
            "world_event_instance",
            instance.id,
            request_id,
            {"status": instance.status, "reason": reason},
        )
        return instance


def advance_world_events(db: Session, at: datetime | None = None) -> dict[str, int]:
    with _LOCK:
        now = as_utc(at or datetime.now(UTC))
        started = 0
        ended = 0
        scheduled = list(
            db.scalars(
                select(WorldEventInstance)
                .where(
                    WorldEventInstance.status == "scheduled",
                    WorldEventInstance.starts_at <= now,
                )
                .order_by(WorldEventInstance.starts_at, WorldEventInstance.id)
                .with_for_update(skip_locked=True)
            )
        )
        for instance in scheduled:
            if as_utc(instance.ends_at) <= now:
                instance.status = "ended"
                instance.ended_at = now
                instance.end_reason = "expired_before_activation"
                ended += 1
                continue
            instance.status = "active"
            instance.activated_at = now
            _emit_event(db, instance.world_id, "world.event.started", instance, now)
            started += 1
        active = list(
            db.scalars(
                select(WorldEventInstance)
                .where(
                    WorldEventInstance.status == "active",
                    WorldEventInstance.ends_at <= now,
                )
                .order_by(WorldEventInstance.ends_at, WorldEventInstance.id)
                .with_for_update(skip_locked=True)
            )
        )
        for instance in active:
            instance.status = "ended"
            instance.ended_at = now
            instance.end_reason = "scheduled_expiry"
            _emit_event(db, instance.world_id, "world.event.ended", instance, now)
            ended += 1
        db.commit()
        return {"started": started, "ended": ended}


def _active_instances(
    db: Session,
    world_id: str,
    now: datetime,
) -> list[WorldEventInstance]:
    return list(
        db.scalars(
            select(WorldEventInstance)
            .where(
                WorldEventInstance.world_id == world_id,
                WorldEventInstance.status == "active",
                WorldEventInstance.starts_at <= now,
                WorldEventInstance.ends_at > now,
                WorldEventInstance.ended_at.is_(None),
            )
            .order_by(WorldEventInstance.starts_at, WorldEventInstance.id)
        )
    )


def _scope_matches_company(
    instance: WorldEventInstance,
    company: Company,
    district: District,
) -> bool:
    return (
        instance.scope_type == "world"
        or (instance.scope_type == "city" and instance.scope_id == district.city_id)
        or (instance.scope_type == "district" and instance.scope_id == district.id)
        or (instance.scope_type == "industry" and instance.scope_id == company.industry)
        or (instance.scope_type == "company" and instance.scope_id == company.id)
    )


def _compose(instances: list[WorldEventInstance]) -> EventModifiers:
    multipliers = {key: 10_000 for key in MULTIPLIER_KEYS}
    deltas = {key: 0 for key in DELTA_BOUNDS}
    for instance in instances:
        effects = instance.effect_config_json
        for key in MULTIPLIER_KEYS:
            value = int(effects.get(key, 10_000))
            multipliers[key] = max(
                2_500,
                min(30_000, multipliers[key] * value // 10_000),
            )
        for key, (lower, upper) in DELTA_BOUNDS.items():
            deltas[key] = max(
                lower,
                min(upper, deltas[key] + int(effects.get(key, 0))),
            )
    return EventModifiers(
        **multipliers,
        **deltas,
        event_instance_ids=tuple(instance.id for instance in instances),
    )


def company_event_modifiers(
    db: Session,
    company: Company,
    district: District,
    at: datetime,
) -> EventModifiers:
    now = as_utc(at)
    instances = [
        instance
        for instance in _active_instances(db, company.world_id, now)
        if _scope_matches_company(instance, company, district)
    ]
    return _compose(instances)


def market_event_modifiers(
    db: Session,
    *,
    world_id: str,
    city_id: str,
    industry: str,
    at: datetime,
) -> EventModifiers:
    now = as_utc(at)
    instances = [
        instance
        for instance in _active_instances(db, world_id, now)
        if instance.scope_type == "world"
        or (instance.scope_type == "city" and instance.scope_id == city_id)
        or (instance.scope_type == "industry" and instance.scope_id == industry)
    ]
    return _compose(instances)


def event_feed(
    db: Session,
    world_id: str,
    *,
    limit: int = 100,
) -> list[WorldEventInstance]:
    return list(
        db.scalars(
            select(WorldEventInstance)
            .where(WorldEventInstance.world_id == world_id)
            .order_by(WorldEventInstance.starts_at.desc(), WorldEventInstance.id)
            .limit(limit)
        )
    )
