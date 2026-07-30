from __future__ import annotations

from fastapi import APIRouter, Request, status
from sqlalchemy import func, select

from shadowgrid.bond_schemas import (
    BondConfigView,
    BondHoldingView,
    BondIssueView,
    BondSettlementView,
    BondSubscriptionView,
    CreateBondIssueRequest,
    SubscribeBondRequest,
)
from shadowgrid.bonds import (
    activate_bond_issue,
    create_bond_issue,
    list_bond_issues,
    list_bond_settlements,
    list_profile_bond_holdings,
    subscribe_bond,
)
from shadowgrid.config import get_settings
from shadowgrid.dependencies import CurrentProfile, Db, IdempotencyKey
from shadowgrid.models import BondHolding, BondIssue, Company

router = APIRouter()


def _issue_view(db: Db, issue: BondIssue) -> BondIssueView:
    company = db.get(Company, issue.issuer_company_id)
    return BondIssueView.model_validate(
        {
            **{
                field: getattr(issue, field)
                for field in BondIssueView.model_fields
                if field not in {"issuer_company_name", "holder_count"}
            },
            "issuer_company_name": company.name if company else "Archived company",
            "holder_count": int(
                db.scalar(
                    select(func.count())
                    .select_from(BondHolding)
                    .where(BondHolding.issue_id == issue.id, BondHolding.quantity > 0)
                )
                or 0
            ),
        }
    )


def _holding_view(db: Db, holding: BondHolding) -> BondHoldingView:
    issue = db.get(BondIssue, holding.issue_id)
    if issue is None:
        raise RuntimeError("bond holding issue is missing")
    company = db.get(Company, issue.issuer_company_id)
    return BondHoldingView.model_validate(
        {
            **{
                field: getattr(holding, field)
                for field in BondHoldingView.model_fields
                if field
                not in {
                    "symbol",
                    "title",
                    "issuer_company_name",
                    "face_value_cents",
                    "coupon_rate_bps",
                    "issue_status",
                }
            },
            "symbol": issue.symbol,
            "title": issue.title,
            "issuer_company_name": company.name if company else "Archived company",
            "face_value_cents": issue.face_value_cents,
            "coupon_rate_bps": issue.coupon_rate_bps,
            "issue_status": issue.status,
        }
    )


@router.get("/bonds/config", response_model=BondConfigView, tags=["bonds"])
def bond_config(_: CurrentProfile) -> BondConfigView:
    settings = get_settings()
    return BondConfigView(
        coupon_interval_minutes=settings.bond_coupon_interval_minutes,
        offering_minutes=settings.bond_offering_minutes,
        max_principal_cents=settings.bond_max_principal_cents,
        max_term_periods=settings.bond_max_term_periods,
        default_reputation_penalty_bps=(settings.bond_default_reputation_penalty_bps),
        default_investigation_penalty_bps=(settings.bond_default_investigation_penalty_bps),
    )


@router.get("/bonds/issues", response_model=list[BondIssueView], tags=["bonds"])
def bond_issues(db: Db, profile: CurrentProfile) -> list[BondIssueView]:
    return [_issue_view(db, issue) for issue in list_bond_issues(db, profile)]


@router.post(
    "/bonds/issues",
    response_model=BondIssueView,
    status_code=status.HTTP_201_CREATED,
    tags=["bonds"],
)
def post_bond_issue(
    payload: CreateBondIssueRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> BondIssueView:
    issue = create_bond_issue(
        db,
        profile,
        **payload.model_dump(),
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
        settings=get_settings(),
    )
    return _issue_view(db, issue)


@router.post(
    "/bonds/issues/{issue_id}/subscribe",
    response_model=BondSubscriptionView,
    status_code=status.HTTP_201_CREATED,
    tags=["bonds"],
)
def post_bond_subscription(
    issue_id: str,
    payload: SubscribeBondRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> BondSubscriptionView:
    return BondSubscriptionView.model_validate(
        subscribe_bond(
            db,
            profile,
            issue_id=issue_id,
            quantity=payload.quantity,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
            settings=get_settings(),
        )
    )


@router.post(
    "/bonds/issues/{issue_id}/activate",
    response_model=BondIssueView,
    tags=["bonds"],
)
def post_activate_bond_issue(
    issue_id: str,
    request: Request,
    db: Db,
    profile: CurrentProfile,
) -> BondIssueView:
    return _issue_view(
        db,
        activate_bond_issue(
            db,
            profile,
            issue_id=issue_id,
            request_id=request.state.request_id,
            settings=get_settings(),
        ),
    )


@router.get(
    "/bonds/holdings/me",
    response_model=list[BondHoldingView],
    tags=["bonds"],
)
def my_bond_holdings(
    db: Db,
    profile: CurrentProfile,
) -> list[BondHoldingView]:
    return [_holding_view(db, holding) for holding in list_profile_bond_holdings(db, profile)]


@router.get(
    "/bonds/issues/{issue_id}/settlements",
    response_model=list[BondSettlementView],
    tags=["bonds"],
)
def bond_settlements(
    issue_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[BondSettlementView]:
    return [
        BondSettlementView.model_validate(settlement)
        for settlement in list_bond_settlements(db, profile, issue_id)
    ]
