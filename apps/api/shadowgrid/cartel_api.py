from __future__ import annotations

from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import func, select

from shadowgrid.cartel_schemas import (
    CartelActivityView,
    CartelExpenseRequest,
    CartelExpenseView,
    CartelInvitationRequest,
    CartelInvitationView,
    CartelMemberView,
    CartelProjectContributionRequest,
    CartelProjectView,
    CartelRankingView,
    CartelTreasuryView,
    CartelView,
    CreateCartelProjectRequest,
    CreateCartelRequest,
    DistrictCartelInfluenceView,
    JoinCartelRequest,
    LeadershipTransferRequest,
    TreasuryDepositRequest,
    UpdateCartelRoleRequest,
)
from shadowgrid.cartels import (
    active_membership,
    approve_expense,
    cartel_activity,
    cartel_permissions,
    cartel_rankings,
    contribute_to_project,
    create_cartel,
    create_invitation,
    create_project,
    deposit_treasury,
    dissolve_cartel,
    district_influence,
    ensure_cartel_account,
    join_cartel,
    leave_cartel,
    list_invitations,
    request_expense,
    transfer_leadership,
    update_member_role,
)
from shadowgrid.dependencies import (
    AppSettings,
    CurrentProfile,
    CurrentUser,
    Db,
    IdempotencyKey,
    request_id,
)
from shadowgrid.models import (
    Account,
    CartelExpense,
    CartelProject,
    Organization,
    OrganizationMembership,
    PlayerProfile,
)
from shadowgrid.schemas import MessageResponse

router = APIRouter()


def _view_cartel(db: Db, cartel: Organization, profile_id: str) -> CartelView:
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == cartel.id,
            OrganizationMembership.profile_id == profile_id,
            OrganizationMembership.status == "active",
        )
    )
    member_count = int(
        db.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == cartel.id,
                OrganizationMembership.status == "active",
            )
        )
        or 0
    )
    account = db.scalar(
        select(Account).where(
            Account.world_id == cartel.world_id,
            Account.owner_type == "organization",
            Account.owner_id == cartel.id,
            Account.currency == "EUR",
        )
    )
    legacy_balance = int((Decimal(cartel.treasury_cash) * Decimal(100)).to_integral_value())
    role = membership.role if membership is not None else None
    return CartelView.model_validate(cartel).model_copy(
        update={
            "member_count": member_count,
            "treasury_balance_cents": account.balance_cents if account else legacy_balance,
            "my_role": role,
            "my_permissions": cartel_permissions(role),
        }
    )


def _project_view(project: CartelProject) -> CartelProjectView:
    requirements = (
        (project.contributed_cash_cents, project.required_cash_cents),
        (project.contributed_influence, project.required_influence),
        (project.contributed_intelligence, project.required_intelligence),
    )
    progress_parts = [
        min(10_000, contributed * 10_000 // required)
        for contributed, required in requirements
        if required > 0
    ]
    progress_bps = sum(progress_parts) // len(progress_parts) if progress_parts else 10_000
    return CartelProjectView.model_validate(project).model_copy(
        update={"progress_bps": progress_bps}
    )


def _active_cartel(db: Db, cartel_id: str, world_id: str) -> Organization:
    cartel = db.scalar(
        select(Organization).where(
            Organization.id == cartel_id,
            Organization.world_id == world_id,
            Organization.status == "active",
        )
    )
    if cartel is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "cartel.not_found", "message": "Active cartel not found"},
        )
    return cartel


@router.get("/cartels", response_model=list[CartelView], tags=["cartels"])
def cartels_list(db: Db, profile: CurrentProfile) -> list[CartelView]:
    return [
        _view_cartel(db, cartel, profile.id)
        for cartel in db.scalars(
            select(Organization)
            .where(
                Organization.world_id == profile.world_id,
                Organization.status == "active",
            )
            .order_by(Organization.name)
        )
    ]


@router.post("/cartels", response_model=CartelView, status_code=201, tags=["cartels"])
def cartels_create(
    payload: CreateCartelRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> CartelView:
    cartel = create_cartel(
        db,
        user=user,
        profile=profile,
        name=payload.name,
        tag=payload.tag,
        archetype=payload.archetype,
        description=payload.description,
        governance_model=payload.governance_model,
        idempotency_key=key,
        request_id=request_id(request),
        settings=settings,
    )
    return _view_cartel(db, cartel, profile.id)


@router.get("/cartels/invitations/me", response_model=list[CartelInvitationView], tags=["cartels"])
def cartel_invitations_me(
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> list[CartelInvitationView]:
    result: list[CartelInvitationView] = []
    for invitation in list_invitations(db, user, profile):
        cartel = db.get(Organization, invitation.organization_id)
        result.append(
            CartelInvitationView.model_validate(invitation).model_copy(
                update={
                    "cartel_name": cartel.name if cartel else "",
                    "cartel_tag": cartel.tag if cartel else "",
                }
            )
        )
    return result


@router.get("/cartels/{cartel_id}", response_model=CartelView, tags=["cartels"])
def cartel_get(cartel_id: str, db: Db, profile: CurrentProfile) -> CartelView:
    return _view_cartel(db, _active_cartel(db, cartel_id, profile.world_id), profile.id)


@router.get(
    "/cartels/{cartel_id}/members",
    response_model=list[CartelMemberView],
    tags=["cartels"],
)
def cartel_members(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[CartelMemberView]:
    _active_cartel(db, cartel_id, profile.world_id)
    active_membership(db, profile.id, cartel_id)
    rows = db.execute(
        select(OrganizationMembership, PlayerProfile)
        .join(PlayerProfile, PlayerProfile.id == OrganizationMembership.profile_id)
        .where(OrganizationMembership.organization_id == cartel_id)
        .order_by(OrganizationMembership.joined_at)
    ).all()
    return [
        CartelMemberView(
            profile_id=membership.profile_id,
            codename=member_profile.codename,
            role=membership.role,
            status=membership.status,
            joined_at=membership.joined_at,
        )
        for membership, member_profile in rows
    ]


@router.post(
    "/cartels/{cartel_id}/invitations",
    response_model=CartelInvitationView,
    status_code=201,
    tags=["cartels"],
)
def cartel_invitation_create(
    cartel_id: str,
    payload: CartelInvitationRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> CartelInvitationView:
    invitation = create_invitation(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        email=str(payload.email),
        idempotency_key=key,
        request_id=request_id(request),
    )
    cartel = db.get(Organization, cartel_id)
    return CartelInvitationView.model_validate(invitation).model_copy(
        update={
            "cartel_name": cartel.name if cartel else "",
            "cartel_tag": cartel.tag if cartel else "",
        }
    )


@router.post(
    "/cartels/{cartel_id}/join",
    response_model=CartelView,
    tags=["cartels"],
)
def cartel_join(
    cartel_id: str,
    payload: JoinCartelRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> CartelView:
    join_cartel(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        invitation_id=payload.invitation_id,
        idempotency_key=key,
        request_id=request_id(request),
    )
    return _view_cartel(db, _active_cartel(db, cartel_id, profile.world_id), profile.id)


@router.post(
    "/cartels/{cartel_id}/leave",
    response_model=MessageResponse,
    tags=["cartels"],
)
def cartel_leave(
    cartel_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> MessageResponse:
    leave_cartel(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        idempotency_key=key,
        request_id=request_id(request),
    )
    return MessageResponse(message="Cartel left.")


@router.patch(
    "/cartels/{cartel_id}/members/{player_id}",
    response_model=CartelMemberView,
    tags=["cartels"],
)
def cartel_member_update(
    cartel_id: str,
    player_id: str,
    payload: UpdateCartelRoleRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> CartelMemberView:
    membership = update_member_role(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        target_profile_id=player_id,
        role=payload.role,
        idempotency_key=key,
        request_id=request_id(request),
    )
    member_profile = db.get(PlayerProfile, membership.profile_id)
    if member_profile is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "profile.missing", "message": "Member profile is missing"},
        )
    return CartelMemberView(
        profile_id=membership.profile_id,
        codename=member_profile.codename,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
    )


@router.post(
    "/cartels/{cartel_id}/leadership-transfer",
    response_model=MessageResponse,
    tags=["cartels"],
)
def cartel_leadership_transfer(
    cartel_id: str,
    payload: LeadershipTransferRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> MessageResponse:
    transfer_leadership(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        target_profile_id=payload.target_profile_id,
        idempotency_key=key,
        request_id=request_id(request),
    )
    return MessageResponse(message="Leadership transferred.")


@router.get(
    "/cartels/{cartel_id}/treasury",
    response_model=CartelTreasuryView,
    tags=["cartels"],
)
def cartel_treasury(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> CartelTreasuryView:
    cartel = _active_cartel(db, cartel_id, profile.world_id)
    active_membership(db, profile.id, cartel.id)
    account = ensure_cartel_account(db, cartel)
    return CartelTreasuryView(
        cartel_id=cartel.id,
        balance_cents=account.balance_cents,
        reserved_cents=account.reserved_cents,
        approval_threshold_cents=cartel.approval_threshold_cents,
        single_spend_limit_cents=cartel.single_spend_limit_cents,
    )


@router.post(
    "/cartels/{cartel_id}/treasury/deposit",
    response_model=CartelTreasuryView,
    tags=["cartels"],
)
def cartel_treasury_deposit(
    cartel_id: str,
    payload: TreasuryDepositRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> CartelTreasuryView:
    account = deposit_treasury(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        amount_cents=payload.amount_cents,
        idempotency_key=key,
        request_id=request_id(request),
    )
    cartel = _active_cartel(db, cartel_id, profile.world_id)
    return CartelTreasuryView(
        cartel_id=cartel.id,
        balance_cents=account.balance_cents,
        reserved_cents=account.reserved_cents,
        approval_threshold_cents=cartel.approval_threshold_cents,
        single_spend_limit_cents=cartel.single_spend_limit_cents,
    )


@router.get(
    "/cartels/{cartel_id}/treasury/expenses",
    response_model=list[CartelExpenseView],
    tags=["cartels"],
)
def cartel_expenses(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[CartelExpense]:
    _active_cartel(db, cartel_id, profile.world_id)
    active_membership(db, profile.id, cartel_id)
    return list(
        db.scalars(
            select(CartelExpense)
            .where(CartelExpense.organization_id == cartel_id)
            .order_by(CartelExpense.created_at.desc())
        )
    )


@router.post(
    "/cartels/{cartel_id}/treasury/expenses",
    response_model=CartelExpenseView,
    status_code=201,
    tags=["cartels"],
)
def cartel_expense_create(
    cartel_id: str,
    payload: CartelExpenseRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> CartelExpense:
    return request_expense(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        amount_cents=payload.amount_cents,
        purpose=payload.purpose,
        idempotency_key=key,
        request_id=request_id(request),
    )


@router.post(
    "/cartels/{cartel_id}/treasury/expenses/{expense_id}/approve",
    response_model=CartelExpenseView,
    tags=["cartels"],
)
def cartel_expense_approve(
    cartel_id: str,
    expense_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    _: IdempotencyKey,
) -> CartelExpense:
    return approve_expense(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        expense_id=expense_id,
        request_id=request_id(request),
    )


@router.get(
    "/cartels/{cartel_id}/projects",
    response_model=list[CartelProjectView],
    tags=["cartels"],
)
def cartel_projects(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[CartelProjectView]:
    _active_cartel(db, cartel_id, profile.world_id)
    active_membership(db, profile.id, cartel_id)
    return [
        _project_view(project)
        for project in db.scalars(
            select(CartelProject)
            .where(CartelProject.organization_id == cartel_id)
            .order_by(CartelProject.created_at.desc())
        )
    ]


@router.post(
    "/cartels/{cartel_id}/projects",
    response_model=CartelProjectView,
    status_code=201,
    tags=["cartels"],
)
def cartel_project_create(
    cartel_id: str,
    payload: CreateCartelProjectRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> CartelProjectView:
    return _project_view(
        create_project(
            db,
            user=user,
            profile=profile,
            cartel_id=cartel_id,
            district_id=payload.district_id,
            project_type=payload.project_type,
            idempotency_key=key,
            request_id=request_id(request),
        )
    )


@router.post(
    "/cartels/{cartel_id}/projects/{project_id}/contribute",
    response_model=CartelProjectView,
    tags=["cartels"],
)
def cartel_project_contribute(
    cartel_id: str,
    project_id: str,
    payload: CartelProjectContributionRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> CartelProjectView:
    return _project_view(
        contribute_to_project(
            db,
            user=user,
            profile=profile,
            cartel_id=cartel_id,
            project_id=project_id,
            resource_type=payload.resource_type,
            amount_units=payload.amount_units,
            idempotency_key=key,
            request_id=request_id(request),
            settings=settings,
        )
    )


@router.get(
    "/influence/cities/{city_id}",
    response_model=list[DistrictCartelInfluenceView],
    tags=["influence"],
)
def cartel_city_influence(
    city_id: str,
    db: Db,
    profile: CurrentProfile,
    settings: AppSettings,
) -> list[dict[str, Any]]:
    return district_influence(
        db,
        world_id=profile.world_id,
        city_id=city_id,
        settings=settings,
    )


@router.get(
    "/leaderboards/cartels/current",
    response_model=list[CartelRankingView],
    tags=["leaderboards"],
)
def cartel_leaderboard(db: Db, profile: CurrentProfile) -> list[dict[str, Any]]:
    return cartel_rankings(db, profile.world_id)


@router.get(
    "/cartels/{cartel_id}/activity",
    response_model=list[CartelActivityView],
    tags=["cartels"],
)
def cartel_activity_log(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[CartelActivityView]:
    return [
        CartelActivityView.model_validate(item)
        for item in cartel_activity(db, cartel_id, profile.id)
    ]


@router.delete(
    "/cartels/{cartel_id}",
    response_model=MessageResponse,
    tags=["cartels"],
)
def cartel_dissolve(
    cartel_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> MessageResponse:
    dissolve_cartel(
        db,
        user=user,
        profile=profile,
        cartel_id=cartel_id,
        idempotency_key=key,
        request_id=request_id(request),
    )
    return MessageResponse(message="Cartel dissolved.")
