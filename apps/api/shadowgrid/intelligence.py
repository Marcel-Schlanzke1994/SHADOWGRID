from __future__ import annotations

import hashlib
import hmac
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Final

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.domain import apply_profile_resource, audit, create_notification
from shadowgrid.finance import cents_to_money
from shadowgrid.models import (
    CartelProject,
    Company,
    CompanyOwnership,
    IntelligenceOperation,
    IntelligenceReport,
    IntelligenceReportOffer,
    OrganizationMembership,
    PlayerProfile,
    PvpProtectionState,
    ResourceBalance,
    Specialist,
    StrategicAction,
    StrategicEffect,
    User,
    as_utc,
    uuid_str,
)

INFORMATION_COSTS: Final[dict[str, tuple[int, int]]] = {
    "public": (0, 5),
    "analyzed": (25_000, 15),
    "covert": (75_000, 30),
}
INFORMATION_BASE_SUCCESS_BPS: Final[dict[str, int]] = {
    "public": 9_000,
    "analyzed": 6_500,
    "covert": 5_000,
}
INFORMATION_BASE_DETECTION_BPS: Final[dict[str, int]] = {
    "public": 0,
    "analyzed": 800,
    "covert": 3_000,
}
STRATEGIC_ACTION_TARGETS: Final[dict[str, tuple[str, str, int]]] = {
    "delay_project": ("cartel_project", "project_delay", 7_200),
    "weaken_reputation": ("profile", "reputation_penalty", 800),
    "raise_operating_cost": ("company", "operating_cost_increase", 1_200),
    "make_information_unreliable": (
        "profile",
        "information_reliability_penalty",
        1_500,
    ),
    "stress_specialist": ("specialist", "specialist_stress", 1_500),
}
STRATEGIC_COST_CASH_CENTS: Final = 100_000
STRATEGIC_COST_INTELLIGENCE: Final = 40
ELIGIBLE_SPECIALIST_ROLES: Final = {
    "technology_expert",
    "market_analyst",
    "compliance_officer",
    "diplomat",
}
_LOCK = threading.RLock()


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def _rolls(secret: str, operation_id: str, idempotency_key: str) -> tuple[str, int, int, int]:
    digest = hmac.new(
        secret.encode(),
        f"{operation_id}:{idempotency_key}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return (
        digest,
        int(digest[0:8], 16) % 10_000,
        int(digest[8:16], 16) % 10_000,
        int(digest[16:24], 16) % 10_000,
    )


def _outcome(success_roll: int, success_chance_bps: int) -> str:
    if success_roll < success_chance_bps:
        return "success"
    if success_roll < min(10_000, success_chance_bps + 2_000):
        return "partial"
    return "failure"


def _active_protection(db: Session, target: PlayerProfile, now: datetime) -> int:
    protection = 0
    if as_utc(target.protected_until) > now:
        protection += 2_000
    states = int(
        db.scalar(
            select(func.count())
            .select_from(PvpProtectionState)
            .where(
                PvpProtectionState.profile_id == target.id,
                PvpProtectionState.ended_at.is_(None),
                PvpProtectionState.protected_until > now,
            )
        )
        or 0
    )
    return min(4_000, protection + states * 1_000)


def _cartel_bonus(db: Session, profile_id: str) -> int:
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.profile_id == profile_id,
            OrganizationMembership.status == "active",
        )
    )
    if membership is None:
        return 0
    return 800 if membership.role == "intelligence_officer" else 300


def _active_effect_magnitude(
    db: Session,
    *,
    effect_type: str,
    target_type: str,
    target_id: str,
    now: datetime,
) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(StrategicEffect.magnitude), 0)).where(
                StrategicEffect.effect_type == effect_type,
                StrategicEffect.target_type == target_type,
                StrategicEffect.target_id == target_id,
                StrategicEffect.starts_at <= now,
                StrategicEffect.ends_at > now,
            )
        )
        or 0
    )


def _eligible_specialist(
    db: Session,
    profile: PlayerProfile,
    specialist_id: str,
    now: datetime,
) -> Specialist:
    specialist = db.scalar(
        select(Specialist).where(Specialist.id == specialist_id).with_for_update()
    )
    if specialist is None or specialist.profile_id != profile.id:
        raise _error(404, "intelligence.specialist_not_found", "Owned specialist not found")
    if specialist.status not in {"hired", "assigned"}:
        raise _error(409, "intelligence.specialist_unavailable", "Specialist is not active")
    if specialist.role not in ELIGIBLE_SPECIALIST_ROLES:
        raise _error(
            409,
            "intelligence.specialist_ineligible",
            "Specialist role cannot perform intelligence operations",
        )
    if specialist.energy < 8:
        raise _error(409, "intelligence.specialist_exhausted", "Specialist energy is too low")
    if specialist.cooldown_until is not None and as_utc(specialist.cooldown_until) > now:
        raise _error(409, "intelligence.specialist_cooldown", "Specialist is cooling down")
    return specialist


def _target_profile(db: Session, profile: PlayerProfile, target_profile_id: str) -> PlayerProfile:
    target = db.scalar(
        select(PlayerProfile).where(PlayerProfile.id == target_profile_id).with_for_update()
    )
    if target is None or target.world_id != profile.world_id or target.id == profile.id:
        raise _error(404, "intelligence.target_not_found", "Eligible target ID not found")
    return target


def _rate_limit(
    db: Session,
    model: type[IntelligenceOperation] | type[StrategicAction],
    profile_id: str,
    limit: int,
    now: datetime,
) -> None:
    count = int(
        db.scalar(
            select(func.count())
            .select_from(model)
            .where(
                model.actor_profile_id == profile_id,
                model.created_at >= now - timedelta(minutes=1),
            )
        )
        or 0
    )
    if count >= limit:
        raise _error(429, "intelligence.rate_limited", "Too many strategic requests")


def _information_statement(
    target: PlayerProfile,
    balance: ResourceBalance,
    category: str,
    outcome: str,
    variant_roll: int,
) -> tuple[str, str, dict[str, object]]:
    cash_cents = int(Decimal(balance.cash) * Decimal(100))
    intelligence_units = int(Decimal(balance.intelligence))
    actual_band = "strong" if cash_cents >= 10_000_000 else "developing"
    snapshot: dict[str, object] = {
        "target_codename": target.codename,
        "category": category,
        "cash_band": actual_band,
        "intelligence_band": "prepared" if intelligence_units >= 100 else "limited",
        "stability": target.stability,
        "observed_city_id": target.city_id or "",
    }
    if outcome == "success":
        return (
            f"Assessment for {category}: the target's economic posture is {actual_band}.",
            "correct",
            snapshot,
        )
    if outcome == "partial":
        state = "outdated" if variant_roll % 2 else "incomplete"
        qualifier = "may have changed" if state == "outdated" else "is only partially visible"
        return (
            f"Assessment for {category}: the target's posture {qualifier}.",
            state,
            snapshot,
        )
    false_band = "developing" if actual_band == "strong" else "strong"
    return (
        f"Assessment for {category}: the target's economic posture is {false_band}.",
        "intentionally_misleading",
        snapshot,
    )


def launch_intelligence_operation(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    target_profile_id: str,
    specialist_id: str,
    information_type: str,
    category: str,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
) -> IntelligenceOperation:
    with _LOCK:
        existing = db.scalar(
            select(IntelligenceOperation).where(
                IntelligenceOperation.actor_profile_id == profile.id,
                IntelligenceOperation.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        _rate_limit(
            db,
            IntelligenceOperation,
            profile.id,
            settings.intelligence_operation_rate_limit_per_minute,
            now,
        )
        target = _target_profile(db, profile, target_profile_id)
        cooldown = db.scalar(
            select(IntelligenceOperation.id).where(
                IntelligenceOperation.actor_profile_id == profile.id,
                IntelligenceOperation.target_profile_id == target.id,
                IntelligenceOperation.category == category,
                IntelligenceOperation.cooldown_until > now,
            )
        )
        if cooldown is not None:
            raise _error(409, "intelligence.cooldown", "Target category is cooling down")
        specialist = _eligible_specialist(db, profile, specialist_id, now)
        balance = db.scalar(
            select(ResourceBalance).where(ResourceBalance.profile_id == target.id).with_for_update()
        )
        if balance is None:
            raise _error(409, "intelligence.target_state_missing", "Target state is unavailable")
        cost_cash_cents, cost_intelligence = INFORMATION_COSTS[information_type]
        operation_id = uuid_str()
        report_id = uuid_str()
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            -cents_to_money(cost_cash_cents),
            reason="intelligence_operation_reservation",
            reference_type="intelligence_operation",
            reference_id=operation_id,
            idempotency_key=f"intel-cash:{idempotency_key}",
        )
        apply_profile_resource(
            db,
            profile.id,
            "intelligence",
            -cost_intelligence,
            reason="intelligence_operation_reservation",
            reference_type="intelligence_operation",
            reference_id=operation_id,
            idempotency_key=f"intel-points:{idempotency_key}",
        )
        protection_bps = _active_protection(db, target, now)
        reliability_penalty = _active_effect_magnitude(
            db,
            effect_type="information_reliability_penalty",
            target_type="profile",
            target_id=profile.id,
            now=now,
        )
        stress_penalty = _active_effect_magnitude(
            db,
            effect_type="specialist_stress",
            target_type="specialist",
            target_id=specialist.id,
            now=now,
        )
        skill_bonus = (specialist.competence - 50) * 40 + specialist.level * 80
        success_chance = max(
            500,
            min(
                9_500,
                INFORMATION_BASE_SUCCESS_BPS[information_type]
                + skill_bonus
                + _cartel_bonus(db, profile.id)
                - protection_bps
                - reliability_penalty
                - stress_penalty,
            ),
        )
        detection_chance = max(
            0,
            min(
                9_500,
                INFORMATION_BASE_DETECTION_BPS[information_type]
                + protection_bps // 2
                + max(0, 50 - specialist.competence) * 30,
            ),
        )
        seed, success_roll, detection_roll, variant_roll = _rolls(
            settings.seed_secret.get_secret_value(),
            operation_id,
            idempotency_key,
        )
        outcome = _outcome(success_roll, success_chance)
        detected = detection_roll < detection_chance
        pressure_delta = 5 if detected else (2 if outcome == "failure" else 1)
        profile.investigation_pressure = min(100, profile.investigation_pressure + pressure_delta)
        specialist.energy = max(0, specialist.energy - 8)
        specialist.stress = min(100, specialist.stress + (6 if information_type == "covert" else 3))
        statement, accuracy_state, snapshot = _information_statement(
            target, balance, category, outcome, variant_roll
        )
        confidence = {
            "success": 8_000,
            "partial": 5_500,
            "failure": 6_500,
        }[outcome]
        observed_at = now if accuracy_state != "outdated" else now - timedelta(hours=8)
        expires_at = now + timedelta(
            hours={"public": 6, "analyzed": 12, "covert": 24}[information_type]
        )
        operation = IntelligenceOperation(
            id=operation_id,
            world_id=profile.world_id,
            actor_profile_id=profile.id,
            target_profile_id=target.id,
            specialist_id=specialist.id,
            information_type=information_type,
            category=category,
            cost_cash_cents=cost_cash_cents,
            cost_intelligence=cost_intelligence,
            random_seed=seed,
            success_roll=success_roll,
            detection_roll=detection_roll,
            success_chance_bps=success_chance,
            detection_chance_bps=detection_chance,
            outcome=outcome,
            detected=detected,
            investigation_pressure_delta=pressure_delta,
            report_id=report_id,
            idempotency_key=idempotency_key,
            cooldown_until=now
            + timedelta(minutes=settings.intelligence_operation_cooldown_minutes),
            created_at=now,
        )
        report = IntelligenceReport(
            id=report_id,
            world_id=profile.world_id,
            owner_profile_id=profile.id,
            target_type="profile",
            target_id=target.id,
            information_type=information_type,
            category=category,
            statement=statement,
            confidence_bps=confidence,
            accuracy_state=accuracy_state,
            source_category={
                "public": "public_registry",
                "analyzed": "market_analysis",
                "covert": "confidential_network",
            }[information_type],
            snapshot_json=snapshot,
            operation_id=operation_id,
            tradable=True,
            observed_at=observed_at,
            expires_at=expires_at,
            created_at=now,
        )
        db.add_all((operation, report))
        if detected:
            create_notification(
                db,
                target.user_id,
                "intelligence.activity_detected",
                "Unusual strategic interest",
                "Your organization detected abstract information-gathering activity.",
                {"target_profile_id": target.id},
            )
        audit(
            db,
            user.id,
            "intelligence.operation_resolved",
            "intelligence_operation",
            operation.id,
            request_id,
            {
                "target_profile_id": target.id,
                "outcome": outcome,
                "detected": detected,
                "success_roll": success_roll,
                "detection_roll": detection_roll,
            },
        )
        return operation


def report_for_owner(db: Session, profile: PlayerProfile, report_id: str) -> IntelligenceReport:
    report = db.get(IntelligenceReport, report_id)
    if report is None or report.owner_profile_id != profile.id:
        raise _error(404, "intelligence.report_not_found", "Owned report not found")
    return report


def create_report_offer(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    report_id: str,
    price_cents: int,
    expires_in_hours: int,
    idempotency_key: str,
    request_id: str,
) -> IntelligenceReportOffer:
    with _LOCK:
        existing = db.scalar(
            select(IntelligenceReportOffer).where(
                IntelligenceReportOffer.seller_profile_id == profile.id,
                IntelligenceReportOffer.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        report = report_for_owner(db, profile, report_id)
        now = datetime.now(UTC)
        if not report.tradable or as_utc(report.expires_at) <= now:
            raise _error(
                409,
                "intelligence.report_not_tradable",
                "Expired or restricted reports cannot be offered",
            )
        already_open = db.scalar(
            select(IntelligenceReportOffer.id).where(
                IntelligenceReportOffer.report_id == report.id,
                IntelligenceReportOffer.status == "open",
                IntelligenceReportOffer.expires_at > now,
            )
        )
        if already_open is not None:
            raise _error(409, "intelligence.offer_exists", "Report already has an open offer")
        offer = IntelligenceReportOffer(
            world_id=profile.world_id,
            report_id=report.id,
            seller_profile_id=profile.id,
            price_cents=price_cents,
            status="open",
            idempotency_key=idempotency_key,
            expires_at=min(
                as_utc(report.expires_at),
                now + timedelta(hours=expires_in_hours),
            ),
            created_at=now,
        )
        db.add(offer)
        db.flush()
        audit(
            db,
            user.id,
            "intelligence.report_offered",
            "intelligence_report_offer",
            offer.id,
            request_id,
            {"report_id": report.id, "price_cents": price_cents},
        )
        return offer


def purchase_report_offer(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    offer_id: str,
    idempotency_key: str,
    request_id: str,
) -> IntelligenceReport:
    with _LOCK:
        existing_offer = db.scalar(
            select(IntelligenceReportOffer).where(
                IntelligenceReportOffer.buyer_profile_id == profile.id,
                IntelligenceReportOffer.purchase_idempotency_key == idempotency_key,
            )
        )
        if existing_offer is not None and existing_offer.purchased_report_id is not None:
            existing_report = db.get(IntelligenceReport, existing_offer.purchased_report_id)
            if existing_report is not None:
                return existing_report
        offer = db.scalar(
            select(IntelligenceReportOffer)
            .where(IntelligenceReportOffer.id == offer_id)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if offer is None or offer.world_id != profile.world_id:
            raise _error(404, "intelligence.offer_not_found", "Report offer not found")
        if offer.seller_profile_id == profile.id:
            raise _error(409, "intelligence.self_purchase", "Cannot buy your own report")
        if offer.status != "open" or as_utc(offer.expires_at) <= now:
            if offer.status == "open":
                offer.status = "expired"
            raise _error(409, "intelligence.offer_closed", "Report offer is no longer open")
        source = db.get(IntelligenceReport, offer.report_id)
        if source is None or as_utc(source.expires_at) <= now:
            offer.status = "expired"
            raise _error(409, "intelligence.report_expired", "The offered report has expired")
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            -cents_to_money(offer.price_cents),
            reason="intelligence_report_purchase",
            reference_type="intelligence_report_offer",
            reference_id=offer.id,
            idempotency_key=f"intel-buy:{idempotency_key}",
        )
        apply_profile_resource(
            db,
            offer.seller_profile_id,
            "cash",
            cents_to_money(offer.price_cents),
            reason="intelligence_report_sale",
            reference_type="intelligence_report_offer",
            reference_id=offer.id,
            idempotency_key=f"intel-sell:{idempotency_key}",
        )
        copied = IntelligenceReport(
            world_id=source.world_id,
            owner_profile_id=profile.id,
            target_type=source.target_type,
            target_id=source.target_id,
            information_type=source.information_type,
            category=source.category,
            statement=source.statement,
            confidence_bps=source.confidence_bps,
            accuracy_state=source.accuracy_state,
            source_category="player_report_market",
            snapshot_json=dict(source.snapshot_json),
            source_report_id=source.id,
            tradable=False,
            observed_at=source.observed_at,
            expires_at=source.expires_at,
            created_at=now,
        )
        db.add(copied)
        db.flush()
        offer.status = "sold"
        offer.buyer_profile_id = profile.id
        offer.purchased_report_id = copied.id
        offer.purchase_idempotency_key = idempotency_key
        offer.sold_at = now
        seller = db.get(PlayerProfile, offer.seller_profile_id)
        if seller is not None:
            create_notification(
                db,
                seller.user_id,
                "intelligence.report_sold",
                "Information report sold",
                "A report offer was completed.",
                {"offer_id": offer.id},
            )
        audit(
            db,
            user.id,
            "intelligence.report_purchased",
            "intelligence_report_offer",
            offer.id,
            request_id,
            {
                "source_report_id": source.id,
                "purchased_report_id": copied.id,
                "price_cents": offer.price_cents,
            },
        )
        return copied


def _validate_strategic_target(
    db: Session,
    profile: PlayerProfile,
    target: PlayerProfile,
    action_type: str,
    target_id: str,
) -> str:
    target_type = STRATEGIC_ACTION_TARGETS[action_type][0]
    if target_type == "profile":
        if target_id != target.id:
            raise _error(404, "strategic.target_not_found", "Target profile ID mismatch")
    elif target_type == "specialist":
        specialist = db.get(Specialist, target_id)
        if specialist is None or specialist.profile_id != target.id:
            raise _error(404, "strategic.target_not_found", "Target specialist not found")
    elif target_type == "company":
        company = db.get(Company, target_id)
        ownership = db.scalar(
            select(CompanyOwnership.id).where(
                CompanyOwnership.company_id == target_id,
                CompanyOwnership.owner_profile_id == target.id,
            )
        )
        if company is None or company.world_id != profile.world_id or ownership is None:
            raise _error(404, "strategic.target_not_found", "Target company not found")
    elif target_type == "cartel_project":
        project = db.get(CartelProject, target_id)
        membership = (
            db.scalar(
                select(OrganizationMembership.id).where(
                    OrganizationMembership.organization_id == project.organization_id,
                    OrganizationMembership.profile_id == target.id,
                    OrganizationMembership.status == "active",
                )
            )
            if project is not None
            else None
        )
        if (
            project is None
            or project.world_id != profile.world_id
            or project.status != "active"
            or membership is None
        ):
            raise _error(404, "strategic.target_not_found", "Active target project not found")
    return target_type


def launch_strategic_action(
    db: Session,
    *,
    user: User,
    profile: PlayerProfile,
    target_profile_id: str,
    specialist_id: str,
    action_type: str,
    target_id: str,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
) -> StrategicAction:
    with _LOCK:
        existing = db.scalar(
            select(StrategicAction).where(
                StrategicAction.actor_profile_id == profile.id,
                StrategicAction.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        now = datetime.now(UTC)
        _rate_limit(
            db,
            StrategicAction,
            profile.id,
            settings.strategic_action_rate_limit_per_minute,
            now,
        )
        target = _target_profile(db, profile, target_profile_id)
        target_type = _validate_strategic_target(db, profile, target, action_type, target_id)
        cooldown = db.scalar(
            select(StrategicAction.id).where(
                StrategicAction.actor_profile_id == profile.id,
                StrategicAction.target_profile_id == target.id,
                StrategicAction.action_type == action_type,
                StrategicAction.cooldown_until > now,
            )
        )
        if cooldown is not None:
            raise _error(409, "strategic.cooldown", "Strategic action is cooling down")
        specialist = _eligible_specialist(db, profile, specialist_id, now)
        action_id = uuid_str()
        effect_id = uuid_str()
        apply_profile_resource(
            db,
            profile.id,
            "cash",
            -cents_to_money(STRATEGIC_COST_CASH_CENTS),
            reason="strategic_action_reservation",
            reference_type="strategic_action",
            reference_id=action_id,
            idempotency_key=f"strategic-cash:{idempotency_key}",
        )
        apply_profile_resource(
            db,
            profile.id,
            "intelligence",
            -STRATEGIC_COST_INTELLIGENCE,
            reason="strategic_action_reservation",
            reference_type="strategic_action",
            reference_id=action_id,
            idempotency_key=f"strategic-points:{idempotency_key}",
        )
        protection = _active_protection(db, target, now)
        success_chance = max(
            500,
            min(
                9_000,
                4_800
                + (specialist.competence - 50) * 40
                + specialist.level * 100
                + _cartel_bonus(db, profile.id)
                - protection,
            ),
        )
        detection_chance = min(
            9_500,
            3_500 + protection // 2 + max(0, 50 - specialist.competence) * 30,
        )
        seed, success_roll, detection_roll, _ = _rolls(
            settings.seed_secret.get_secret_value(),
            action_id,
            idempotency_key,
        )
        outcome = _outcome(success_roll, success_chance)
        detected = detection_roll < detection_chance
        pressure_delta = 7 if detected else (3 if outcome == "failure" else 2)
        profile.investigation_pressure = min(100, profile.investigation_pressure + pressure_delta)
        specialist.energy = max(0, specialist.energy - 12)
        specialist.stress = min(100, specialist.stress + 8)
        configured_magnitude = STRATEGIC_ACTION_TARGETS[action_type][2]
        magnitude = (
            configured_magnitude
            if outcome == "success"
            else configured_magnitude // 2
            if outcome == "partial"
            else 0
        )
        effect_type = STRATEGIC_ACTION_TARGETS[action_type][1]
        action = StrategicAction(
            id=action_id,
            world_id=profile.world_id,
            actor_profile_id=profile.id,
            target_profile_id=target.id,
            specialist_id=specialist.id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            cost_cash_cents=STRATEGIC_COST_CASH_CENTS,
            cost_intelligence=STRATEGIC_COST_INTELLIGENCE,
            random_seed=seed,
            success_roll=success_roll,
            detection_roll=detection_roll,
            success_chance_bps=success_chance,
            detection_chance_bps=detection_chance,
            outcome=outcome,
            detected=detected,
            investigation_pressure_delta=pressure_delta,
            effect_id=effect_id if magnitude else None,
            idempotency_key=idempotency_key,
            cooldown_until=now + timedelta(minutes=settings.strategic_action_cooldown_minutes),
            created_at=now,
        )
        db.add(action)
        if magnitude:
            db.add(
                StrategicEffect(
                    id=effect_id,
                    world_id=profile.world_id,
                    action_id=action_id,
                    source_profile_id=profile.id,
                    target_profile_id=target.id,
                    effect_type=effect_type,
                    target_type=target_type,
                    target_id=target_id,
                    magnitude=magnitude,
                    starts_at=now,
                    ends_at=now + timedelta(minutes=settings.strategic_effect_minutes),
                    created_at=now,
                )
            )
        if detected:
            create_notification(
                db,
                target.user_id,
                "strategic.activity_detected",
                "Strategic pressure detected",
                "Your organization detected an abstract strategic action.",
                {"target_profile_id": target.id},
            )
        audit(
            db,
            user.id,
            "strategic.action_resolved",
            "strategic_action",
            action.id,
            request_id,
            {
                "target_profile_id": target.id,
                "target_type": target_type,
                "target_id": target_id,
                "outcome": outcome,
                "detected": detected,
                "success_roll": success_roll,
                "detection_roll": detection_roll,
            },
        )
        return action


def list_active_effects(db: Session, profile: PlayerProfile) -> list[StrategicEffect]:
    now = datetime.now(UTC)
    return list(
        db.scalars(
            select(StrategicEffect)
            .where(
                StrategicEffect.target_profile_id == profile.id,
                StrategicEffect.starts_at <= now,
                StrategicEffect.ends_at > now,
            )
            .order_by(StrategicEffect.ends_at)
        )
    )


def effective_project_deadline(db: Session, project: CartelProject) -> datetime:
    delay_seconds = _active_effect_magnitude(
        db,
        effect_type="project_delay",
        target_type="cartel_project",
        target_id=project.id,
        now=datetime.now(UTC),
    )
    return as_utc(project.ends_at) + timedelta(seconds=delay_seconds)


def active_company_cost_increase_bps(db: Session, company_id: str, now: datetime) -> int:
    return min(
        5_000,
        _active_effect_magnitude(
            db,
            effect_type="operating_cost_increase",
            target_type="company",
            target_id=company_id,
            now=now,
        ),
    )


def active_reputation_penalty(db: Session, profile_id: str, now: datetime) -> int:
    return min(
        50,
        _active_effect_magnitude(
            db,
            effect_type="reputation_penalty",
            target_type="profile",
            target_id=profile_id,
            now=now,
        )
        // 100,
    )
