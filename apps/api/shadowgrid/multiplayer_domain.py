from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.domain import (
    apply_profile_resource,
    as_decimal,
    audit,
    create_notification,
    membership_with_permission,
)
from shadowgrid.game_config import (
    PVP_DEFENSE_ACTIONS,
    PVP_OPERATION_TYPES,
    RISK_POSTURES,
    WAR_SCORE_WEIGHTS,
)
from shadowgrid.intelligence import active_reputation_penalty
from shadowgrid.models import (
    AllianceMembership,
    Business,
    CartelWar,
    CartelWarEvent,
    CartelWarObjective,
    CartelWarOperation,
    CartelWarParticipant,
    CartelWarScore,
    CartelWarTreaty,
    District,
    DistrictInfluence,
    LedgerEntry,
    Organization,
    OrganizationMembership,
    PlayerProfile,
    PvpCooldown,
    PvpDefenseAction,
    PvpOperation,
    PvpOperationParticipant,
    PvpProtectionState,
    PvpReport,
    PvpReputation,
    ResourceBalance,
    TerritoryClaim,
    TerritoryContribution,
    TerritoryControlPoint,
    TerritoryHistory,
    Treaty,
    User,
    as_utc,
)
from shadowgrid.multiplayer_schemas import (
    PvpPreviewView,
    PvpProtectionView,
    PvpTargetView,
    TerritoryClaimView,
    TerritoryControlPointView,
    TerritoryView,
)
from shadowgrid.realtime import emit_realtime_event

PVP_OPEN_STATES = {"warning", "running"}
WAR_OPEN_STATES = {"ultimatum", "preparation", "active", "aftermath"}


def active_membership(db: Session, profile_id: str) -> OrganizationMembership | None:
    return db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.profile_id == profile_id,
            OrganizationMembership.status == "active",
        )
    )


def emit_realtime(
    db: Session,
    world_id: str,
    event_type: str,
    payload: dict[str, Any],
    profile_ids: list[str] | None = None,
) -> None:
    if profile_ids:
        for profile_id in dict.fromkeys(profile_ids):
            emit_realtime_event(
                db,
                world_id=world_id,
                event_type=event_type,
                payload=payload,
                audience_type="player",
                audience_id=profile_id,
                ttl=timedelta(hours=24),
            )
        return
    emit_realtime_event(
        db,
        world_id=world_id,
        event_type=event_type,
        payload=payload,
        ttl=timedelta(hours=24),
    )


def protection_for_profile(db: Session, profile: PlayerProfile) -> PvpProtectionView:
    now = datetime.now(UTC)
    reasons: list[str] = []
    protected_until: datetime | None = None
    offensive_lock = False
    if as_utc(profile.protected_until) > now:
        protected_until = as_utc(profile.protected_until)
        reasons.append("new_player")
    if profile.recovery_until is not None and as_utc(profile.recovery_until) > now:
        candidate = as_utc(profile.recovery_until)
        protected_until = max(protected_until or candidate, candidate)
        reasons.append("recovery")
        offensive_lock = True
    states = list(
        db.scalars(
            select(PvpProtectionState).where(
                PvpProtectionState.profile_id == profile.id,
                PvpProtectionState.ended_at.is_(None),
                PvpProtectionState.protected_until > now,
            )
        )
    )
    for state in states:
        candidate = as_utc(state.protected_until)
        protected_until = max(protected_until or candidate, candidate)
        reasons.append(state.protection_type)
        offensive_lock = offensive_lock or state.offensive_lock
    return PvpProtectionView(
        status="protected" if protected_until else "open",
        protected_until=protected_until,
        recovery_until=profile.recovery_until,
        offensive_lock=offensive_lock,
        reasons=sorted(set(reasons)),
    )


def get_or_create_reputation(db: Session, profile: PlayerProfile) -> PvpReputation:
    reputation = db.get(PvpReputation, profile.id)
    if reputation is None:
        reputation = PvpReputation(
            profile_id=profile.id,
            world_id=profile.world_id,
            stability=profile.stability,
        )
        db.add(reputation)
        db.flush()
    return reputation


def _cartel_for_profile(db: Session, profile_id: str) -> Organization | None:
    membership = active_membership(db, profile_id)
    return db.get(Organization, membership.organization_id) if membership else None


def _treaty_status(
    db: Session, attacker_cartel_id: str | None, defender_cartel_id: str | None
) -> str | None:
    if attacker_cartel_id is None or defender_cartel_id is None:
        return None
    shared_alliance = db.scalar(
        select(AllianceMembership.id).where(
            AllianceMembership.cartel_id == defender_cartel_id,
            AllianceMembership.status == "active",
            AllianceMembership.alliance_id.in_(
                select(AllianceMembership.alliance_id).where(
                    AllianceMembership.cartel_id == attacker_cartel_id,
                    AllianceMembership.status == "active",
                )
            ),
        )
    )
    if shared_alliance is not None:
        return "alliance"
    now = datetime.now(UTC)
    treaty = db.scalar(
        select(Treaty).where(
            Treaty.status == "active",
            Treaty.expires_at > now,
            or_(
                (Treaty.proposer_org_id == attacker_cartel_id)
                & (Treaty.recipient_org_id == defender_cartel_id),
                (Treaty.proposer_org_id == defender_cartel_id)
                & (Treaty.recipient_org_id == attacker_cartel_id),
            ),
        )
    )
    return treaty.treaty_type if treaty else None


def _strength_value(db: Session, profile: PlayerProfile) -> Decimal:
    balance = db.get(ResourceBalance, profile.id)
    if balance is None:
        return Decimal("0")
    business_count = (
        db.scalar(
            select(func.count()).select_from(Business).where(Business.profile_id == profile.id)
        )
        or 0
    )
    return (
        as_decimal(balance.cash) / Decimal("10000")
        + as_decimal(balance.capital) / Decimal("5000")
        + as_decimal(balance.influence) * Decimal("2")
        + Decimal(business_count * 4)
        + Decimal(profile.stability) / Decimal("5")
    )


def _strength_band(attacker_strength: Decimal, defender_strength: Decimal) -> str:
    if attacker_strength <= 0:
        return "very_risky"
    ratio = defender_strength / attacker_strength
    if ratio < Decimal("0.55"):
        return "easy"
    if ratio < Decimal("1.20"):
        return "balanced"
    if ratio < Decimal("1.70"):
        return "challenging"
    if ratio < Decimal("2.40"):
        return "very_risky"
    return "not_recommended"


def pvp_targets(db: Session, profile: PlayerProfile) -> list[PvpTargetView]:
    if profile.city_id is None:
        return []
    attacker_cartel = _cartel_for_profile(db, profile.id)
    attacker_strength = _strength_value(db, profile)
    result: list[PvpTargetView] = []
    targets = db.scalars(
        select(PlayerProfile)
        .where(
            PlayerProfile.world_id == profile.world_id,
            PlayerProfile.city_id == profile.city_id,
            PlayerProfile.id != profile.id,
        )
        .order_by(PlayerProfile.created_at.desc())
        .limit(100)
    )
    for target in targets:
        target_cartel = _cartel_for_profile(db, target.id)
        reputation = get_or_create_reputation(db, target)
        reputation_penalty = active_reputation_penalty(db, target.id, datetime.now(UTC))
        protection = protection_for_profile(db, target)
        business_count = (
            db.scalar(
                select(func.count()).select_from(Business).where(Business.profile_id == target.id)
            )
            or 0
        )
        district_ids = list(
            db.scalars(
                select(DistrictInfluence.district_id)
                .where(DistrictInfluence.profile_id == target.id, DistrictInfluence.points > 0)
                .limit(5)
            )
        )
        treaty = _treaty_status(
            db,
            attacker_cartel.id if attacker_cartel else None,
            target_cartel.id if target_cartel else None,
        )
        recommendation = _strength_band(attacker_strength, _strength_value(db, target))
        if protection.status == "protected":
            recommendation = "protected"
        result.append(
            PvpTargetView(
                profile_id=target.id,
                codename=target.codename,
                city_id=target.city_id or "",
                cartel_id=target_cartel.id if target_cartel else None,
                cartel_name=target_cartel.name if target_cartel else None,
                public_reputation={
                    "reliability": max(0, reputation.reliability - reputation_penalty),
                    "economic_strength": reputation.economic_strength,
                    "diplomacy": reputation.diplomacy,
                    "aggression": reputation.aggression,
                    "defense": reputation.defense,
                    "stability": max(0, reputation.stability - reputation_penalty),
                },
                estimated_strength=recommendation,
                known_businesses=int(business_count),
                known_district_presence=district_ids,
                last_public_activity=target.created_at,
                treaty_status=treaty,
                protection_status=protection.status,
                recommendation=recommendation,
            )
        )
    return result


def preview_pvp(
    db: Session,
    profile: PlayerProfile,
    defender_profile_id: str,
    operation_type: str,
    district_id: str | None,
    risk_posture: str,
) -> PvpPreviewView:
    if operation_type not in PVP_OPERATION_TYPES or risk_posture not in RISK_POSTURES:
        raise HTTPException(
            status_code=422,
            detail={"code": "pvp.invalid_configuration", "message": "Unsupported PvP setup"},
        )
    defender = db.get(PlayerProfile, defender_profile_id)
    if (
        defender is None
        or defender.id == profile.id
        or defender.world_id != profile.world_id
        or defender.city_id is None
        or defender.city_id != profile.city_id
    ):
        raise HTTPException(
            status_code=404,
            detail={"code": "pvp.target_not_found", "message": "Eligible target not found"},
        )
    if district_id is not None:
        district = db.get(District, district_id)
        if (
            district is None
            or district.world_id != profile.world_id
            or district.city_id != profile.city_id
        ):
            raise HTTPException(
                status_code=422,
                detail={"code": "pvp.invalid_district", "message": "District is outside the city"},
            )
    now = datetime.now(UTC)
    repeated = (
        db.scalar(
            select(func.count())
            .select_from(PvpOperation)
            .where(
                PvpOperation.attacker_profile_id == profile.id,
                PvpOperation.defender_profile_id == defender.id,
                PvpOperation.created_at > now - timedelta(hours=24),
            )
        )
        or 0
    )
    repetition_multiplier = Decimal("1") + Decimal(repeated) * Decimal("0.50")
    reward_multiplier = max(Decimal("0.25"), Decimal("1") - Decimal(repeated) * Decimal("0.25"))
    config = PVP_OPERATION_TYPES[operation_type]
    protection = protection_for_profile(db, defender)
    attacker_cartel = _cartel_for_profile(db, profile.id)
    defender_cartel = _cartel_for_profile(db, defender.id)
    treaty = _treaty_status(
        db,
        attacker_cartel.id if attacker_cartel else None,
        defender_cartel.id if defender_cartel else None,
    )
    cooldown = db.scalar(
        select(PvpCooldown).where(
            PvpCooldown.attacker_profile_id == profile.id,
            PvpCooldown.defender_profile_id == defender.id,
            PvpCooldown.expires_at > now,
        )
    )
    reasons: list[str] = []
    if protection.status == "protected":
        reasons.append("target_protected")
    if treaty in {"non_aggression", "alliance"}:
        reasons.append("alliance_partner" if treaty == "alliance" else "non_aggression_treaty")
    if cooldown:
        reasons.append("cooldown_active")
    if repeated >= 3:
        reasons.append("daily_target_limit")
    if protection_for_profile(db, profile).offensive_lock:
        reasons.append("recovery_offensive_lock")
    band = _strength_band(_strength_value(db, profile), _strength_value(db, defender))
    return PvpPreviewView(
        defender_profile_id=defender.id,
        operation_type=operation_type,
        estimated_cost_cash=as_decimal(config["cash"]) * repetition_multiplier,
        estimated_cost_influence=as_decimal(config["influence"]) * repetition_multiplier,
        estimated_minutes=int(config["minutes"]),
        estimated_success_band=band,
        repetition_multiplier=repetition_multiplier,
        reward_multiplier=reward_multiplier,
        protection_status=protection.status,
        treaty_status=treaty,
        can_launch=not reasons,
        reasons=reasons,
    )


def launch_pvp_operation(
    db: Session,
    user: User,
    profile: PlayerProfile,
    defender_profile_id: str,
    operation_type: str,
    district_id: str | None,
    risk_posture: str,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
) -> PvpOperation:
    existing = db.scalar(
        select(PvpOperation).where(
            PvpOperation.attacker_profile_id == profile.id,
            PvpOperation.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return existing
    preview = preview_pvp(
        db, profile, defender_profile_id, operation_type, district_id, risk_posture
    )
    if not preview.can_launch:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "pvp.launch_blocked",
                "message": "PvP operation is blocked by protection, treaty or cooldown rules",
                "reasons": preview.reasons,
            },
        )
    defender = db.scalar(
        select(PlayerProfile).where(PlayerProfile.id == defender_profile_id).with_for_update()
    )
    attacker = db.scalar(
        select(PlayerProfile).where(PlayerProfile.id == profile.id).with_for_update()
    )
    if defender is None or attacker is None or attacker.city_id is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "pvp.target_not_found", "message": "Eligible target not found"},
        )
    open_count = (
        db.scalar(
            select(func.count())
            .select_from(PvpOperation)
            .where(
                PvpOperation.attacker_profile_id == attacker.id,
                PvpOperation.status.in_(PVP_OPEN_STATES),
            )
        )
        or 0
    )
    if open_count >= attacker.operation_slots:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "pvp.operation_slots_full",
                "message": "No PvP operation slot available",
            },
        )
    apply_profile_resource(
        db,
        attacker.id,
        "cash",
        -preview.estimated_cost_cash,
        reason="pvp_operation_reservation",
        reference_type="pvp_operation",
        reference_id=defender.id,
        idempotency_key=idempotency_key,
    )
    apply_profile_resource(
        db,
        attacker.id,
        "influence",
        -preview.estimated_cost_influence,
        reason="pvp_operation_reservation",
        reference_type="pvp_operation",
        reference_id=defender.id,
        idempotency_key=idempotency_key,
    )
    now = datetime.now(UTC)
    duration = (
        1 if settings.app_env == "test" else int(PVP_OPERATION_TYPES[operation_type]["minutes"])
    )
    response_minutes = 1 if settings.app_env == "test" else max(5, duration // 2)
    attacker_cartel = _cartel_for_profile(db, attacker.id)
    defender_cartel = _cartel_for_profile(db, defender.id)
    operation = PvpOperation(
        world_id=attacker.world_id,
        city_id=attacker.city_id,
        attacker_profile_id=attacker.id,
        attacker_cartel_id=attacker_cartel.id if attacker_cartel else None,
        defender_profile_id=defender.id,
        defender_cartel_id=defender_cartel.id if defender_cartel else None,
        operation_type=operation_type,
        target_type="profile",
        target_id=defender.id,
        district_id=district_id or defender.home_district_id,
        risk_posture=risk_posture,
        status="warning",
        response_deadline_at=now + timedelta(minutes=response_minutes),
        resolves_at=now + timedelta(minutes=duration),
        attacker_commitment={
            "cash": str(preview.estimated_cost_cash),
            "influence": str(preview.estimated_cost_influence),
            "reward_multiplier": str(preview.reward_multiplier),
        },
        idempotency_key=idempotency_key,
    )
    db.add(operation)
    db.flush()
    db.add_all(
        [
            PvpOperationParticipant(
                world_id=attacker.world_id,
                operation_id=operation.id,
                profile_id=attacker.id,
                cartel_id=operation.attacker_cartel_id,
                side="attacker",
            ),
            PvpOperationParticipant(
                world_id=attacker.world_id,
                operation_id=operation.id,
                profile_id=defender.id,
                cartel_id=operation.defender_cartel_id,
                side="defender",
            ),
        ]
    )
    if as_utc(attacker.protected_until) > now:
        attacker.protected_until = now
    defender_user = db.get(User, defender.user_id)
    if defender_user:
        create_notification(
            db,
            defender_user.id,
            "pvp.operation_detected",
            "Important organization development",
            "A time-sensitive defensive decision is available.",
            {"operation_id": operation.id},
        )
    emit_realtime(
        db,
        attacker.world_id,
        "pvp.operation_detected",
        {"operation_id": operation.id},
        [defender.id],
    )
    audit(
        db,
        user.id,
        "pvp.operation_launched",
        "pvp_operation",
        operation.id,
        request_id,
        {"operation_type": operation_type, "target_profile_id": defender.id},
    )
    return operation


def defend_pvp_operation(
    db: Session,
    user: User,
    profile: PlayerProfile,
    operation_id: str,
    action_type: str,
    commitment: dict[str, Any],
    request_id: str,
) -> PvpOperation:
    if action_type not in PVP_DEFENSE_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail={"code": "pvp.invalid_defense", "message": "Unsupported defense action"},
        )
    operation = db.scalar(
        select(PvpOperation).where(PvpOperation.id == operation_id).with_for_update()
    )
    now = datetime.now(UTC)
    if operation is None or operation.defender_profile_id != profile.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "pvp.operation_not_found", "message": "Defensive operation not found"},
        )
    if operation.status not in PVP_OPEN_STATES or as_utc(operation.resolves_at) < now:
        raise HTTPException(
            status_code=409,
            detail={"code": "pvp.response_closed", "message": "Defense response window is closed"},
        )
    existing = db.scalar(
        select(PvpDefenseAction).where(
            PvpDefenseAction.operation_id == operation.id,
            PvpDefenseAction.profile_id == profile.id,
        )
    )
    if existing:
        return operation
    action = PvpDefenseAction(
        world_id=profile.world_id,
        operation_id=operation.id,
        profile_id=profile.id,
        action_type=action_type,
        commitment_json=commitment,
    )
    db.add(action)
    operation.defender_commitment = {
        "submitted": True,
        "defense_power": PVP_DEFENSE_ACTIONS[action_type],
    }
    operation.status = "running"
    operation.version += 1
    emit_realtime(
        db,
        profile.world_id,
        "pvp.operation_updated",
        {"operation_id": operation.id, "status": operation.status},
        [operation.attacker_profile_id, operation.defender_profile_id],
    )
    audit(
        db,
        user.id,
        "pvp.defense_submitted",
        "pvp_operation",
        operation.id,
        request_id,
        {"action_type": action_type},
    )
    return operation


def support_pvp_operation(
    db: Session,
    user: User,
    profile: PlayerProfile,
    operation_id: str,
    side: str,
    cash: Decimal,
    influence: Decimal,
    idempotency_key: str,
    request_id: str,
) -> PvpOperation:
    operation = db.scalar(
        select(PvpOperation).where(PvpOperation.id == operation_id).with_for_update()
    )
    if operation is None or operation.status not in PVP_OPEN_STATES:
        raise HTTPException(
            status_code=404,
            detail={"code": "pvp.operation_not_found", "message": "Open PvP operation not found"},
        )
    membership = active_membership(db, profile.id)
    expected_cartel = (
        operation.attacker_cartel_id if side == "attacker" else operation.defender_cartel_id
    )
    if (
        membership is None
        or expected_cartel is None
        or membership.organization_id != expected_cartel
    ):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "pvp.support_denied",
                "message": "Cartel membership does not match side",
            },
        )
    existing = db.scalar(
        select(PvpOperationParticipant).where(
            PvpOperationParticipant.operation_id == operation.id,
            PvpOperationParticipant.profile_id == profile.id,
        )
    )
    if existing and existing.contribution_json:
        return operation
    if cash > 0:
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            -cash,
            reason="pvp_support",
            reference_type="pvp_operation",
            reference_id=operation.id,
            idempotency_key=idempotency_key,
        )
    if influence > 0:
        apply_profile_resource(
            db,
            profile.id,
            "influence",
            -influence,
            reason="pvp_support",
            reference_type="pvp_operation",
            reference_id=operation.id,
            idempotency_key=idempotency_key,
        )
    participant = existing or PvpOperationParticipant(
        world_id=profile.world_id,
        operation_id=operation.id,
        profile_id=profile.id,
        cartel_id=membership.organization_id,
        side=side,
    )
    participant.contribution_json = {"cash": str(cash), "influence": str(influence)}
    db.add(participant)
    audit(
        db,
        user.id,
        "pvp.support_committed",
        "pvp_operation",
        operation.id,
        request_id,
        {"side": side},
    )
    return operation


def _district_influence(
    db: Session, district_id: str, profile_id: str, kind: str
) -> DistrictInfluence:
    influence = db.scalar(
        select(DistrictInfluence)
        .where(
            DistrictInfluence.district_id == district_id,
            DistrictInfluence.profile_id == profile_id,
            DistrictInfluence.kind == kind,
        )
        .with_for_update()
    )
    if influence is None:
        influence = DistrictInfluence(
            district_id=district_id,
            profile_id=profile_id,
            kind=kind,
            points=Decimal("0"),
        )
        db.add(influence)
        db.flush()
    return influence


def _operation_roll(operation: PvpOperation, settings: Settings) -> int:
    material = f"{operation.id}:{settings.seed_secret.get_secret_value()}".encode()
    return int(hashlib.sha256(material).hexdigest()[:8], 16) % 100


def resolve_pvp_operation(db: Session, operation: PvpOperation, settings: Settings) -> PvpOperation:
    if operation.status in {"resolved", "cancelled"}:
        return operation
    attacker = db.get(PlayerProfile, operation.attacker_profile_id)
    defender = db.get(PlayerProfile, operation.defender_profile_id)
    if attacker is None or defender is None:
        operation.status = "cancelled"
        operation.resolved_at = datetime.now(UTC)
        return operation
    config = PVP_OPERATION_TYPES[operation.operation_type]
    risk = RISK_POSTURES[operation.risk_posture]
    defense_action = db.scalar(
        select(PvpDefenseAction).where(PvpDefenseAction.operation_id == operation.id)
    )
    defense_power = PVP_DEFENSE_ACTIONS.get(defense_action.action_type, 4) if defense_action else 4
    attacker_support = Decimal("0")
    defender_support = Decimal("0")
    for participant in db.scalars(
        select(PvpOperationParticipant).where(PvpOperationParticipant.operation_id == operation.id)
    ):
        contribution = participant.contribution_json or {}
        score = as_decimal(contribution.get("cash", 0)) / Decimal("2500") + as_decimal(
            contribution.get("influence", 0)
        )
        if participant.side == "attacker":
            attacker_support += score
        else:
            defender_support += score
    attacker_power = (
        Decimal(int(config["base_power"]))
        + _strength_value(db, attacker) / Decimal("5")
        + attacker_support
        + Decimal(int(risk["chance"]))
    )
    defender_power = (
        Decimal(defender.stability) / Decimal("4")
        + Decimal(defense_power)
        + defender_support
        + Decimal("10")
    )
    threshold = max(
        Decimal("15"), min(Decimal("85"), Decimal("50") + attacker_power - defender_power)
    )
    roll = _operation_roll(operation, settings)
    success = Decimal(roll) < threshold
    reward_multiplier = as_decimal(operation.attacker_commitment.get("reward_multiplier", "1"))
    effect_cap = as_decimal(config["effect_cap"])
    effect = max(Decimal("1"), (effect_cap * reward_multiplier).quantize(Decimal("0.01")))
    kind = {
        "intelligence_probe": "information",
        "market_pressure": "economic",
        "influence_campaign": "social",
        "abstract_disruption": "digital",
        "strategic_confrontation": "street",
    }[operation.operation_type]
    if operation.district_id:
        attacker_influence = _district_influence(db, operation.district_id, attacker.id, kind)
        defender_influence = _district_influence(db, operation.district_id, defender.id, kind)
        if success:
            attacker_influence.points = as_decimal(attacker_influence.points) + effect
            defender_influence.points = max(
                Decimal("0"), as_decimal(defender_influence.points) - effect / Decimal("2")
            )
        else:
            defender_influence.points = as_decimal(defender_influence.points) + Decimal("0.50")
    attacker_rep = get_or_create_reputation(db, attacker)
    defender_rep = get_or_create_reputation(db, defender)
    attacker_rep.attack_count += 1
    attacker_rep.aggression = min(100, attacker_rep.aggression + 2)
    defender_rep.defense_count += 1
    defender_rep.defense = min(100, defender_rep.defense + (2 if not success else 1))
    attacker_rep.version += 1
    defender_rep.version += 1
    attacker_summary = (
        "The operation achieved a limited strategic effect."
        if success
        else "The operation was contained."
    )
    defender_summary = (
        "Defensive measures limited the rival operation."
        if not success
        else "A rival operation caused a limited temporary setback."
    )
    attacker_report = PvpReport(
        world_id=operation.world_id,
        operation_id=operation.id,
        profile_id=attacker.id,
        perspective="attacker",
        summary=attacker_summary,
        confidence=65,
        details_json={
            "outcome": "success" if success else "contained",
            "effect_band": "limited",
            "district_id": operation.district_id,
            "defense": "unknown_countermeasures",
        },
    )
    defender_report = PvpReport(
        world_id=operation.world_id,
        operation_id=operation.id,
        profile_id=defender.id,
        perspective="defender",
        summary=defender_summary,
        confidence=85,
        details_json={
            "outcome": "contained" if not success else "limited_setback",
            "effect_points": str(effect if success else Decimal("0")),
            "district_id": operation.district_id,
            "defense_action": defense_action.action_type if defense_action else "passive_defense",
        },
    )
    db.add_all([attacker_report, defender_report])
    db.flush()
    operation.attacker_report_id = attacker_report.id
    operation.defender_report_id = defender_report.id
    operation.status = "resolved"
    operation.resolved_at = datetime.now(UTC)
    operation.result_payload = {
        "outcome": "attacker_advantage" if success else "defender_advantage",
        "effect_band": "limited",
    }
    operation.version += 1
    cooldown = db.scalar(
        select(PvpCooldown).where(
            PvpCooldown.attacker_profile_id == attacker.id,
            PvpCooldown.defender_profile_id == defender.id,
            PvpCooldown.cooldown_type == "direct_target",
        )
    )
    if cooldown is None:
        cooldown = PvpCooldown(
            world_id=operation.world_id,
            attacker_profile_id=attacker.id,
            defender_profile_id=defender.id,
            cooldown_type="direct_target",
            expires_at=datetime.now(UTC) + timedelta(hours=2),
        )
        db.add(cooldown)
    else:
        cooldown.expires_at = datetime.now(UTC) + timedelta(hours=2)
    for target in (attacker, defender):
        target_user = db.get(User, target.user_id)
        if target_user:
            create_notification(
                db,
                target_user.id,
                "pvp.operation_resolved",
                "Operation report available",
                "A multiplayer operation has been resolved.",
                {"operation_id": operation.id},
            )
    emit_realtime(
        db,
        operation.world_id,
        "pvp.operation_resolved",
        {"operation_id": operation.id},
        [attacker.id, defender.id],
    )
    audit(
        db,
        None,
        "pvp.operation_resolved",
        "pvp_operation",
        operation.id,
        f"worker:{operation.id}",
        {"outcome": operation.result_payload["outcome"]},
    )
    return operation


def cancel_pvp_operation(
    db: Session,
    user: User,
    profile: PlayerProfile,
    operation_id: str,
    request_id: str,
) -> PvpOperation:
    operation = db.scalar(
        select(PvpOperation).where(PvpOperation.id == operation_id).with_for_update()
    )
    if operation is None or operation.attacker_profile_id != profile.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "pvp.operation_not_found", "message": "PvP operation not found"},
        )
    if operation.status != "warning" or operation.defender_commitment:
        raise HTTPException(
            status_code=409,
            detail={"code": "pvp.cancel_closed", "message": "Operation can no longer be cancelled"},
        )
    operation.status = "cancelled"
    operation.resolved_at = datetime.now(UTC)
    operation.version += 1
    reserved_cash = as_decimal(operation.attacker_commitment.get("cash", 0))
    reserved_influence = as_decimal(operation.attacker_commitment.get("influence", 0))
    if reserved_cash:
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            reserved_cash / Decimal("2"),
            reason="pvp_cancel_refund",
            reference_type="pvp_operation",
            reference_id=operation.id,
            idempotency_key=f"cancel:{operation.id}",
        )
    if reserved_influence:
        apply_profile_resource(
            db,
            profile.id,
            "influence",
            reserved_influence / Decimal("2"),
            reason="pvp_cancel_refund",
            reference_type="pvp_operation",
            reference_id=operation.id,
            idempotency_key=f"cancel:{operation.id}",
        )
    audit(
        db,
        user.id,
        "pvp.operation_cancelled",
        "pvp_operation",
        operation.id,
        request_id,
    )
    return operation


def resolve_due_pvp(db: Session, settings: Settings, at: datetime | None = None) -> int:
    now = at or datetime.now(UTC)
    resolved = 0
    operations = db.scalars(
        select(PvpOperation)
        .where(PvpOperation.status.in_(PVP_OPEN_STATES), PvpOperation.resolves_at <= now)
        .with_for_update(skip_locked=True)
    )
    for operation in operations:
        resolve_pvp_operation(db, operation, settings)
        resolved += 1
    return resolved


def _territory_view(db: Session, district: District) -> TerritoryView:
    claims = list(
        db.scalars(
            select(TerritoryClaim)
            .where(TerritoryClaim.district_id == district.id, TerritoryClaim.status != "abandoned")
            .order_by(TerritoryClaim.claim_strength.desc())
        )
    )
    points = list(
        db.scalars(
            select(TerritoryControlPoint)
            .where(TerritoryControlPoint.district_id == district.id)
            .order_by(TerritoryControlPoint.point_type)
        )
    )
    controlling = next(
        (point.controlling_cartel_id for point in points if point.controlling_cartel_id), None
    )
    controlled_count = sum(1 for point in points if point.controlling_cartel_id == controlling)
    status = "neutral"
    if claims and not controlling:
        status = "contested"
    elif controlling and controlled_count >= 5:
        status = "dominant"
    elif controlling and controlled_count >= 3:
        status = "controlled"
    elif controlling:
        status = "influenced"
    return TerritoryView(
        district_id=district.id,
        district_name=district.name,
        status=status,
        controlling_cartel_id=controlling,
        active_claims=[TerritoryClaimView.model_validate(item) for item in claims],
        control_points=[TerritoryControlPointView.model_validate(item) for item in points],
    )


def territories(db: Session, profile: PlayerProfile) -> list[TerritoryView]:
    districts = db.scalars(
        select(District)
        .where(District.world_id == profile.world_id, District.city_id == profile.city_id)
        .order_by(District.name)
    )
    return [_territory_view(db, district) for district in districts]


def claim_territory(
    db: Session,
    user: User,
    profile: PlayerProfile,
    district_id: str,
    idempotency_key: str,
    request_id: str,
) -> TerritoryClaim:
    membership = membership_with_permission(db, profile.id, "territory.claim")
    district = db.get(District, district_id)
    if (
        district is None
        or district.world_id != profile.world_id
        or district.city_id != profile.city_id
        or profile.city_id is None
    ):
        raise HTTPException(
            status_code=404,
            detail={"code": "territory.not_found", "message": "District territory not found"},
        )
    existing = db.scalar(
        select(TerritoryClaim).where(
            TerritoryClaim.district_id == district.id,
            TerritoryClaim.cartel_id == membership.organization_id,
            TerritoryClaim.status.in_(("claimed", "contested", "controlled")),
        )
    )
    if existing:
        return existing
    apply_profile_resource(
        db,
        profile.id,
        "influence",
        -3,
        reason="territory_claim",
        reference_type="district",
        reference_id=district.id,
        idempotency_key=idempotency_key,
    )
    claim = TerritoryClaim(
        world_id=profile.world_id,
        city_id=profile.city_id,
        district_id=district.id,
        cartel_id=membership.organization_id,
        status="claimed",
        claim_strength=Decimal("10"),
        visibility=15,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    db.add(claim)
    db.flush()
    db.add(
        TerritoryHistory(
            world_id=profile.world_id,
            district_id=district.id,
            event_type="claim_created",
            previous_cartel_id=None,
            new_cartel_id=membership.organization_id,
            payload_json={"claim_id": claim.id},
        )
    )
    emit_realtime(
        db,
        profile.world_id,
        "territory.claimed",
        {"district_id": district.id, "claim_id": claim.id},
    )
    audit(
        db,
        user.id,
        "territory.claimed",
        "territory_claim",
        claim.id,
        request_id,
        {"district_id": district.id},
    )
    return claim


def contribute_territory(
    db: Session,
    user: User,
    profile: PlayerProfile,
    district_id: str,
    contribution_type: str,
    amount: Decimal,
    idempotency_key: str,
    request_id: str,
    *,
    challenge: bool = False,
) -> TerritoryClaim:
    permission = "territory.defend" if not challenge else "territory.claim"
    membership = membership_with_permission(db, profile.id, permission)
    claim = db.scalar(
        select(TerritoryClaim)
        .where(
            TerritoryClaim.district_id == district_id,
            TerritoryClaim.cartel_id == membership.organization_id,
            TerritoryClaim.status.in_(("claimed", "contested", "controlled")),
        )
        .with_for_update()
    )
    if claim is None:
        if not challenge:
            raise HTTPException(
                status_code=404,
                detail={"code": "territory.claim_not_found", "message": "Active claim not found"},
            )
        claim = claim_territory(
            db, user, profile, district_id, idempotency_key + ":claim", request_id
        )
        claim.status = "contested"
    existing = db.scalar(
        select(TerritoryContribution).where(
            TerritoryContribution.profile_id == profile.id,
            TerritoryContribution.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return claim
    cost = max(Decimal("1"), as_decimal(amount) / Decimal("5"))
    apply_profile_resource(
        db,
        profile.id,
        "influence",
        -cost,
        reason="territory_challenge" if challenge else "territory_support",
        reference_type="territory_claim",
        reference_id=claim.id,
        idempotency_key=idempotency_key,
    )
    contribution = TerritoryContribution(
        world_id=profile.world_id,
        claim_id=claim.id,
        district_id=district_id,
        cartel_id=membership.organization_id,
        profile_id=profile.id,
        contribution_type="challenge" if challenge else contribution_type,
        amount=amount,
        idempotency_key=idempotency_key,
    )
    db.add(contribution)
    claim.claim_strength = as_decimal(claim.claim_strength) + as_decimal(amount)
    claim.status = "contested" if challenge else claim.status
    claim.visibility = min(100, claim.visibility + int(amount))
    claim.version += 1
    if claim.claim_strength >= Decimal("50"):
        point = db.scalar(
            select(TerritoryControlPoint)
            .where(TerritoryControlPoint.district_id == district_id)
            .order_by(TerritoryControlPoint.control_value, TerritoryControlPoint.point_type)
            .with_for_update()
        )
        if point:
            previous = point.controlling_cartel_id
            point.controlling_cartel_id = membership.organization_id
            point.control_value = min(Decimal("100"), claim.claim_strength)
            point.status = "controlled"
            point.version += 1
            claim.status = "controlled"
            db.add(
                TerritoryHistory(
                    world_id=profile.world_id,
                    district_id=district_id,
                    event_type="control_changed",
                    previous_cartel_id=previous,
                    new_cartel_id=membership.organization_id,
                    payload_json={"control_point_id": point.id},
                )
            )
            emit_realtime(
                db,
                profile.world_id,
                "territory.control_changed",
                {"district_id": district_id, "control_point_id": point.id},
            )
    audit(
        db,
        user.id,
        "territory.challenged" if challenge else "territory.supported",
        "territory_claim",
        claim.id,
        request_id,
        {"amount": str(amount), "contribution_type": contribution_type},
    )
    return claim


def abandon_territory(
    db: Session,
    user: User,
    profile: PlayerProfile,
    district_id: str,
    request_id: str,
) -> TerritoryClaim:
    membership = membership_with_permission(db, profile.id, "territory.abandon")
    claim = db.scalar(
        select(TerritoryClaim)
        .where(
            TerritoryClaim.district_id == district_id,
            TerritoryClaim.cartel_id == membership.organization_id,
            TerritoryClaim.status != "abandoned",
        )
        .with_for_update()
    )
    if claim is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "territory.claim_not_found", "message": "Active claim not found"},
        )
    claim.status = "abandoned"
    claim.version += 1
    for point in db.scalars(
        select(TerritoryControlPoint)
        .where(
            TerritoryControlPoint.district_id == district_id,
            TerritoryControlPoint.controlling_cartel_id == membership.organization_id,
        )
        .with_for_update()
    ):
        point.controlling_cartel_id = None
        point.control_value = Decimal("0")
        point.status = "neutral"
        point.version += 1
    db.add(
        TerritoryHistory(
            world_id=profile.world_id,
            district_id=district_id,
            event_type="claim_abandoned",
            previous_cartel_id=membership.organization_id,
            new_cartel_id=None,
            payload_json={"claim_id": claim.id},
        )
    )
    audit(
        db,
        user.id,
        "territory.abandoned",
        "territory_claim",
        claim.id,
        request_id,
    )
    return claim


def war_for_profile(db: Session, war_id: str, profile: PlayerProfile) -> CartelWar:
    war = db.get(CartelWar, war_id)
    if war is None or war.world_id != profile.world_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "war.not_found", "message": "Cartel war not found"},
        )
    membership = active_membership(db, profile.id)
    if membership is None or membership.organization_id not in {
        war.attacker_cartel_id,
        war.defender_cartel_id,
    }:
        raise HTTPException(
            status_code=403,
            detail={"code": "war.access_denied", "message": "War-room access denied"},
        )
    return war


def propose_cartel_war(
    db: Session,
    user: User,
    profile: PlayerProfile,
    defender_cartel_id: str,
    war_type: str,
    city_id: str | None,
    district_id: str | None,
    declaration_reason: str,
    demand: str,
    peace_conditions: str,
    request_id: str,
) -> CartelWar:
    membership = membership_with_permission(db, profile.id, "wars.propose")
    attacker = db.get(Organization, membership.organization_id)
    defender = db.get(Organization, defender_cartel_id)
    if (
        attacker is None
        or defender is None
        or attacker.id == defender.id
        or defender.world_id != profile.world_id
    ):
        raise HTTPException(
            status_code=404,
            detail={"code": "war.defender_not_found", "message": "Defender cartel not found"},
        )
    relationship = _treaty_status(db, attacker.id, defender.id)
    if relationship in {"non_aggression", "alliance"}:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "war.treaty_block",
                "message": "Active alliance or non-aggression treaty blocks war",
            },
        )
    existing = db.scalar(
        select(CartelWar).where(
            CartelWar.world_id == profile.world_id,
            CartelWar.war_status.in_(WAR_OPEN_STATES),
            or_(
                (CartelWar.attacker_cartel_id == attacker.id)
                & (CartelWar.defender_cartel_id == defender.id),
                (CartelWar.attacker_cartel_id == defender.id)
                & (CartelWar.defender_cartel_id == attacker.id),
            ),
        )
    )
    if existing:
        return existing
    war = CartelWar(
        world_id=profile.world_id,
        attacker_cartel_id=attacker.id,
        defender_cartel_id=defender.id,
        war_type=war_type,
        war_status="ultimatum",
        city_id=city_id or attacker.city_id,
        objective_config={
            "district_id": district_id,
            "demand": demand,
            "peace_conditions": peace_conditions,
        },
        rules_config={
            "territorial": 25,
            "economic": 20,
            "operations": 20,
            "intelligence": 15,
            "participation": 10,
            "stability": 10,
        },
        declaration_reason=declaration_reason,
    )
    db.add(war)
    db.flush()
    db.add_all(
        [
            CartelWarObjective(
                world_id=profile.world_id,
                war_id=war.id,
                objective_type=war_type,
                district_id=district_id,
            ),
            CartelWarScore(world_id=profile.world_id, war_id=war.id, cartel_id=attacker.id),
            CartelWarScore(world_id=profile.world_id, war_id=war.id, cartel_id=defender.id),
            CartelWarEvent(
                world_id=profile.world_id,
                war_id=war.id,
                event_type="ultimatum_issued",
                actor_cartel_id=attacker.id,
                public_payload={"war_type": war_type, "city_id": war.city_id},
                private_payload={"demand": demand, "peace_conditions": peace_conditions},
            ),
        ]
    )
    defender_profiles = list(
        db.scalars(
            select(OrganizationMembership.profile_id).where(
                OrganizationMembership.organization_id == defender.id,
                OrganizationMembership.status == "active",
            )
        )
    )
    emit_realtime(
        db,
        profile.world_id,
        "cartel.war_proposed",
        {"war_id": war.id},
        defender_profiles,
    )
    audit(
        db,
        user.id,
        "cartel_war.proposed",
        "cartel_war",
        war.id,
        request_id,
        {"defender_cartel_id": defender.id},
    )
    return war


def declare_cartel_war(
    db: Session,
    user: User,
    profile: PlayerProfile,
    war_id: str,
    request_id: str,
    settings: Settings,
) -> CartelWar:
    membership = membership_with_permission(db, profile.id, "wars.declare")
    war = db.scalar(select(CartelWar).where(CartelWar.id == war_id).with_for_update())
    if (
        war is None
        or war.attacker_cartel_id != membership.organization_id
        or war.war_status != "ultimatum"
    ):
        raise HTTPException(
            status_code=409,
            detail={"code": "war.declare_invalid", "message": "War cannot be declared"},
        )
    now = datetime.now(UTC)
    prep_hours = 0 if settings.app_env == "test" else 12
    active_hours = 1 if settings.app_env == "test" else 6
    war.war_status = "preparation"
    war.preparation_starts_at = now
    war.active_starts_at = now + timedelta(hours=prep_hours)
    war.active_ends_at = war.active_starts_at + timedelta(hours=active_hours)
    war.aftermath_ends_at = war.active_ends_at + timedelta(hours=24)
    war.version += 1
    db.add(
        CartelWarEvent(
            world_id=war.world_id,
            war_id=war.id,
            event_type="war_declared",
            actor_cartel_id=membership.organization_id,
            public_payload={"active_starts_at": war.active_starts_at.isoformat()},
            private_payload={},
        )
    )
    affected_profiles = list(
        db.scalars(
            select(OrganizationMembership.profile_id).where(
                OrganizationMembership.organization_id.in_(
                    (war.attacker_cartel_id, war.defender_cartel_id)
                ),
                OrganizationMembership.status == "active",
            )
        )
    )
    emit_realtime(
        db,
        war.world_id,
        "cartel.war_declared",
        {"war_id": war.id},
        affected_profiles,
    )
    audit(
        db,
        user.id,
        "cartel_war.declared",
        "cartel_war",
        war.id,
        request_id,
    )
    return war


def advance_cartel_war(db: Session, war: CartelWar, at: datetime | None = None) -> CartelWar:
    now = at or datetime.now(UTC)
    previous = war.war_status
    if (
        war.war_status == "preparation"
        and war.active_starts_at
        and as_utc(war.active_starts_at) <= now
    ):
        war.war_status = "active"
    elif war.war_status == "active" and war.active_ends_at and as_utc(war.active_ends_at) <= now:
        war.war_status = "aftermath"
    elif (
        war.war_status == "aftermath"
        and war.aftermath_ends_at
        and as_utc(war.aftermath_ends_at) <= now
    ):
        war.war_status = "ended"
        if as_decimal(war.attacker_score) > as_decimal(war.defender_score):
            war.winner_cartel_id = war.attacker_cartel_id
            war.resolution_type = "score_victory"
        elif as_decimal(war.defender_score) > as_decimal(war.attacker_score):
            war.winner_cartel_id = war.defender_cartel_id
            war.resolution_type = "score_victory"
        else:
            war.resolution_type = "stalemate"
    if war.war_status != previous:
        war.version += 1
        db.add(
            CartelWarEvent(
                world_id=war.world_id,
                war_id=war.id,
                event_type=f"phase_{war.war_status}",
                actor_cartel_id=None,
                public_payload={"previous": previous, "current": war.war_status},
                private_payload={},
            )
        )
        emit_realtime(
            db,
            war.world_id,
            "cartel.war_started" if war.war_status == "active" else "cartel.war_event_created",
            {"war_id": war.id, "status": war.war_status},
        )
    return war


def join_cartel_war(
    db: Session, profile: PlayerProfile, war_id: str, side: str
) -> CartelWarParticipant:
    membership = membership_with_permission(db, profile.id, "wars.prepare")
    war = db.scalar(select(CartelWar).where(CartelWar.id == war_id).with_for_update())
    if war is None:
        raise HTTPException(
            status_code=404, detail={"code": "war.not_found", "message": "Cartel war not found"}
        )
    expected_cartel = war.attacker_cartel_id if side == "attacker" else war.defender_cartel_id
    if membership.organization_id != expected_cartel or war.war_status not in {
        "preparation",
        "active",
    }:
        raise HTTPException(
            status_code=403,
            detail={"code": "war.join_denied", "message": "Cannot join this war side"},
        )
    participant = db.scalar(
        select(CartelWarParticipant).where(
            CartelWarParticipant.war_id == war.id,
            CartelWarParticipant.profile_id == profile.id,
        )
    )
    if participant:
        return participant
    participant = CartelWarParticipant(
        world_id=profile.world_id,
        war_id=war.id,
        cartel_id=membership.organization_id,
        profile_id=profile.id,
        side=side,
    )
    db.add(participant)
    return participant


def commit_war_resources(
    db: Session,
    user: User,
    profile: PlayerProfile,
    war_id: str,
    resource_type: str,
    amount: Decimal,
    idempotency_key: str,
    request_id: str,
) -> CartelWar:
    membership = membership_with_permission(db, profile.id, "wars.commit_resources")
    war = war_for_profile(db, war_id, profile)
    organization = db.scalar(
        select(Organization).where(Organization.id == membership.organization_id).with_for_update()
    )
    if organization is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "organization.not_found", "message": "Organization not found"},
        )
    existing = db.scalar(
        select(LedgerEntry).where(
            LedgerEntry.owner_type == "organization",
            LedgerEntry.owner_id == organization.id,
            LedgerEntry.idempotency_key == idempotency_key,
            LedgerEntry.resource_type == resource_type,
        )
    )
    if existing:
        return war
    field = f"treasury_{resource_type}"
    current = as_decimal(getattr(organization, field))
    if current < amount:
        raise HTTPException(
            status_code=409,
            detail={"code": "war.treasury_insufficient", "message": "Insufficient cartel treasury"},
        )
    new_balance = current - amount
    setattr(organization, field, new_balance)
    organization.version += 1
    db.add(
        LedgerEntry(
            owner_type="organization",
            owner_id=organization.id,
            resource_type=resource_type,
            amount=-amount,
            balance_after=new_balance,
            reason="cartel_war_commitment",
            reference_type="cartel_war",
            reference_id=war.id,
            idempotency_key=idempotency_key,
            metadata_json={"profile_id": profile.id},
        )
    )
    audit(
        db,
        user.id,
        "cartel_war.resources_committed",
        "cartel_war",
        war.id,
        request_id,
        {"resource_type": resource_type, "amount": str(amount)},
    )
    return war


def _recalculate_war_score(score: CartelWarScore) -> None:
    score.total = (
        as_decimal(score.territorial) * WAR_SCORE_WEIGHTS["territorial"]
        + as_decimal(score.economic) * WAR_SCORE_WEIGHTS["economic"]
        + as_decimal(score.operations) * WAR_SCORE_WEIGHTS["operations"]
        + as_decimal(score.intelligence) * WAR_SCORE_WEIGHTS["intelligence"]
        + as_decimal(score.participation) * WAR_SCORE_WEIGHTS["participation"]
        + as_decimal(score.stability) * WAR_SCORE_WEIGHTS["stability"]
        - as_decimal(score.penalties)
    ).quantize(Decimal("0.01"))
    score.version += 1


def launch_war_operation(
    db: Session,
    user: User,
    profile: PlayerProfile,
    war_id: str,
    operation_type: str,
    district_id: str | None,
    cash: Decimal,
    influence: Decimal,
    idempotency_key: str,
    request_id: str,
) -> CartelWarOperation:
    membership = membership_with_permission(db, profile.id, "wars.prepare")
    war = war_for_profile(db, war_id, profile)
    advance_cartel_war(db, war)
    if war.war_status != "active":
        raise HTTPException(
            status_code=409,
            detail={"code": "war.not_active", "message": "War operation window is not active"},
        )
    participant = db.scalar(
        select(CartelWarParticipant).where(
            CartelWarParticipant.war_id == war.id,
            CartelWarParticipant.profile_id == profile.id,
            CartelWarParticipant.status == "active",
        )
    )
    if participant is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "war.participation_required", "message": "Join the war first"},
        )
    existing = db.scalar(
        select(CartelWarOperation).where(
            CartelWarOperation.profile_id == profile.id,
            CartelWarOperation.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return existing
    if cash > 0:
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            -cash,
            reason="cartel_war_operation",
            reference_type="cartel_war",
            reference_id=war.id,
            idempotency_key=idempotency_key,
        )
    if influence > 0:
        apply_profile_resource(
            db,
            profile.id,
            "influence",
            -influence,
            reason="cartel_war_operation",
            reference_type="cartel_war",
            reference_id=war.id,
            idempotency_key=idempotency_key,
        )
    delta = min(Decimal("25"), Decimal("5") + cash / Decimal("5000") + influence)
    score = db.scalar(
        select(CartelWarScore)
        .where(
            CartelWarScore.war_id == war.id,
            CartelWarScore.cartel_id == membership.organization_id,
        )
        .with_for_update()
    )
    if score is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "war.score_missing", "message": "War score state is missing"},
        )
    setattr(score, operation_type, as_decimal(getattr(score, operation_type)) + delta)
    score.participation = as_decimal(score.participation) + Decimal("1")
    _recalculate_war_score(score)
    if membership.organization_id == war.attacker_cartel_id:
        war.attacker_score = score.total
    else:
        war.defender_score = score.total
    war.version += 1
    participant.contribution_score = as_decimal(participant.contribution_score) + delta
    operation = CartelWarOperation(
        world_id=profile.world_id,
        war_id=war.id,
        cartel_id=membership.organization_id,
        profile_id=profile.id,
        operation_type=operation_type,
        district_id=district_id,
        commitment_json={"cash": str(cash), "influence": str(influence)},
        score_delta=delta,
        idempotency_key=idempotency_key,
    )
    db.add(operation)
    db.add(
        CartelWarEvent(
            world_id=profile.world_id,
            war_id=war.id,
            event_type="war_operation_resolved",
            actor_cartel_id=membership.organization_id,
            public_payload={"operation_type": operation_type, "score_delta": str(delta)},
            private_payload={"profile_id": profile.id},
        )
    )
    emit_realtime(
        db,
        profile.world_id,
        "cartel.war_score_updated",
        {"war_id": war.id},
    )
    audit(
        db,
        user.id,
        "cartel_war.operation_launched",
        "cartel_war",
        war.id,
        request_id,
        {"operation_type": operation_type, "score_delta": str(delta)},
    )
    return operation


def offer_ceasefire(
    db: Session, profile: PlayerProfile, war_id: str, terms: dict[str, Any]
) -> CartelWarTreaty:
    membership = membership_with_permission(db, profile.id, "wars.negotiate_ceasefire")
    war = war_for_profile(db, war_id, profile)
    if war.war_status not in {"preparation", "active", "aftermath"}:
        raise HTTPException(
            status_code=409,
            detail={"code": "war.ceasefire_closed", "message": "Ceasefire is not available"},
        )
    treaty = CartelWarTreaty(
        world_id=profile.world_id,
        war_id=war.id,
        proposer_cartel_id=membership.organization_id,
        treaty_type="ceasefire",
        terms_json=terms,
    )
    db.add(treaty)
    db.flush()
    emit_realtime(
        db,
        profile.world_id,
        "cartel.war_ceasefire_offered",
        {"war_id": war.id, "treaty_id": treaty.id},
    )
    return treaty


def accept_ceasefire(db: Session, profile: PlayerProfile, war_id: str) -> CartelWarTreaty:
    membership = membership_with_permission(db, profile.id, "wars.negotiate_ceasefire")
    war = war_for_profile(db, war_id, profile)
    treaty = db.scalar(
        select(CartelWarTreaty)
        .where(
            CartelWarTreaty.war_id == war.id,
            CartelWarTreaty.status == "offered",
            CartelWarTreaty.proposer_cartel_id != membership.organization_id,
        )
        .order_by(CartelWarTreaty.created_at.desc())
        .with_for_update()
    )
    if treaty is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "war.ceasefire_not_found", "message": "Ceasefire offer not found"},
        )
    treaty.status = "accepted"
    treaty.accepted_at = datetime.now(UTC)
    war.war_status = "ended"
    war.resolution_type = "ceasefire"
    war.version += 1
    db.add(
        CartelWarEvent(
            world_id=war.world_id,
            war_id=war.id,
            event_type="ceasefire_accepted",
            actor_cartel_id=membership.organization_id,
            public_payload={},
            private_payload={"treaty_id": treaty.id},
        )
    )
    emit_realtime(
        db, war.world_id, "cartel.war_ended", {"war_id": war.id, "resolution": "ceasefire"}
    )
    return treaty


def surrender_cartel_war(db: Session, profile: PlayerProfile, war_id: str) -> CartelWar:
    membership = membership_with_permission(db, profile.id, "wars.surrender")
    war = war_for_profile(db, war_id, profile)
    if war.war_status not in WAR_OPEN_STATES:
        raise HTTPException(
            status_code=409,
            detail={"code": "war.surrender_closed", "message": "War is already closed"},
        )
    war.war_status = "ended"
    war.winner_cartel_id = (
        war.defender_cartel_id
        if membership.organization_id == war.attacker_cartel_id
        else war.attacker_cartel_id
    )
    war.resolution_type = "surrender"
    war.version += 1
    emit_realtime(
        db, war.world_id, "cartel.war_ended", {"war_id": war.id, "resolution": "surrender"}
    )
    return war


def advance_due_wars(db: Session, at: datetime | None = None) -> int:
    changed = 0
    for war in db.scalars(
        select(CartelWar)
        .where(CartelWar.war_status.in_(WAR_OPEN_STATES))
        .with_for_update(skip_locked=True)
    ):
        previous = war.war_status
        advance_cartel_war(db, war, at)
        if war.war_status != previous:
            changed += 1
    return changed
