from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import or_, select

from shadowgrid.dependencies import (
    AppSettings,
    CurrentProfile,
    CurrentUser,
    Db,
    IdempotencyKey,
    request_id,
    require_admin,
)
from shadowgrid.domain import safe_commit
from shadowgrid.intelligence import (
    create_report_offer,
    launch_intelligence_operation,
    launch_strategic_action,
    list_active_effects,
    purchase_report_offer,
    report_for_owner,
)
from shadowgrid.intelligence_schemas import (
    IntelligenceAdminOperationView,
    IntelligenceOfferRequest,
    IntelligenceOfferView,
    IntelligenceOperationRequest,
    IntelligenceOperationView,
    IntelligenceReportAdminView,
    IntelligenceReportView,
    StrategicActionRequest,
    StrategicActionView,
    StrategicEffectView,
)
from shadowgrid.models import (
    IntelligenceOperation,
    IntelligenceReport,
    IntelligenceReportOffer,
    StrategicAction,
    User,
    as_utc,
)

router = APIRouter()
AdminUser = Annotated[User, Depends(require_admin)]


def _report_view(report: IntelligenceReport) -> IntelligenceReportView:
    now = datetime.now(UTC)
    observed_at = as_utc(report.observed_at)
    return IntelligenceReportView(
        id=report.id,
        owner_profile_id=report.owner_profile_id,
        target_type=report.target_type,
        target_id=report.target_id,
        information_type=report.information_type,
        category=report.category,
        statement=report.statement,
        confidence_bps=report.confidence_bps,
        source_category=report.source_category,
        source_report_id=report.source_report_id,
        tradable=report.tradable,
        observed_at=report.observed_at,
        expires_at=report.expires_at,
        created_at=report.created_at,
        is_expired=as_utc(report.expires_at) <= now,
        age_seconds=max(0, int((now - observed_at).total_seconds())),
    )


def _offer_view(db: Db, offer: IntelligenceReportOffer) -> IntelligenceOfferView:
    report = db.get(IntelligenceReport, offer.report_id)
    return IntelligenceOfferView(
        id=offer.id,
        report_id=offer.report_id,
        seller_profile_id=offer.seller_profile_id,
        buyer_profile_id=offer.buyer_profile_id,
        purchased_report_id=offer.purchased_report_id,
        price_cents=offer.price_cents,
        status=offer.status,
        expires_at=offer.expires_at,
        sold_at=offer.sold_at,
        created_at=offer.created_at,
        category=report.category if report is not None else "",
        target_type=report.target_type if report is not None else "",
        target_id=report.target_id if report is not None else "",
        confidence_bps=report.confidence_bps if report is not None else 0,
    )


@router.post(
    "/intelligence/operations",
    response_model=IntelligenceOperationView,
    status_code=status.HTTP_201_CREATED,
    tags=["intelligence"],
)
def intelligence_operation_create(
    payload: IntelligenceOperationRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> IntelligenceOperation:
    operation = launch_intelligence_operation(
        db,
        user=user,
        profile=profile,
        target_profile_id=payload.target_profile_id,
        specialist_id=payload.specialist_id,
        information_type=payload.information_type,
        category=payload.category,
        idempotency_key=key,
        request_id=request_id(request),
        settings=settings,
    )
    safe_commit(db)
    return operation


@router.get(
    "/intelligence/operations",
    response_model=list[IntelligenceOperationView],
    tags=["intelligence"],
)
def intelligence_operation_list(db: Db, profile: CurrentProfile) -> list[IntelligenceOperation]:
    return list(
        db.scalars(
            select(IntelligenceOperation)
            .where(IntelligenceOperation.actor_profile_id == profile.id)
            .order_by(IntelligenceOperation.created_at.desc())
            .limit(100)
        )
    )


@router.get(
    "/intelligence/reports",
    response_model=list[IntelligenceReportView],
    tags=["intelligence"],
)
def intelligence_report_list(db: Db, profile: CurrentProfile) -> list[IntelligenceReportView]:
    reports = db.scalars(
        select(IntelligenceReport)
        .where(IntelligenceReport.owner_profile_id == profile.id)
        .order_by(IntelligenceReport.created_at.desc())
        .limit(200)
    )
    return [_report_view(report) for report in reports]


@router.get(
    "/intelligence/reports/{report_id}",
    response_model=IntelligenceReportView,
    tags=["intelligence"],
)
def intelligence_report_get(
    report_id: str, db: Db, profile: CurrentProfile
) -> IntelligenceReportView:
    return _report_view(report_for_owner(db, profile, report_id))


@router.post(
    "/intelligence/reports/{report_id}/sell",
    response_model=IntelligenceOfferView,
    status_code=status.HTTP_201_CREATED,
    tags=["intelligence"],
)
def intelligence_report_sell(
    report_id: str,
    payload: IntelligenceOfferRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> IntelligenceOfferView:
    offer = create_report_offer(
        db,
        user=user,
        profile=profile,
        report_id=report_id,
        price_cents=payload.price_cents,
        expires_in_hours=payload.expires_in_hours,
        idempotency_key=key,
        request_id=request_id(request),
    )
    safe_commit(db)
    return _offer_view(db, offer)


@router.get(
    "/intelligence/offers",
    response_model=list[IntelligenceOfferView],
    tags=["intelligence"],
)
def intelligence_offer_list(db: Db, profile: CurrentProfile) -> list[IntelligenceOfferView]:
    now = datetime.now(UTC)
    offers = list(
        db.scalars(
            select(IntelligenceReportOffer)
            .where(
                IntelligenceReportOffer.world_id == profile.world_id,
                or_(
                    IntelligenceReportOffer.status != "open",
                    IntelligenceReportOffer.expires_at > now,
                ),
            )
            .order_by(IntelligenceReportOffer.created_at.desc())
            .limit(200)
        )
    )
    return [_offer_view(db, offer) for offer in offers]


@router.post(
    "/intelligence/offers/{offer_id}/buy",
    response_model=IntelligenceReportView,
    tags=["intelligence"],
)
def intelligence_offer_buy(
    offer_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> IntelligenceReportView:
    report = purchase_report_offer(
        db,
        user=user,
        profile=profile,
        offer_id=offer_id,
        idempotency_key=key,
        request_id=request_id(request),
    )
    safe_commit(db)
    return _report_view(report)


@router.post(
    "/strategic-actions",
    response_model=StrategicActionView,
    status_code=status.HTTP_201_CREATED,
    tags=["strategic-actions"],
)
def strategic_action_create(
    payload: StrategicActionRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> StrategicAction:
    action = launch_strategic_action(
        db,
        user=user,
        profile=profile,
        target_profile_id=payload.target_profile_id,
        specialist_id=payload.specialist_id,
        action_type=payload.action_type,
        target_id=payload.target_id,
        idempotency_key=key,
        request_id=request_id(request),
        settings=settings,
    )
    safe_commit(db)
    return action


@router.get(
    "/strategic-actions/me",
    response_model=list[StrategicActionView],
    tags=["strategic-actions"],
)
def strategic_action_list(db: Db, profile: CurrentProfile) -> list[StrategicAction]:
    return list(
        db.scalars(
            select(StrategicAction)
            .where(StrategicAction.actor_profile_id == profile.id)
            .order_by(StrategicAction.created_at.desc())
            .limit(100)
        )
    )


@router.get(
    "/strategic-actions/effects/me",
    response_model=list[StrategicEffectView],
    tags=["strategic-actions"],
)
def strategic_effect_list(db: Db, profile: CurrentProfile) -> list[StrategicEffectView]:
    return [StrategicEffectView.model_validate(item) for item in list_active_effects(db, profile)]


@router.get(
    "/admin/intelligence/operations",
    response_model=list[IntelligenceAdminOperationView],
    tags=["admin", "intelligence"],
)
def intelligence_admin_trace(
    db: Db,
    _: AdminUser,
) -> list[IntelligenceAdminOperationView]:
    intelligence_operations = db.scalars(
        select(IntelligenceOperation).order_by(IntelligenceOperation.created_at.desc()).limit(100)
    )
    strategic_actions = db.scalars(
        select(StrategicAction).order_by(StrategicAction.created_at.desc()).limit(100)
    )
    items = [
        IntelligenceAdminOperationView(
            kind="intelligence",
            id=item.id,
            actor_profile_id=item.actor_profile_id,
            target_profile_id=item.target_profile_id,
            action_type=item.information_type,
            outcome=item.outcome,
            detected=item.detected,
            success_roll=item.success_roll,
            detection_roll=item.detection_roll,
            random_seed=item.random_seed,
            created_at=item.created_at,
        )
        for item in intelligence_operations
    ]
    items.extend(
        IntelligenceAdminOperationView(
            kind="strategic",
            id=item.id,
            actor_profile_id=item.actor_profile_id,
            target_profile_id=item.target_profile_id,
            action_type=item.action_type,
            outcome=item.outcome,
            detected=item.detected,
            success_roll=item.success_roll,
            detection_roll=item.detection_roll,
            random_seed=item.random_seed,
            created_at=item.created_at,
        )
        for item in strategic_actions
    )
    return sorted(items, key=lambda item: item.created_at, reverse=True)[:200]


@router.get(
    "/admin/intelligence/reports/{report_id}",
    response_model=IntelligenceReportAdminView,
    tags=["admin", "intelligence"],
)
def intelligence_admin_report(
    report_id: str,
    db: Db,
    _: AdminUser,
) -> IntelligenceReportAdminView:
    report = db.get(IntelligenceReport, report_id)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "intelligence.report_not_found", "message": "Report not found"},
        )
    view = _report_view(report)
    return IntelligenceReportAdminView(
        **view.model_dump(),
        accuracy_state=report.accuracy_state,
        snapshot_json=report.snapshot_json,
        operation_id=report.operation_id,
    )
