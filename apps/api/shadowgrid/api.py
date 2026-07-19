from __future__ import annotations

import hashlib
import secrets
import threading
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

import pyotp
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings, get_settings
from shadowgrid.dependencies import (
    AppSettings,
    CurrentProfile,
    CurrentUser,
    Db,
    IdempotencyKey,
    request_id,
    require_admin,
)
from shadowgrid.domain import (
    apply_profile_resource,
    audit,
    build_facility,
    buy_business,
    create_player_profile,
    get_idempotent,
    membership_with_permission,
    recruit_specialist,
    remember_idempotent,
    resolve_operation,
    safe_commit,
    start_operation,
    start_research,
)
from shadowgrid.game_config import (
    ARCHETYPES,
    BUSINESS_TYPES,
    FACILITY_TYPES,
    OPERATION_TYPES,
    RESEARCH,
)
from shadowgrid.mailer import deliver_email, queue_email
from shadowgrid.models import (
    AuditLog,
    Business,
    District,
    DistrictInfluence,
    EmailOutbox,
    Evidence,
    Facility,
    IntelReport,
    LedgerEntry,
    Notification,
    OneTimeToken,
    Operation,
    Organization,
    OrganizationInvite,
    OrganizationMembership,
    PlayerProfile,
    RefreshSession,
    ResearchProject,
    Specialist,
    Treaty,
    User,
    World,
    WorldEvent,
    as_utc,
)
from shadowgrid.schemas import (
    BusinessView,
    BuyBusinessRequest,
    CreateOrganizationRequest,
    CreateTreatyRequest,
    DistrictView,
    FacilityRequest,
    FacilityView,
    HealthResponse,
    IntelReportView,
    InviteRequest,
    JoinWorldRequest,
    LoginRequest,
    MessageResponse,
    NetworkEdge,
    NetworkNode,
    NetworkView,
    OperationView,
    OrganizationMemberView,
    OrganizationView,
    PasswordForgotRequest,
    PasswordResetRequest,
    ProfileView,
    RecruitSpecialistRequest,
    RefreshRequest,
    RegisterRequest,
    ResearchView,
    SessionView,
    SpecialistView,
    StartOperationRequest,
    StartResearchRequest,
    TokenPair,
    TreasuryRequest,
    TreatyView,
    TutorialRequest,
    UpdateOrganizationRoleRequest,
    UserView,
    VerifyEmailRequest,
    WorldView,
)
from shadowgrid.security import (
    create_access_token,
    create_refresh_session,
    hash_password,
    hash_token,
    rotate_refresh_session,
    verify_password,
    verify_totp,
)

router = APIRouter()
_login_attempts: dict[str, list[datetime]] = {}
_operation_resolution_lock = threading.Lock()


def _cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        "shadowgrid_refresh",
        token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.app_env == "production",
        samesite="lax",
        path=f"{settings.api_prefix}/auth",
    )


def _issue_one_time_token(db: Session, user: User, purpose: str, settings: Settings) -> str:
    raw = secrets.token_urlsafe(36)
    db.add(
        OneTimeToken(
            user_id=user.id,
            purpose=purpose,
            token_hash=hash_token(raw, settings.refresh_pepper.get_secret_value()),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    return raw


def _consume_one_time_token(db: Session, raw: str, purpose: str, settings: Settings) -> User:
    digest = hash_token(raw, settings.refresh_pepper.get_secret_value())
    item = db.scalar(
        select(OneTimeToken)
        .where(OneTimeToken.token_hash == digest, OneTimeToken.purpose == purpose)
        .with_for_update()
    )
    now = datetime.now(UTC)
    if item is None or item.consumed_at is not None or as_utc(item.expires_at) <= now:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "auth.invalid_one_time_token",
                "message": "Token is invalid or expired",
            },
        )
    user = db.get(User, item.user_id)
    if user is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "auth.invalid_one_time_token",
                "message": "Token is invalid or expired",
            },
        )
    item.consumed_at = now
    return user


def _email_attempt_key(email: str) -> str:
    return hashlib.sha256(email.lower().encode()).hexdigest()


def _check_login_limit(email: str) -> None:
    now = datetime.now(UTC)
    key = _email_attempt_key(email)
    recent = [item for item in _login_attempts.get(key, []) if item > now - timedelta(minutes=10)]
    if len(recent) >= 8:
        raise HTTPException(
            status_code=429,
            detail={"code": "auth.rate_limited", "message": "Too many login attempts; retry later"},
        )
    recent.append(now)
    _login_attempts[key] = recent


@router.get("/health", response_model=HealthResponse, tags=["operations"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", version="0.1.0", server_time=datetime.now(UTC))


@router.get("/ready", response_model=HealthResponse, tags=["operations"])
def readiness(db: Db) -> HealthResponse:
    db.execute(select(1))
    return HealthResponse(status="ready", version="0.1.0", server_time=datetime.now(UTC))


@router.post("/auth/register", response_model=MessageResponse, status_code=201, tags=["auth"])
def register(
    payload: RegisterRequest, request: Request, db: Db, settings: AppSettings
) -> MessageResponse:
    email = payload.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        return MessageResponse(
            message="If the address can be registered, a verification email will arrive shortly."
        )
    user = User(
        email=email,
        display_name=payload.display_name,
        password_hash=hash_password(payload.password),
        locale=payload.locale,
    )
    db.add(user)
    db.flush()
    raw = _issue_one_time_token(db, user, "verify_email", settings)
    body = f"Welcome to SHADOWGRID. Verify your local account:\nhttp://localhost:5173/verify-email?token={raw}\n\nThis fictional game never requests real-world operational information."
    message = queue_email(db, user.email, "Verify your SHADOWGRID account", body)
    audit(db, user.id, "auth.register", "user", user.id, request_id(request))
    db.commit()
    deliver_email(db, message, settings)
    db.commit()
    return MessageResponse(
        message="If the address can be registered, a verification email will arrive shortly."
    )


@router.post("/auth/verify-email", response_model=MessageResponse, tags=["auth"])
def verify_email(payload: VerifyEmailRequest, db: Db, settings: AppSettings) -> MessageResponse:
    user = _consume_one_time_token(db, payload.token, "verify_email", settings)
    user.email_verified = True
    db.commit()
    return MessageResponse(message="Email verified.")


@router.post("/auth/login", response_model=TokenPair, tags=["auth"])
def login(
    payload: LoginRequest, request: Request, response: Response, db: Db, settings: AppSettings
) -> TokenPair:
    _check_login_limit(payload.email)
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    valid = user is not None and verify_password(payload.password, user.password_hash)
    if not valid or user is None or not verify_totp(user, payload.totp_code):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "auth.invalid_credentials",
                "message": "Email, password or verification code is invalid",
            },
        )
    if not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "auth.email_unverified",
                "message": "Verify the email address before signing in",
            },
        )
    if user.disabled_at:
        raise HTTPException(
            status_code=403,
            detail={"code": "auth.account_disabled", "message": "Account is disabled"},
        )
    _login_attempts.pop(_email_attempt_key(payload.email), None)
    refresh_session, raw = create_refresh_session(
        db, user, settings, request.headers.get("user-agent", "unknown")
    )
    access, expires = create_access_token(user, refresh_session.id, settings)
    audit(db, user.id, "auth.login", "session", refresh_session.id, request_id(request))
    db.commit()
    _cookie(response, raw, settings)
    return TokenPair(
        access_token=access,
        refresh_token=raw if request.headers.get("x-client-kind") == "mobile" else None,
        expires_in=expires,
    )


@router.post("/auth/refresh", response_model=TokenPair, tags=["auth"])
def refresh(
    payload: RefreshRequest,
    request: Request,
    response: Response,
    db: Db,
    settings: AppSettings,
    shadowgrid_refresh: Annotated[str | None, Cookie()] = None,
) -> TokenPair:
    raw = payload.refresh_token or shadowgrid_refresh
    if not raw:
        raise HTTPException(
            status_code=401,
            detail={"code": "auth.refresh_required", "message": "Refresh token required"},
        )
    rotated = rotate_refresh_session(
        db, raw, settings, request.headers.get("user-agent", "unknown")
    )
    if rotated is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "auth.invalid_refresh",
                "message": "Refresh token is invalid or was reused",
            },
        )
    user, refresh_session, new_raw = rotated
    access, expires = create_access_token(user, refresh_session.id, settings)
    _cookie(response, new_raw, settings)
    return TokenPair(
        access_token=access,
        refresh_token=new_raw if payload.refresh_token else None,
        expires_in=expires,
    )


@router.post("/auth/logout", response_model=MessageResponse, tags=["auth"])
def logout(response: Response, db: Db, user: CurrentUser, request: Request) -> MessageResponse:
    credentials = request.headers.get("authorization", "").removeprefix("Bearer ")
    from shadowgrid.security import decode_access_token

    payload = decode_access_token(credentials, get_settings())
    session = db.get(RefreshSession, payload["sid"])
    if session:
        session.revoked_at = datetime.now(UTC)
    db.commit()
    response.delete_cookie("shadowgrid_refresh", path=f"{get_settings().api_prefix}/auth")
    return MessageResponse(message="Signed out.")


@router.post("/auth/password/forgot", response_model=MessageResponse, tags=["auth"])
def forgot_password(
    payload: PasswordForgotRequest, db: Db, settings: AppSettings
) -> MessageResponse:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user:
        raw = _issue_one_time_token(db, user, "password_reset", settings)
        message = queue_email(
            db,
            user.email,
            "Reset your SHADOWGRID password",
            f"Reset your local password:\nhttp://localhost:5173/reset-password?token={raw}",
        )
        db.commit()
        deliver_email(db, message, settings)
        db.commit()
    return MessageResponse(message="If the account exists, reset instructions will arrive shortly.")


@router.post("/auth/password/reset", response_model=MessageResponse, tags=["auth"])
def reset_password(payload: PasswordResetRequest, db: Db, settings: AppSettings) -> MessageResponse:
    user = _consume_one_time_token(db, payload.token, "password_reset", settings)
    user.password_hash = hash_password(payload.password)
    now = datetime.now(UTC)
    db.query(RefreshSession).filter(RefreshSession.user_id == user.id).update(
        {RefreshSession.revoked_at: now}
    )
    db.commit()
    return MessageResponse(message="Password changed and existing sessions revoked.")


@router.get("/auth/me", response_model=UserView, tags=["auth"])
def me(user: CurrentUser) -> User:
    return user


@router.get("/auth/sessions", response_model=list[SessionView], tags=["auth"])
def sessions(db: Db, user: CurrentUser) -> list[RefreshSession]:
    return list(
        db.scalars(
            select(RefreshSession)
            .where(RefreshSession.user_id == user.id)
            .order_by(RefreshSession.created_at.desc())
        )
    )


@router.delete("/auth/sessions/{session_id}", response_model=MessageResponse, tags=["auth"])
def revoke_session(session_id: str, db: Db, user: CurrentUser) -> MessageResponse:
    session = db.scalar(
        select(RefreshSession).where(
            RefreshSession.id == session_id, RefreshSession.user_id == user.id
        )
    )
    if session is None:
        raise HTTPException(
            status_code=404, detail={"code": "session.not_found", "message": "Session not found"}
        )
    session.revoked_at = datetime.now(UTC)
    db.commit()
    return MessageResponse(message="Session revoked.")


@router.post("/auth/2fa/setup", tags=["auth"])
def setup_2fa(db: Db, user: CurrentUser) -> dict[str, str]:
    secret = pyotp.random_base32()
    user.totp_secret = f"pending:{secret}"
    db.commit()
    return {
        "secret": secret,
        "uri": pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="SHADOWGRID"),
    }


@router.post("/auth/2fa/confirm", response_model=MessageResponse, tags=["auth"])
def confirm_2fa(
    code: Annotated[str, Query(pattern=r"^\d{6}$")], db: Db, user: CurrentUser
) -> MessageResponse:
    if not user.totp_secret or not user.totp_secret.startswith("pending:"):
        raise HTTPException(
            status_code=409,
            detail={"code": "auth.2fa_not_pending", "message": "Two-factor setup is not pending"},
        )
    secret = user.totp_secret.removeprefix("pending:")
    if not pyotp.TOTP(secret).verify(code, valid_window=1):
        raise HTTPException(
            status_code=400,
            detail={"code": "auth.invalid_2fa", "message": "Verification code is invalid"},
        )
    user.totp_secret = secret
    db.commit()
    return MessageResponse(message="Two-factor authentication enabled.")


@router.get("/worlds", response_model=list[WorldView], tags=["worlds"])
def worlds(db: Db, _: CurrentUser) -> list[World]:
    return list(db.scalars(select(World).order_by(World.starts_at.desc())))


@router.get("/worlds/{world_id}/districts", response_model=list[DistrictView], tags=["worlds"])
def world_districts(world_id: str, db: Db, _: CurrentUser) -> list[DistrictView]:
    return [
        DistrictView.model_validate(item)
        for item in db.scalars(
            select(District).where(District.world_id == world_id).order_by(District.name)
        )
    ]


@router.post("/worlds/{world_id}/join", response_model=ProfileView, tags=["worlds"])
def join_world(
    world_id: str, payload: JoinWorldRequest, db: Db, user: CurrentUser, key: IdempotencyKey
) -> PlayerProfile:
    existing_command = get_idempotent(db, user.id, key, "world.join")
    if existing_command:
        profile = db.get(PlayerProfile, existing_command.resource_id)
        if profile:
            return profile
    world = db.get(World, world_id)
    district = db.get(District, payload.home_district_id)
    if world is None or world.status != "active" or district is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "world.not_found", "message": "Active world or district not found"},
        )
    profile = create_player_profile(
        db, user, world, payload.codename, payload.archetype, district, key
    )
    remember_idempotent(db, user.id, key, "world.join", profile.id, {"profile_id": profile.id})
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/profiles/me", response_model=ProfileView, tags=["profiles"])
def profile_me(profile: CurrentProfile) -> PlayerProfile:
    return profile


@router.patch("/profiles/me/tutorial", response_model=ProfileView, tags=["profiles"])
def tutorial(payload: TutorialRequest, db: Db, profile: CurrentProfile) -> PlayerProfile:
    if payload.step < profile.tutorial_step or payload.step > profile.tutorial_step + 1:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "tutorial.invalid_transition",
                "message": "Tutorial steps must be completed in order",
            },
        )
    profile.tutorial_step = payload.step
    db.commit()
    return profile


@router.get("/resources", tags=["resources"])
def resources(db: Db, profile: CurrentProfile) -> dict[str, Any]:
    entries = list(
        db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.owner_type == "profile", LedgerEntry.owner_id == profile.id)
            .order_by(LedgerEntry.created_at.desc())
            .limit(50)
        )
    )
    return {
        "balance": {
            name: float(getattr(profile.resources, name))
            for name in (
                "cash",
                "capital",
                "influence",
                "intelligence",
                "logistics_capacity",
                "personnel_capacity",
            )
        },
        "version": profile.resources.version,
        "ledger": [
            {
                "id": item.id,
                "resource_type": item.resource_type,
                "amount": float(item.amount),
                "balance_after": float(item.balance_after),
                "reason": item.reason,
                "reference_type": item.reference_type,
                "reference_id": item.reference_id,
                "created_at": item.created_at,
            }
            for item in entries
        ],
    }


@router.get("/districts", response_model=list[DistrictView], tags=["districts"])
def districts(db: Db, profile: CurrentProfile) -> list[DistrictView]:
    result: list[DistrictView] = []
    for district in db.scalars(
        select(District).where(District.world_id == profile.world_id).order_by(District.name)
    ):
        totals: dict[str, Decimal] = {
            kind: value
            for kind, value in db.execute(
                select(DistrictInfluence.kind, func.sum(DistrictInfluence.points))
                .where(DistrictInfluence.district_id == district.id)
                .group_by(DistrictInfluence.kind)
            ).tuples()
        }
        result.append(
            DistrictView.model_validate(district).model_copy(
                update={"influence": {key: float(value) for key, value in totals.items()}}
            )
        )
    return result


@router.get("/districts/{district_id}", response_model=DistrictView, tags=["districts"])
def district_detail(district_id: str, db: Db, profile: CurrentProfile) -> DistrictView:
    district = db.scalar(
        select(District).where(District.id == district_id, District.world_id == profile.world_id)
    )
    if not district:
        raise HTTPException(
            status_code=404, detail={"code": "district.not_found", "message": "District not found"}
        )
    totals: dict[str, Decimal] = {
        kind: value
        for kind, value in db.execute(
            select(DistrictInfluence.kind, func.sum(DistrictInfluence.points))
            .where(DistrictInfluence.district_id == district.id)
            .group_by(DistrictInfluence.kind)
        ).tuples()
    }
    return DistrictView.model_validate(district).model_copy(
        update={"influence": {key: float(value) for key, value in totals.items()}}
    )


@router.get("/businesses", response_model=list[BusinessView], tags=["businesses"])
def businesses(db: Db, profile: CurrentProfile) -> list[Business]:
    return list(
        db.scalars(
            select(Business)
            .where(Business.profile_id == profile.id)
            .order_by(Business.created_at.desc())
        )
    )


@router.post("/businesses", response_model=BusinessView, status_code=201, tags=["businesses"])
def purchase_business(
    payload: BuyBusinessRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Business:
    previous = get_idempotent(db, user.id, key, "business.buy")
    if previous:
        existing = db.get(Business, previous.resource_id)
        if existing:
            return existing
    district = db.get(District, payload.district_id)
    if district is None:
        raise HTTPException(
            status_code=404, detail={"code": "district.not_found", "message": "District not found"}
        )
    business = buy_business(db, profile, payload.business_type, district, payload.name, key)
    remember_idempotent(db, user.id, key, "business.buy", business.id, {"business_id": business.id})
    audit(db, user.id, "business.buy", "business", business.id, request_id(request))
    safe_commit(db)
    return business


@router.post("/businesses/{business_id}/upgrade", response_model=BusinessView, tags=["businesses"])
def upgrade_business(
    business_id: str, db: Db, user: CurrentUser, profile: CurrentProfile, key: IdempotencyKey
) -> Business:
    business = db.scalar(
        select(Business)
        .where(Business.id == business_id, Business.profile_id == profile.id)
        .with_for_update()
    )
    if not business:
        raise HTTPException(
            status_code=404, detail={"code": "business.not_found", "message": "Business not found"}
        )
    if business.upgrade_finishes_at:
        raise HTTPException(
            status_code=409,
            detail={"code": "business.upgrade_running", "message": "Upgrade already running"},
        )
    price = (
        as_money(BUSINESS_TYPES[business.business_type]["price"]) * Decimal("0.6") * business.level
    )
    apply_profile_resource(
        db,
        profile.id,
        "capital",
        -price,
        reason="business_upgrade",
        reference_type="business",
        reference_id=business.id,
        idempotency_key=key,
    )
    business.level += 1
    business.revenue *= Decimal("1.35")
    business.operating_cost *= Decimal("1.18")
    business.upgrade_finishes_at = datetime.now(UTC) + timedelta(minutes=30 * business.level)
    remember_idempotent(
        db, user.id, key, "business.upgrade", business.id, {"business_id": business.id}
    )
    safe_commit(db)
    return business


def as_money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


@router.get("/facilities", response_model=list[FacilityView], tags=["facilities"])
def facilities(db: Db, profile: CurrentProfile) -> list[Facility]:
    return list(db.scalars(select(Facility).where(Facility.profile_id == profile.id)))


@router.post("/facilities", response_model=FacilityView, status_code=201, tags=["facilities"])
def facility_build(
    payload: FacilityRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Facility:
    previous = get_idempotent(db, user.id, key, "facility.build")
    if previous:
        existing = db.get(Facility, previous.resource_id)
        if existing:
            return existing
    facility = build_facility(db, profile, payload.facility_type, key)
    remember_idempotent(
        db, user.id, key, "facility.build", facility.id, {"facility_id": facility.id}
    )
    safe_commit(db)
    return facility


@router.get("/specialists", response_model=list[SpecialistView], tags=["specialists"])
def specialists(db: Db, profile: CurrentProfile) -> list[Specialist]:
    return list(
        db.scalars(
            select(Specialist)
            .where(Specialist.profile_id == profile.id)
            .order_by(Specialist.created_at)
        )
    )


@router.post("/specialists", response_model=SpecialistView, status_code=201, tags=["specialists"])
def specialist_recruit(
    payload: RecruitSpecialistRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Specialist:
    previous = get_idempotent(db, user.id, key, "specialist.recruit")
    if previous:
        existing = db.get(Specialist, previous.resource_id)
        if existing:
            return existing
    specialist = recruit_specialist(db, profile, payload.role, key)
    remember_idempotent(
        db, user.id, key, "specialist.recruit", specialist.id, {"specialist_id": specialist.id}
    )
    safe_commit(db)
    return specialist


@router.get("/operations", response_model=list[OperationView], tags=["operations"])
def operations(db: Db, profile: CurrentProfile, settings: AppSettings) -> list[Operation]:
    with _operation_resolution_lock:
        items = list(
            db.scalars(
                select(Operation)
                .where(Operation.profile_id == profile.id)
                .order_by(Operation.started_at.desc())
                .with_for_update()
            )
        )
        changed = False
        for operation in items:
            before = operation.status
            resolve_operation(db, operation, settings)
            changed = changed or before != operation.status
        if changed:
            db.commit()
        return items


@router.post("/operations", response_model=OperationView, status_code=201, tags=["operations"])
def operation_start(
    payload: StartOperationRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> Operation:
    previous = get_idempotent(db, user.id, key, "operation.start")
    if previous:
        existing = db.get(Operation, previous.resource_id)
        if existing:
            return existing
    specialist = db.get(Specialist, payload.specialist_id)
    district = db.get(District, payload.district_id)
    if specialist is None or district is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "operation.dependency_missing",
                "message": "Specialist or district not found",
            },
        )
    operation = start_operation(db, profile, specialist, district, payload, key, settings)
    remember_idempotent(
        db, user.id, key, "operation.start", operation.id, {"operation_id": operation.id}
    )
    safe_commit(db)
    return operation


@router.get("/operations/{operation_id}", response_model=OperationView, tags=["operations"])
def operation_report(
    operation_id: str, db: Db, profile: CurrentProfile, settings: AppSettings
) -> Operation:
    operation = db.scalar(
        select(Operation).where(Operation.id == operation_id, Operation.profile_id == profile.id)
    )
    if not operation:
        raise HTTPException(
            status_code=404,
            detail={"code": "operation.not_found", "message": "Operation not found"},
        )
    resolve_operation(db, operation, settings)
    db.commit()
    return operation


@router.get("/intelligence", response_model=list[IntelReportView], tags=["intelligence"])
def intelligence(db: Db, profile: CurrentProfile) -> list[IntelReport]:
    return list(
        db.scalars(
            select(IntelReport)
            .where(IntelReport.profile_id == profile.id)
            .order_by(IntelReport.observed_at.desc())
            .limit(100)
        )
    )


@router.patch("/intelligence/{report_id}", response_model=IntelReportView, tags=["intelligence"])
def update_intel(
    report_id: str,
    status_value: Annotated[
        str,
        Query(alias="status", pattern=r"^(new|reviewed|stale|contradicted|confirmed|archived)$"),
    ],
    db: Db,
    profile: CurrentProfile,
) -> IntelReport:
    report = db.scalar(
        select(IntelReport).where(IntelReport.id == report_id, IntelReport.profile_id == profile.id)
    )
    if not report:
        raise HTTPException(
            status_code=404,
            detail={"code": "intel.not_found", "message": "Intelligence report not found"},
        )
    report.status = status_value
    db.commit()
    return report


@router.get("/network", response_model=NetworkView, tags=["network"])
def network(db: Db, profile: CurrentProfile) -> NetworkView:
    nodes = [NetworkNode(id=profile.id, kind="player", label=profile.codename)]
    edges: list[NetworkEdge] = []
    for specialist in db.scalars(select(Specialist).where(Specialist.profile_id == profile.id)):
        nodes.append(NetworkNode(id=specialist.id, kind="specialist", label=specialist.name))
        edges.append(NetworkEdge(source=profile.id, target=specialist.id, kind="assignment"))
    for business in db.scalars(select(Business).where(Business.profile_id == profile.id)):
        nodes.append(NetworkNode(id=business.id, kind="business", label=business.name))
        edges.append(NetworkEdge(source=profile.id, target=business.id, kind="ownership"))
        edges.append(
            NetworkEdge(source=business.id, target=business.district_id, kind="district_presence")
        )
    district_ids = {edge.target for edge in edges if edge.kind == "district_presence"}
    for district in db.scalars(select(District).where(District.id.in_(district_ids))):
        nodes.append(NetworkNode(id=district.id, kind="district", label=district.name))
    for report in db.scalars(select(IntelReport).where(IntelReport.profile_id == profile.id)):
        if report.target_id not in {node.id for node in nodes}:
            nodes.append(
                NetworkNode(
                    id=report.target_id,
                    kind=report.target_type,
                    label="Uncertain contact",
                    uncertain=True,
                )
            )
        edges.append(
            NetworkEdge(
                source=profile.id,
                target=report.target_id,
                kind="intelligence",
                uncertain=report.visible_confidence < 75,
            )
        )
    return NetworkView(nodes=nodes, edges=edges)


@router.get("/investigations", tags=["investigations"])
def investigation(db: Db, profile: CurrentProfile) -> dict[str, Any]:
    pressure = profile.investigation_pressure
    stage = (
        "unremarkable"
        if pressure < 20
        else "attention"
        if pressure < 40
        else "observation"
        if pressure < 60
        else "structural_investigation"
        if pressure < 75
        else "taskforce"
        if pressure < 90
        else "enforcement_risk"
    )
    known = list(
        db.scalars(
            select(Evidence)
            .where(Evidence.profile_id == profile.id)
            .order_by(Evidence.created_at.desc())
            .limit(max(1, pressure // 20))
        )
    )
    return {
        "estimated": True,
        "pressure": pressure,
        "stage": stage,
        "known_signals": [
            {
                "id": item.id,
                "type": item.evidence_type,
                "estimated_strength": max(5, item.strength - 8),
                "created_at": item.created_at,
            }
            for item in known
        ],
        "notice": "This is an incomplete player estimate; the internal authority model remains hidden.",
    }


def _organization_view(
    db: Session, organization: Organization, profile_id: str | None = None
) -> OrganizationView:
    membership = (
        db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.organization_id == organization.id,
                OrganizationMembership.profile_id == profile_id,
            )
        )
        if profile_id
        else None
    )
    count = (
        db.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization.id,
                OrganizationMembership.status == "active",
            )
        )
        or 0
    )
    return OrganizationView.model_validate(organization).model_copy(
        update={"my_role": membership.role if membership else None, "member_count": count}
    )


@router.get("/organizations", response_model=list[OrganizationView], tags=["organizations"])
def organizations(db: Db, profile: CurrentProfile) -> list[OrganizationView]:
    return [
        _organization_view(db, item, profile.id)
        for item in db.scalars(
            select(Organization)
            .where(Organization.world_id == profile.world_id)
            .order_by(Organization.name)
        )
    ]


@router.get(
    "/organizations/{organization_id}/members",
    response_model=list[OrganizationMemberView],
    tags=["organizations"],
)
def organization_members(
    organization_id: str, db: Db, profile: CurrentProfile
) -> list[OrganizationMemberView]:
    membership_with_permission(db, profile.id, "organization.view", organization_id)
    rows = db.execute(
        select(OrganizationMembership, PlayerProfile)
        .join(PlayerProfile, PlayerProfile.id == OrganizationMembership.profile_id)
        .where(OrganizationMembership.organization_id == organization_id)
        .order_by(OrganizationMembership.joined_at)
    ).all()
    return [
        OrganizationMemberView(
            membership_id=membership.id,
            profile_id=member_profile.id,
            codename=member_profile.codename,
            role=membership.role,
            status=membership.status,
            joined_at=membership.joined_at,
        )
        for membership, member_profile in rows
    ]


@router.patch(
    "/organizations/{organization_id}/members/{membership_id}",
    response_model=OrganizationMemberView,
    tags=["organizations"],
)
def organization_member_role(
    organization_id: str,
    membership_id: str,
    payload: UpdateOrganizationRoleRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> OrganizationMemberView:
    membership_with_permission(db, profile.id, "organization.manage_roles", organization_id)
    membership = db.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
        )
        .with_for_update()
    )
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "organization.member_not_found", "message": "Member not found"},
        )
    if membership.role == "director":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "organization.director_protected",
                "message": "Director transfer requires a dedicated transfer workflow",
            },
        )
    previous_role = membership.role
    membership.role = payload.role
    member_profile = db.get(PlayerProfile, membership.profile_id)
    if member_profile is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "profile.not_found", "message": "Profile not found"},
        )
    audit(
        db,
        user.id,
        "organization.member_role_changed",
        "organization_membership",
        membership.id,
        request_id(request),
        {"previous_role": previous_role, "new_role": payload.role},
    )
    safe_commit(db)
    return OrganizationMemberView(
        membership_id=membership.id,
        profile_id=member_profile.id,
        codename=member_profile.codename,
        role=membership.role,
        status=membership.status,
        joined_at=membership.joined_at,
    )


@router.delete(
    "/organizations/{organization_id}/members/{membership_id}",
    response_model=MessageResponse,
    tags=["organizations"],
)
def organization_member_remove(
    organization_id: str,
    membership_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> MessageResponse:
    membership_with_permission(db, profile.id, "organization.remove_members", organization_id)
    membership = db.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.id == membership_id,
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.status == "active",
        )
        .with_for_update()
    )
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "organization.member_not_found", "message": "Member not found"},
        )
    if membership.profile_id == profile.id or membership.role == "director":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "organization.member_protected",
                "message": "The active director or current actor cannot be removed",
            },
        )
    membership.status = "removed"
    audit(
        db,
        user.id,
        "organization.member_removed",
        "organization_membership",
        membership.id,
        request_id(request),
        {"role": membership.role},
    )
    safe_commit(db)
    return MessageResponse(message="Member removed.")


@router.post(
    "/organizations", response_model=OrganizationView, status_code=201, tags=["organizations"]
)
def organization_create(
    payload: CreateOrganizationRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> OrganizationView:
    if profile.tutorial_step < 3:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "organization.progress_required",
                "message": "Complete the organization tutorial milestone first",
            },
        )
    if db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.profile_id == profile.id,
            OrganizationMembership.status == "active",
        )
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "organization.already_member",
                "message": "Leave the current organization before creating one",
            },
        )
    if payload.archetype not in ARCHETYPES:
        raise HTTPException(
            status_code=422,
            detail={"code": "organization.invalid_archetype", "message": "Unknown archetype"},
        )
    organization = Organization(
        world_id=profile.world_id,
        name=payload.name,
        tag=payload.tag.upper(),
        archetype=payload.archetype,
        description=payload.description,
    )
    db.add(organization)
    db.flush()
    apply_profile_resource(
        db,
        profile.id,
        "capital",
        -10_000,
        reason="organization_creation",
        reference_type="organization",
        reference_id=organization.id,
        idempotency_key=key,
    )
    apply_profile_resource(
        db,
        profile.id,
        "influence",
        -5,
        reason="organization_creation",
        reference_type="organization",
        reference_id=organization.id,
        idempotency_key=key,
    )
    db.add(
        OrganizationMembership(
            organization_id=organization.id, profile_id=profile.id, role="director"
        )
    )
    remember_idempotent(
        db,
        user.id,
        key,
        "organization.create",
        organization.id,
        {"organization_id": organization.id},
    )
    safe_commit(db)
    return _organization_view(db, organization, profile.id)


@router.post(
    "/organizations/{organization_id}/invites",
    response_model=MessageResponse,
    tags=["organizations"],
)
def organization_invite(
    organization_id: str, payload: InviteRequest, db: Db, profile: CurrentProfile
) -> MessageResponse:
    membership_with_permission(db, profile.id, "organization.invite", organization_id)
    count = (
        db.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.status == "active",
            )
        )
        or 0
    )
    organization = db.get(Organization, organization_id)
    if organization is None or count >= organization.member_limit:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "organization.member_limit",
                "message": "Organization member limit reached",
            },
        )
    db.add(
        OrganizationInvite(
            organization_id=organization_id,
            invited_by_profile_id=profile.id,
            email=payload.email.lower(),
            expires_at=datetime.now(UTC) + timedelta(days=3),
        )
    )
    safe_commit(db)
    return MessageResponse(message="Invitation created.")


@router.post(
    "/organizations/invites/{invite_id}/accept",
    response_model=OrganizationView,
    tags=["organizations"],
)
def accept_invite(
    invite_id: str, db: Db, user: CurrentUser, profile: CurrentProfile
) -> OrganizationView:
    invite = db.scalar(
        select(OrganizationInvite).where(OrganizationInvite.id == invite_id).with_for_update()
    )
    if (
        invite is None
        or invite.email != user.email
        or invite.status != "pending"
        or as_utc(invite.expires_at) < datetime.now(UTC)
    ):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "organization.invite_not_found",
                "message": "Active invitation not found",
            },
        )
    if db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.profile_id == profile.id,
            OrganizationMembership.status == "active",
        )
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "organization.already_member",
                "message": "Profile is already in an organization",
            },
        )
    db.add(
        OrganizationMembership(
            organization_id=invite.organization_id, profile_id=profile.id, role="candidate"
        )
    )
    invite.status = "accepted"
    db.commit()
    organization = db.get(Organization, invite.organization_id)
    if organization is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "organization.not_found", "message": "Organization not found"},
        )
    return _organization_view(db, organization, profile.id)


@router.post(
    "/organizations/{organization_id}/treasury/deposit",
    response_model=OrganizationView,
    tags=["treasury"],
)
def treasury_deposit(
    organization_id: str,
    payload: TreasuryRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> OrganizationView:
    membership_with_permission(db, profile.id, "treasury.deposit", organization_id)
    organization = db.scalar(
        select(Organization).where(Organization.id == organization_id).with_for_update()
    )
    if organization is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "organization.not_found", "message": "Organization not found"},
        )
    apply_profile_resource(
        db,
        profile.id,
        payload.resource_type,
        -payload.amount,
        reason="treasury_deposit",
        reference_type="organization",
        reference_id=organization.id,
        idempotency_key=key,
    )
    field = f"treasury_{payload.resource_type}"
    new_balance = as_money(getattr(organization, field)) + as_money(payload.amount)
    setattr(organization, field, new_balance)
    db.add(
        LedgerEntry(
            owner_type="organization",
            owner_id=organization.id,
            resource_type=payload.resource_type,
            amount=payload.amount,
            balance_after=new_balance,
            reason="treasury_deposit",
            reference_type="profile",
            reference_id=profile.id,
            idempotency_key=key,
            metadata_json={},
        )
    )
    remember_idempotent(
        db, user.id, key, "treasury.deposit", organization.id, {"organization_id": organization.id}
    )
    safe_commit(db)
    return _organization_view(db, organization, profile.id)


@router.get("/treaties", response_model=list[TreatyView], tags=["treaties"])
def treaties(db: Db, profile: CurrentProfile) -> list[Treaty]:
    membership = db.scalar(
        select(OrganizationMembership).where(
            OrganizationMembership.profile_id == profile.id,
            OrganizationMembership.status == "active",
        )
    )
    query = select(Treaty).where(Treaty.world_id == profile.world_id)
    if membership:
        query = query.where(
            (Treaty.visibility == "public")
            | (Treaty.proposer_org_id == membership.organization_id)
            | (Treaty.recipient_org_id == membership.organization_id)
        )
    else:
        query = query.where(Treaty.visibility == "public")
    return list(db.scalars(query.order_by(Treaty.created_at.desc())))


@router.post("/treaties", response_model=TreatyView, status_code=201, tags=["treaties"])
def treaty_create(payload: CreateTreatyRequest, db: Db, profile: CurrentProfile) -> Treaty:
    membership = membership_with_permission(db, profile.id, "diplomacy.propose")
    if payload.recipient_org_id == membership.organization_id:
        raise HTTPException(
            status_code=422,
            detail={"code": "treaty.same_party", "message": "Treaty parties must differ"},
        )
    recipient = db.get(Organization, payload.recipient_org_id)
    if recipient is None or recipient.world_id != profile.world_id:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "organization.not_found",
                "message": "Recipient organization not found",
            },
        )
    allowed = {"non_aggression", "intelligence_exchange", "trade_cooperation", "joint_operation"}
    if payload.treaty_type not in allowed:
        raise HTTPException(
            status_code=422,
            detail={"code": "treaty.invalid_type", "message": "Unsupported treaty type"},
        )
    treaty = Treaty(
        world_id=profile.world_id,
        proposer_org_id=membership.organization_id,
        recipient_org_id=recipient.id,
        treaty_type=payload.treaty_type,
        terms_json=payload.terms,
        visibility=payload.visibility,
        expires_at=datetime.now(UTC) + timedelta(days=payload.duration_days),
    )
    db.add(treaty)
    db.commit()
    return treaty


@router.post("/treaties/{treaty_id}/accept", response_model=TreatyView, tags=["treaties"])
def treaty_accept(treaty_id: str, db: Db, profile: CurrentProfile) -> Treaty:
    treaty = db.scalar(select(Treaty).where(Treaty.id == treaty_id).with_for_update())
    if treaty is None or treaty.status != "proposed":
        raise HTTPException(
            status_code=404,
            detail={"code": "treaty.not_found", "message": "Proposed treaty not found"},
        )
    membership_with_permission(db, profile.id, "diplomacy.accept", treaty.recipient_org_id)
    treaty.status = "active"
    treaty.starts_at = datetime.now(UTC)
    db.commit()
    return treaty


@router.get("/research", response_model=list[ResearchView], tags=["research"])
def research_projects(db: Db, profile: CurrentProfile) -> list[ResearchProject]:
    return list(
        db.scalars(
            select(ResearchProject)
            .where(ResearchProject.profile_id == profile.id)
            .order_by(ResearchProject.started_at.desc())
        )
    )


@router.post("/research", response_model=ResearchView, status_code=201, tags=["research"])
def research_start(
    payload: StartResearchRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> ResearchProject:
    previous = get_idempotent(db, user.id, key, "research.start")
    if previous:
        existing = db.get(ResearchProject, previous.resource_id)
        if existing:
            return existing
    project = start_research(db, profile, payload.research_key, key, settings)
    remember_idempotent(db, user.id, key, "research.start", project.id, {"research_id": project.id})
    safe_commit(db)
    return project


@router.get("/world-events", tags=["world-events"])
def world_events(db: Db, profile: CurrentProfile) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "event_key": item.event_key,
            "title": item.title,
            "status": item.status,
            "effects": item.effects_json,
            "starts_at": item.starts_at,
            "ends_at": item.ends_at,
        }
        for item in db.scalars(
            select(WorldEvent)
            .where(WorldEvent.world_id == profile.world_id)
            .order_by(WorldEvent.starts_at)
        )
    ]


@router.get("/news", tags=["news"])
def news(db: Db, profile: CurrentProfile) -> list[dict[str, Any]]:
    events = db.scalars(
        select(WorldEvent)
        .where(WorldEvent.world_id == profile.world_id)
        .order_by(WorldEvent.starts_at.desc())
        .limit(20)
    )
    return [
        {
            "id": event.id,
            "title": event.title,
            "summary": "A verified world-state event is changing simulated district and market values.",
            "published_at": event.starts_at,
            "certainty": "verified" if event.status == "active" else "scheduled",
        }
        for event in events
    ]


@router.get("/notifications", tags=["notifications"])
def notifications(db: Db, user: CurrentUser) -> list[dict[str, Any]]:
    return [
        {
            "id": item.id,
            "event_type": item.event_type,
            "title": item.title,
            "body": item.body,
            "read_at": item.read_at,
            "created_at": item.created_at,
        }
        for item in db.scalars(
            select(Notification)
            .where(Notification.user_id == user.id)
            .order_by(Notification.created_at.desc())
            .limit(100)
        )
    ]


@router.post(
    "/notifications/{notification_id}/read", response_model=MessageResponse, tags=["notifications"]
)
def read_notification(notification_id: str, db: Db, user: CurrentUser) -> MessageResponse:
    item = db.scalar(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "notification.not_found", "message": "Notification not found"},
        )
    item.read_at = datetime.now(UTC)
    db.commit()
    return MessageResponse(message="Notification marked as read.")


@router.get("/rankings", tags=["rankings"])
def rankings(db: Db, profile: CurrentProfile) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    profiles = db.scalars(select(PlayerProfile).where(PlayerProfile.world_id == profile.world_id))
    for candidate in profiles:
        business_value = (
            db.scalar(
                select(
                    func.coalesce(func.sum(Business.revenue - Business.operating_cost), 0)
                ).where(Business.profile_id == candidate.id)
            )
            or 0
        )
        influence = (
            db.scalar(
                select(func.coalesce(func.sum(DistrictInfluence.points), 0)).where(
                    DistrictInfluence.profile_id == candidate.id
                )
            )
            or 0
        )
        economic = float(business_value) / 1000 + float(candidate.resources.capital) / 5000
        influence_score = float(influence)
        intel_score = float(candidate.resources.intelligence)
        penalty = candidate.investigation_pressure * 0.35
        score = (
            economic * 0.25
            + influence_score * 0.20
            + candidate.stability * 0.15
            + intel_score * 0.10
            + candidate.legitimacy * 0.10
            + candidate.loyalty * 0.10
            + candidate.stability * 0.10
            - penalty
        )
        rows.append(
            {
                "profile_id": candidate.id,
                "codename": candidate.codename,
                "economic_power": round(economic, 2),
                "influence": round(influence_score, 2),
                "stability": candidate.stability,
                "intelligence": round(intel_score, 2),
                "diplomacy": candidate.legitimacy,
                "resilience": candidate.loyalty,
                "social_impact": candidate.stability,
                "penalty": round(penalty, 2),
                "score": round(score, 2),
            }
        )
    rows.sort(key=lambda item: item["score"], reverse=True)
    for rank, item in enumerate(rows, 1):
        item["rank"] = rank
    return rows


@router.get("/privacy/export", tags=["privacy"])
def privacy_export(db: Db, user: CurrentUser) -> dict[str, Any]:
    profiles = list(db.scalars(select(PlayerProfile).where(PlayerProfile.user_id == user.id)))
    profile_ids = [item.id for item in profiles]
    return {
        "exported_at": datetime.now(UTC),
        "account": {
            "id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "locale": user.locale,
            "created_at": user.created_at,
        },
        "profiles": [
            {
                "id": item.id,
                "world_id": item.world_id,
                "codename": item.codename,
                "archetype": item.archetype,
            }
            for item in profiles
        ],
        "ledger": [
            {
                "resource_type": item.resource_type,
                "amount": float(item.amount),
                "balance_after": float(item.balance_after),
                "reason": item.reason,
                "created_at": item.created_at,
            }
            for item in db.scalars(
                select(LedgerEntry).where(
                    LedgerEntry.owner_type == "profile", LedgerEntry.owner_id.in_(profile_ids)
                )
            )
        ],
    }


@router.delete("/privacy/account", response_model=MessageResponse, tags=["privacy"])
def delete_account(db: Db, user: CurrentUser) -> MessageResponse:
    now = datetime.now(UTC)
    user.disabled_at = now
    user.email = f"deleted-{user.id}@shadowgrid.invalid"
    user.display_name = "Deleted player"
    user.password_hash = hash_password(secrets.token_urlsafe(48))
    user.totp_secret = None
    db.query(RefreshSession).filter(RefreshSession.user_id == user.id).update(
        {RefreshSession.revoked_at: now}
    )
    db.commit()
    return MessageResponse(message="Account disabled and personal identifiers pseudonymized.")


@router.get("/admin/summary", tags=["admin"])
def admin_summary(db: Db, _: Annotated[User, Depends(require_admin)]) -> dict[str, int]:
    return {
        "users": db.scalar(select(func.count()).select_from(User)) or 0,
        "worlds": db.scalar(select(func.count()).select_from(World)) or 0,
        "operations_running": db.scalar(
            select(func.count()).select_from(Operation).where(Operation.status == "running")
        )
        or 0,
        "outbox_pending": db.scalar(
            select(func.count()).select_from(EmailOutbox).where(EmailOutbox.status != "sent")
        )
        or 0,
        "audit_events": db.scalar(select(func.count()).select_from(AuditLog)) or 0,
    }


@router.get("/moderation/audit", tags=["moderation"])
def moderation_audit(db: Db, user: CurrentUser) -> list[dict[str, Any]]:
    if not (user.is_admin or user.is_moderator):
        raise HTTPException(
            status_code=403,
            detail={"code": "auth.forbidden", "message": "Moderator permission required"},
        )
    return [
        {
            "id": item.id,
            "actor_user_id": item.actor_user_id,
            "action": item.action,
            "target_type": item.target_type,
            "target_id": item.target_id,
            "request_id": item.request_id,
            "created_at": item.created_at,
        }
        for item in db.scalars(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(200))
    ]


@router.get("/config", tags=["game-config"])
def public_config() -> dict[str, Any]:
    return {
        "archetypes": ARCHETYPES,
        "business_types": BUSINESS_TYPES,
        "facility_types": FACILITY_TYPES,
        "operation_types": OPERATION_TYPES,
        "research": RESEARCH,
        "safety_notice": "All covert categories are fictional and abstract.",
    }
