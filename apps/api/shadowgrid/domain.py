from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.game_config import (
    ARCHETYPES,
    BUSINESS_TYPES,
    FACILITY_TYPES,
    OPERATION_TYPES,
    RESEARCH,
    RISK_POSTURES,
    ROLE_PERMISSIONS,
    SPECIALIST_ROLES,
    START_RESOURCES,
)
from shadowgrid.models import (
    AuditLog,
    Business,
    District,
    DistrictInfluence,
    Evidence,
    Facility,
    IdempotencyRecord,
    IntelReport,
    LedgerEntry,
    Notification,
    Operation,
    OrganizationMembership,
    PlayerProfile,
    ResearchProject,
    ResourceBalance,
    Specialist,
    User,
    World,
    as_utc,
    utcnow,
)

RESOURCE_FIELDS = {
    "cash",
    "capital",
    "influence",
    "intelligence",
    "logistics_capacity",
    "personnel_capacity",
}


def as_decimal(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def get_idempotent(db: Session, user_id: str, key: str, scope: str) -> IdempotencyRecord | None:
    return db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user_id,
            IdempotencyRecord.key == key,
            IdempotencyRecord.scope == scope,
        )
    )


def remember_idempotent(
    db: Session, user_id: str, key: str, scope: str, resource_id: str, response: dict[str, Any]
) -> None:
    db.add(
        IdempotencyRecord(
            user_id=user_id,
            key=key,
            scope=scope,
            resource_id=resource_id,
            response_json=response,
        )
    )


def audit(
    db: Session,
    actor_user_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    request_id: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditLog(
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            request_id=request_id,
            metadata_json=metadata or {},
        )
    )


def apply_profile_resource(
    db: Session,
    profile_id: str,
    resource_type: str,
    amount: Decimal | int | float | str,
    *,
    reason: str,
    reference_type: str,
    reference_id: str,
    idempotency_key: str,
    metadata: dict[str, Any] | None = None,
) -> LedgerEntry:
    if resource_type not in RESOURCE_FIELDS:
        raise ValueError(f"unsupported resource: {resource_type}")
    existing = db.scalar(
        select(LedgerEntry).where(
            LedgerEntry.owner_type == "profile",
            LedgerEntry.owner_id == profile_id,
            LedgerEntry.idempotency_key == idempotency_key,
            LedgerEntry.resource_type == resource_type,
        )
    )
    if existing:
        return existing
    balance = db.scalar(
        select(ResourceBalance).where(ResourceBalance.profile_id == profile_id).with_for_update()
    )
    if balance is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "resource.missing", "message": "Resource balance does not exist"},
        )
    delta = as_decimal(amount)
    current = as_decimal(getattr(balance, resource_type))
    new_balance = current + delta
    if new_balance < 0:
        raise HTTPException(
            status_code=409,
            detail={"code": "resource.insufficient", "message": f"Insufficient {resource_type}"},
        )
    setattr(balance, resource_type, new_balance)
    balance.version += 1
    entry = LedgerEntry(
        owner_type="profile",
        owner_id=profile_id,
        resource_type=resource_type,
        amount=delta,
        balance_after=new_balance,
        reason=reason,
        reference_type=reference_type,
        reference_id=reference_id,
        idempotency_key=idempotency_key,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.flush()
    return entry


def create_player_profile(
    db: Session,
    user: User,
    world: World,
    codename: str,
    archetype: str,
    home_district: District,
    idempotency_key: str,
) -> PlayerProfile:
    if archetype not in ARCHETYPES:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "profile.invalid_archetype",
                "message": "Unknown organization archetype",
            },
        )
    existing = db.scalar(
        select(PlayerProfile).where(
            PlayerProfile.user_id == user.id, PlayerProfile.world_id == world.id
        )
    )
    if existing:
        return existing
    if home_district.world_id != world.id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "district.invalid",
                "message": "District does not belong to this world",
            },
        )
    archetype_modifiers = ARCHETYPES[archetype]
    profile = PlayerProfile(
        user_id=user.id,
        world_id=world.id,
        codename=codename,
        archetype=archetype,
        home_district_id=home_district.id,
        loyalty=65 + int(archetype_modifiers.get("loyalty", 0)),
        legitimacy=60 + int(archetype_modifiers.get("legitimacy", 0)),
        protected_until=datetime.now(UTC) + timedelta(hours=72),
    )
    db.add(profile)
    db.flush()
    db.add(ResourceBalance(profile_id=profile.id))
    db.flush()
    for resource, value in START_RESOURCES.items():
        apply_profile_resource(
            db,
            profile.id,
            resource,
            value,
            reason="initial_grant",
            reference_type="profile",
            reference_id=profile.id,
            idempotency_key=f"{idempotency_key}:initial",
        )
    db.add(Facility(profile_id=profile.id, facility_type="headquarters", level=1))
    starter = Business(
        profile_id=profile.id,
        district_id=home_district.id,
        business_type="gastronomy",
        name=f"{codename} Civic Café",
        revenue=as_decimal(BUSINESS_TYPES["gastronomy"]["revenue"]),
        operating_cost=as_decimal(BUSINESS_TYPES["gastronomy"]["cost"]),
        personnel_need=2,
        logistics_need=1,
        risk=8,
    )
    db.add(starter)
    for index, role in enumerate(
        ("finance_director", "strategist", "district_coordinator", "intelligence_analyst")
    ):
        db.add(
            Specialist(
                profile_id=profile.id,
                name=("Mara Voss", "Elias Kern", "Nia Calder", "Jun Arendt")[index],
                role=role,
                competence=55 + index * 3,
                loyalty=65 + index * 2,
                ambition=35 + index * 4,
                stress=5,
                exposure=8,
                salary=as_decimal(1_200 + index * 200),
            )
        )
    db.add(
        DistrictInfluence(
            district_id=home_district.id,
            profile_id=profile.id,
            kind="economic",
            points=Decimal("8"),
        )
    )
    db.flush()
    return profile


def buy_business(
    db: Session,
    profile: PlayerProfile,
    business_type: str,
    district: District,
    name: str,
    idempotency_key: str,
) -> Business:
    config = BUSINESS_TYPES.get(business_type)
    if config is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "business.invalid_type", "message": "Unknown business type"},
        )
    if district.world_id != profile.world_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "district.invalid",
                "message": "District does not belong to this world",
            },
        )
    business = Business(
        profile_id=profile.id,
        district_id=district.id,
        business_type=business_type,
        name=name,
        revenue=as_decimal(config["revenue"]),
        operating_cost=as_decimal(config["cost"]),
        personnel_need=int(config["personnel"]),
        logistics_need=int(config["logistics"]),
        risk=int(config["risk"]),
    )
    db.add(business)
    db.flush()
    apply_profile_resource(
        db,
        profile.id,
        "capital",
        -as_decimal(config["price"]),
        reason="business_purchase",
        reference_type="business",
        reference_id=business.id,
        idempotency_key=idempotency_key,
    )
    influence = db.scalar(
        select(DistrictInfluence)
        .where(
            DistrictInfluence.district_id == district.id,
            DistrictInfluence.profile_id == profile.id,
            DistrictInfluence.kind == "economic",
        )
        .with_for_update()
    )
    if influence is None:
        influence = DistrictInfluence(
            district_id=district.id, profile_id=profile.id, kind="economic", points=Decimal("0")
        )
        db.add(influence)
    influence.points = as_decimal(influence.points) + Decimal("2")
    return business


def build_facility(
    db: Session, profile: PlayerProfile, facility_type: str, idempotency_key: str
) -> Facility:
    config = FACILITY_TYPES.get(facility_type)
    if config is None or facility_type == "headquarters":
        raise HTTPException(
            status_code=422,
            detail={"code": "facility.invalid_type", "message": "Unknown buildable facility"},
        )
    facility = db.scalar(
        select(Facility)
        .where(Facility.profile_id == profile.id, Facility.facility_type == facility_type)
        .with_for_update()
    )
    if facility and facility.status == "building":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "facility.already_building",
                "message": "Facility construction is already running",
            },
        )
    next_level = 1 if facility is None else facility.level + 1
    if next_level > int(config["max_level"]):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "facility.max_level",
                "message": "Facility is already at maximum level",
            },
        )
    multiplier = Decimal("1.85") ** (next_level - 1)
    reference_id = facility.id if facility else "pending"
    apply_profile_resource(
        db,
        profile.id,
        "cash",
        -as_decimal(config["cash"]) * multiplier,
        reason="facility_build",
        reference_type="facility",
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    apply_profile_resource(
        db,
        profile.id,
        "capital",
        -as_decimal(config["capital"]) * multiplier,
        reason="facility_build",
        reference_type="facility",
        reference_id=reference_id,
        idempotency_key=idempotency_key,
    )
    duration = timedelta(hours=float(config["hours"]) * (1.7 ** (next_level - 1)))
    if facility is None:
        facility = Facility(profile_id=profile.id, facility_type=facility_type)
        db.add(facility)
        db.flush()
    facility.level = next_level
    facility.status = "building"
    facility.finishes_at = datetime.now(UTC) + duration
    return facility


def recruit_specialist(
    db: Session, profile: PlayerProfile, role: str, idempotency_key: str
) -> Specialist:
    if role not in SPECIALIST_ROLES:
        raise HTTPException(
            status_code=422,
            detail={"code": "specialist.invalid_role", "message": "Unknown specialist role"},
        )
    count = (
        db.scalar(
            select(func.count()).select_from(Specialist).where(Specialist.profile_id == profile.id)
        )
        or 0
    )
    if count >= int(profile.resources.personnel_capacity):
        raise HTTPException(
            status_code=409,
            detail={"code": "specialist.capacity", "message": "Personnel capacity reached"},
        )
    digest = hashlib.sha256(f"{profile.id}:{role}:{count}".encode()).digest()
    names = (
        "Avery Sol",
        "Leonie Rook",
        "Samir Vale",
        "Mika Rowan",
        "Noa Kestrel",
        "Tarin Cross",
        "Ira North",
        "Remy Lark",
    )
    specialist = Specialist(
        profile_id=profile.id,
        name=names[digest[0] % len(names)],
        role=role,
        competence=45 + digest[1] % 31,
        loyalty=50 + digest[2] % 31,
        ambition=25 + digest[3] % 51,
        stress=0,
        exposure=5 + digest[4] % 16,
        salary=as_decimal(900 + digest[5] * 5),
    )
    db.add(specialist)
    db.flush()
    apply_profile_resource(
        db,
        profile.id,
        "cash",
        -5_000,
        reason="specialist_recruitment",
        reference_type="specialist",
        reference_id=specialist.id,
        idempotency_key=idempotency_key,
    )
    return specialist


def start_operation(
    db: Session,
    profile: PlayerProfile,
    specialist: Specialist,
    district: District,
    payload: Any,
    idempotency_key: str,
    settings: Settings,
) -> Operation:
    operation_config = OPERATION_TYPES.get(payload.operation_type)
    posture = RISK_POSTURES.get(payload.risk_posture)
    if operation_config is None or posture is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "operation.invalid_configuration",
                "message": "Unknown operation type or risk posture",
            },
        )
    if specialist.profile_id != profile.id or specialist.status != "available":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "operation.specialist_unavailable",
                "message": "Specialist is not available",
            },
        )
    if district.world_id != profile.world_id:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "district.invalid",
                "message": "District does not belong to this world",
            },
        )
    running = (
        db.scalar(
            select(func.count())
            .select_from(Operation)
            .where(Operation.profile_id == profile.id, Operation.status == "running")
        )
        or 0
    )
    if running >= profile.operation_slots:
        raise HTTPException(
            status_code=409,
            detail={"code": "operation.slots_full", "message": "All operation slots are occupied"},
        )
    duration_seconds = settings.test_operation_seconds or int(
        float(operation_config["minutes"]) * 60 * float(posture["duration"])
    )
    operation = Operation(
        profile_id=profile.id,
        operation_type=payload.operation_type,
        district_id=district.id,
        specialist_id=specialist.id,
        target=payload.target,
        budget=payload.budget,
        intelligence_spend=payload.intelligence_spend,
        risk_posture=payload.risk_posture,
        secrecy=payload.secrecy,
        finishes_at=datetime.now(UTC) + timedelta(seconds=duration_seconds),
    )
    db.add(operation)
    db.flush()
    apply_profile_resource(
        db,
        profile.id,
        "cash",
        -payload.budget,
        reason="operation_budget",
        reference_type="operation",
        reference_id=operation.id,
        idempotency_key=idempotency_key,
    )
    if payload.intelligence_spend:
        apply_profile_resource(
            db,
            profile.id,
            "intelligence",
            -payload.intelligence_spend,
            reason="operation_intelligence",
            reference_type="operation",
            reference_id=operation.id,
            idempotency_key=idempotency_key,
        )
    specialist.status = "assigned"
    specialist.assigned_operation_id = operation.id
    return operation


def _operation_roll(operation_id: str, settings: Settings) -> int:
    digest = hmac.new(
        settings.seed_secret.get_secret_value().encode(), operation_id.encode(), hashlib.sha256
    ).digest()
    return int.from_bytes(digest[:4], "big") % 100 + 1


def resolve_operation(
    db: Session, operation: Operation, settings: Settings, *, force: bool = False
) -> Operation:
    if operation.status != "running":
        return operation
    now = datetime.now(UTC)
    if not force and as_utc(operation.finishes_at) > now:
        return operation
    profile = db.get(PlayerProfile, operation.profile_id)
    specialist = db.get(Specialist, operation.specialist_id)
    district = db.get(District, operation.district_id)
    if profile is None or specialist is None or district is None:
        raise RuntimeError("operation dependencies are missing")
    config = OPERATION_TYPES[operation.operation_type]
    posture = RISK_POSTURES[operation.risk_posture]
    chance = (
        52
        + specialist.competence * 0.45
        + float(operation.intelligence_spend) * 1.4
        + operation.secrecy * 0.05
    )
    chance += (
        float(posture["chance"])
        - float(config["difficulty"])
        - specialist.stress * 0.15
        - district.authority_presence * 0.08
    )
    chance = max(12, min(88, chance))
    roll = _operation_roll(operation.id, settings)
    if roll <= max(5, chance - 35):
        result, multiplier = "critical_success", Decimal("1.5")
    elif roll <= chance:
        result, multiplier = "success", Decimal("1.0")
    elif roll <= min(94, chance + 18):
        result, multiplier = "partial_success", Decimal("0.5")
    elif roll <= 96:
        result, multiplier = "failure", Decimal("0")
    else:
        result, multiplier = "critical_failure", Decimal("-0.35")
    reward_scale = multiplier * as_decimal(posture["reward"])
    outcome: dict[str, Any] = {"roll_band": result, "effects": {}}
    for resource in ("cash", "influence", "intelligence"):
        base = as_decimal(config.get(resource, 0))
        if resource == "cash" and base == 0:
            base = as_decimal(operation.budget) * Decimal("0.35")
        delta = (base * reward_scale).quantize(Decimal("0.01"))
        if delta:
            apply_profile_resource(
                db,
                profile.id,
                resource,
                delta,
                reason="operation_result",
                reference_type="operation",
                reference_id=operation.id,
                idempotency_key=f"resolve:{operation.id}",
            )
            outcome["effects"][resource] = float(delta)
    pressure_delta = max(
        0,
        round(
            float(config["pressure"]) * float(posture["risk"]) + max(0, 55 - operation.secrecy) / 15
        ),
    )
    if result in {"failure", "critical_failure"}:
        pressure_delta += 4 if result == "failure" else 10
        db.add(
            Evidence(
                profile_id=profile.id,
                evidence_type="operation_trace",
                strength=15 if result == "failure" else 28,
                source_reference=operation.id,
            )
        )
    profile.investigation_pressure = min(100, profile.investigation_pressure + pressure_delta)
    specialist.stress = min(
        100, specialist.stress + (8 if operation.risk_posture == "aggressive" else 4)
    )
    specialist.exposure = min(100, specialist.exposure + pressure_delta // 2)
    specialist.status = "available"
    specialist.assigned_operation_id = None
    points = as_decimal(config.get("influence", 1)) * max(Decimal("0"), multiplier)
    influence = db.scalar(
        select(DistrictInfluence)
        .where(
            DistrictInfluence.district_id == district.id,
            DistrictInfluence.profile_id == profile.id,
            DistrictInfluence.kind == "economic",
        )
        .with_for_update()
    )
    if influence is None:
        influence = DistrictInfluence(
            district_id=district.id, profile_id=profile.id, kind="economic", points=Decimal("0")
        )
        db.add(influence)
    influence.points = as_decimal(influence.points) + points
    if operation.operation_type == "intelligence_gathering" and result not in {
        "failure",
        "critical_failure",
    }:
        db.add(
            IntelReport(
                profile_id=profile.id,
                title="District activity assessment",
                summary="A fictional source observed changing commercial relationships. Treat this estimate as uncertain.",
                target_type="district",
                target_id=district.id,
                visible_confidence=min(90, 50 + specialist.competence // 3),
                actual_accuracy=65 + specialist.competence // 5,
                source="abstract field source",
                observed_at=now,
                expires_at=now + timedelta(days=3),
            )
        )
    operation.status = "completed"
    operation.result = result
    operation.outcome_json = outcome
    operation.resolved_at = now
    return operation


def start_research(
    db: Session, profile: PlayerProfile, research_key: str, idempotency_key: str, settings: Settings
) -> ResearchProject:
    config = RESEARCH.get(research_key)
    if config is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "research.invalid", "message": "Unknown research project"},
        )
    running = db.scalar(
        select(ResearchProject).where(
            ResearchProject.profile_id == profile.id, ResearchProject.status == "running"
        )
    )
    if running:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "research.slot_full",
                "message": "A personal research project is already running",
            },
        )
    duration_seconds = settings.test_operation_seconds or int(config["minutes"]) * 60
    project = ResearchProject(
        profile_id=profile.id,
        research_key=research_key,
        category=str(config["category"]),
        finishes_at=datetime.now(UTC) + timedelta(seconds=duration_seconds),
    )
    db.add(project)
    db.flush()
    apply_profile_resource(
        db,
        profile.id,
        "cash",
        -as_decimal(config["cash"]),
        reason="research_start",
        reference_type="research",
        reference_id=project.id,
        idempotency_key=idempotency_key,
    )
    apply_profile_resource(
        db,
        profile.id,
        "capital",
        -as_decimal(config["capital"]),
        reason="research_start",
        reference_type="research",
        reference_id=project.id,
        idempotency_key=idempotency_key,
    )
    return project


def membership_with_permission(
    db: Session, profile_id: str, permission: str, organization_id: str | None = None
) -> OrganizationMembership:
    query = select(OrganizationMembership).where(
        OrganizationMembership.profile_id == profile_id, OrganizationMembership.status == "active"
    )
    if organization_id:
        query = query.where(OrganizationMembership.organization_id == organization_id)
    membership = db.scalar(query)
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "organization.membership_required",
                "message": "Active organization membership required",
            },
        )
    permissions = ROLE_PERMISSIONS.get(membership.role, set())
    if "*" not in permissions and permission not in permissions:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "organization.permission_denied",
                "message": "Organization permission denied",
            },
        )
    return membership


def settle_businesses(db: Session, at: datetime | None = None) -> int:
    now = at or utcnow()
    settlement_key = now.strftime("business-hour:%Y%m%d%H")
    settled = 0
    for business in db.scalars(select(Business).where(Business.status == "operating")):
        net_hour = (as_decimal(business.revenue) - as_decimal(business.operating_cost)) / Decimal(
            "24"
        )
        apply_profile_resource(
            db,
            business.profile_id,
            "cash",
            net_hour,
            reason="business_settlement",
            reference_type="business",
            reference_id=business.id,
            idempotency_key=settlement_key,
        )
        settled += 1
    db.commit()
    return settled


def resolve_due(db: Session, settings: Settings) -> dict[str, int]:
    now = datetime.now(UTC)
    counts = {"operations": 0, "facilities": 0, "research": 0}
    for operation in db.scalars(
        select(Operation)
        .where(Operation.status == "running", Operation.finishes_at <= now)
        .with_for_update(skip_locked=True)
    ):
        resolve_operation(db, operation, settings)
        counts["operations"] += 1
    for facility in db.scalars(
        select(Facility)
        .where(Facility.status == "building", Facility.finishes_at <= now)
        .with_for_update(skip_locked=True)
    ):
        facility.status = "active"
        facility.finishes_at = None
        counts["facilities"] += 1
    for project in db.scalars(
        select(ResearchProject)
        .where(ResearchProject.status == "running", ResearchProject.finishes_at <= now)
        .with_for_update(skip_locked=True)
    ):
        project.status = "completed"
        project.resolved_at = now
        counts["research"] += 1
    db.commit()
    return counts


def create_notification(
    db: Session,
    user_id: str,
    event_type: str,
    title: str,
    body: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    db.add(
        Notification(
            user_id=user_id,
            event_type=event_type,
            title=title,
            body=body,
            metadata_json=metadata or {},
        )
    )


def safe_commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={
                "code": "request.conflict",
                "message": "The request conflicts with existing state",
            },
        ) from exc
