from __future__ import annotations

import hashlib
import secrets
import threading
import unicodedata
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated, Any

import pyotp
from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.ai import (
    list_ai_profiles,
    list_local_companies,
    run_ai_tick,
    set_ai_paused,
)
from shadowgrid.cartels import ensure_cartel_account
from shadowgrid.companies import (
    company_configuration,
    company_history,
    create_company,
    get_company,
    invest_in_company,
    list_owned_companies,
)
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
    get_idempotent,
    membership_with_permission,
    recruit_specialist,
    remember_idempotent,
    resolve_operation,
    safe_commit,
    start_operation,
    start_research,
)
from shadowgrid.economy import (
    latest_economy_tick,
    list_city_sector_markets,
    list_company_economy_reports,
    list_market_economy_reports,
    next_economy_tick_at,
    run_economy_tick,
)
from shadowgrid.exchange import (
    cancel_order,
    create_ipo,
    declare_dividend,
    exchange_configuration,
    get_company_exchange_listing,
    get_exchange_listing,
    ipo_eligibility,
    list_dividends,
    list_exchange_listings,
    list_profile_orders,
    listing_company_reports,
    listing_order_book,
    listing_price_history,
    listing_shareholders,
    listing_trades,
    place_order,
    profile_portfolio,
)
from shadowgrid.game_config import (
    ARCHETYPES,
    BUSINESS_TYPES,
    FACILITY_TYPES,
    OPERATION_TYPES,
    RESEARCH,
)
from shadowgrid.mailer import account_email_copy, deliver_email, queue_email
from shadowgrid.models import (
    AuditLog,
    Business,
    Company,
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
from shadowgrid.multiplayer_schemas import CityView
from shadowgrid.onboarding import (
    join_world as join_world_service,
)
from shadowgrid.onboarding import (
    list_active_cities,
    list_city_districts,
    select_city,
)
from shadowgrid.rate_limits import clear_rate_limit, consume_rate_limit
from shadowgrid.schemas import (
    AiDecisionTickView,
    AiPauseRequest,
    AiProfileView,
    AssignSpecialistRequest,
    BusinessView,
    BuyBusinessRequest,
    CitySectorMarketView,
    CompanyConfigurationView,
    CompanyDetailView,
    CompanyEconomyReportView,
    CompanyInvestmentRequest,
    CompanyInvestmentView,
    CompanyMetricView,
    CompanyOwnershipView,
    CompanyView,
    CreateCompanyRequest,
    CreateIpoRequest,
    CreateOrganizationRequest,
    CreateTreatyRequest,
    DistrictView,
    DividendDeclarationView,
    DividendRequest,
    EconomyStatusView,
    EconomyTickView,
    ExchangeConfigurationView,
    ExchangeListingView,
    ExchangeOrderBookView,
    ExchangeOrderRequest,
    ExchangeOrderView,
    ExchangeTradeView,
    FacilityRequest,
    FacilityView,
    HealthResponse,
    HireSpecialistRequest,
    IntelReportView,
    InviteRequest,
    IpoEligibilityView,
    JoinWorldRequest,
    LoginRequest,
    ManualAiTickRequest,
    ManualEconomyTickRequest,
    ManualSpecialistPayrollRequest,
    MarketEconomyReportView,
    MessageResponse,
    NetworkEdge,
    NetworkNode,
    NetworkView,
    OperationView,
    OrganizationMemberView,
    OrganizationView,
    PasswordForgotRequest,
    PasswordResetRequest,
    PortfolioItemView,
    PriceSnapshotView,
    ProfileView,
    RecruitSpecialistRequest,
    RefreshRequest,
    RegisterRequest,
    ResearchView,
    ResourceView,
    SelectCityRequest,
    SessionView,
    ShareholderView,
    SpecialistEffectsView,
    SpecialistMarketCandidateView,
    SpecialistPayrollReportView,
    SpecialistPayrollTickView,
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
from shadowgrid.specialists import (
    assign_specialist,
    company_specialist_effects,
    hire_specialist,
    list_market_candidates,
    list_profile_specialists,
    list_specialist_payroll_reports,
    release_specialist,
    run_specialist_payroll,
)
from shadowgrid.world_events import event_feed

router = APIRouter()
_operation_resolution_lock = threading.Lock()


def _normalize_alpha_name(value: str) -> str:
    name = " ".join(unicodedata.normalize("NFKC", value).strip().split())
    if not 2 <= len(name) <= 40:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "auth.invalid_display_name",
                "message": "Name must contain between 2 and 40 characters",
            },
        )
    return name


def _alpha_account_email(display_name: str) -> str:
    normalized = _normalize_alpha_name(display_name).casefold()
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:40]
    return f"alpha-{digest}@accounts.shadowgrid.game"


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


def _check_login_limit(email: str, settings: Settings) -> None:
    attempts, retry_after = consume_rate_limit(
        scope="auth.login",
        raw_key=email,
        limit=settings.auth_login_rate_limit,
        window_seconds=settings.auth_login_rate_window_seconds,
    )
    if attempts > settings.auth_login_rate_limit:
        raise HTTPException(
            status_code=429,
            detail={"code": "auth.rate_limited", "message": "Too many login attempts; retry later"},
            headers={"Retry-After": str(retry_after)},
        )


def _check_auth_action_limit(
    scope: str,
    raw_key: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    attempts, retry_after = consume_rate_limit(
        scope=scope,
        raw_key=raw_key,
        limit=limit,
        window_seconds=window_seconds,
    )
    if attempts > limit:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "auth.rate_limited",
                "message": "Too many authentication requests; retry later",
            },
            headers={"Retry-After": str(retry_after)},
        )


def _check_trading_limit(profile_id: str, settings: Settings) -> None:
    attempts, retry_after = consume_rate_limit(
        scope="exchange.order",
        raw_key=profile_id,
        limit=settings.exchange_order_rate_limit_per_minute,
        window_seconds=60,
    )
    if attempts > settings.exchange_order_rate_limit_per_minute:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "exchange.rate_limited",
                "message": "Too many exchange order requests; retry later",
            },
            headers={"Retry-After": str(retry_after)},
        )


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
    display_name = _normalize_alpha_name(payload.display_name)
    if settings.alpha_open_registration:
        email = (
            payload.email.lower()
            if payload.email is not None
            else _alpha_account_email(display_name)
        )
    else:
        if payload.email is None:
            raise HTTPException(
                status_code=422,
                detail={"code": "auth.email_required", "message": "Email is required"},
            )
        email = payload.email.lower()
    _check_auth_action_limit(
        "auth.register",
        email,
        limit=settings.auth_email_rate_limit,
        window_seconds=settings.auth_email_rate_window_seconds,
    )
    if db.scalar(select(User).where(User.email == email)):
        if settings.alpha_open_registration and payload.email is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "auth.name_unavailable", "message": "Name is unavailable"},
            )
        return MessageResponse(
            message="If the address can be registered, a verification email will arrive shortly."
        )
    user = User(
        email=email,
        display_name=display_name,
        password_hash=hash_password(payload.password),
        locale=payload.locale,
        email_verified=settings.alpha_open_registration,
    )
    db.add(user)
    db.flush()
    if settings.alpha_open_registration:
        audit(db, user.id, "auth.alpha_register", "user", user.id, request_id(request))
        db.commit()
        return MessageResponse(message="Account created. You can sign in now.")

    raw = _issue_one_time_token(db, user, "verify_email", settings)
    subject, body = account_email_copy(
        "verify_email",
        user.locale,
        f"{settings.web_url}/verify-email?token={raw}",
    )
    message = queue_email(db, user.email, subject, body)
    audit(db, user.id, "auth.register", "user", user.id, request_id(request))
    db.commit()
    deliver_email(db, message, settings)
    db.commit()
    return MessageResponse(
        message="If the address can be registered, a verification email will arrive shortly."
    )


@router.post("/auth/verify-email", response_model=MessageResponse, tags=["auth"])
def verify_email(payload: VerifyEmailRequest, db: Db, settings: AppSettings) -> MessageResponse:
    _check_auth_action_limit(
        "auth.verify_email",
        payload.token,
        limit=settings.auth_token_rate_limit,
        window_seconds=settings.auth_token_rate_window_seconds,
    )
    user = _consume_one_time_token(db, payload.token, "verify_email", settings)
    user.email_verified = True
    db.commit()
    return MessageResponse(message="Email verified.")


@router.post("/auth/login", response_model=TokenPair, tags=["auth"])
def login(
    payload: LoginRequest, request: Request, response: Response, db: Db, settings: AppSettings
) -> TokenPair:
    if payload.display_name is not None and settings.alpha_open_registration:
        email = _alpha_account_email(payload.display_name)
    elif payload.email is not None:
        email = payload.email.lower()
    else:
        raise HTTPException(
            status_code=401,
            detail={"code": "auth.invalid_credentials", "message": "Invalid credentials"},
        )
    _check_login_limit(email, settings)
    user = db.scalar(select(User).where(User.email == email))
    valid = user is not None and verify_password(payload.password, user.password_hash)
    if not valid or user is None or not verify_totp(user, payload.totp_code):
        raise HTTPException(
            status_code=401,
            detail={
                "code": "auth.invalid_credentials",
                "message": "Name, email, password or verification code is invalid",
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
    clear_rate_limit(scope="auth.login", raw_key=email)
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
    email = payload.email.lower()
    _check_auth_action_limit(
        "auth.password_forgot",
        email,
        limit=settings.auth_email_rate_limit,
        window_seconds=settings.auth_email_rate_window_seconds,
    )
    user = db.scalar(select(User).where(User.email == email))
    if user:
        raw = _issue_one_time_token(db, user, "password_reset", settings)
        subject, body = account_email_copy(
            "password_reset",
            user.locale,
            f"{settings.web_url}/reset-password?token={raw}",
        )
        message = queue_email(
            db,
            user.email,
            subject,
            body,
        )
        db.commit()
        deliver_email(db, message, settings)
        db.commit()
    return MessageResponse(message="If the account exists, reset instructions will arrive shortly.")


@router.post("/auth/password/reset", response_model=MessageResponse, tags=["auth"])
def reset_password(payload: PasswordResetRequest, db: Db, settings: AppSettings) -> MessageResponse:
    _check_auth_action_limit(
        "auth.password_reset",
        payload.token,
        limit=settings.auth_token_rate_limit,
        window_seconds=settings.auth_token_rate_window_seconds,
    )
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


@router.get("/world/cities", response_model=list[CityView], tags=["world"])
def world_cities(db: Db, _: CurrentUser) -> list[CityView]:
    return [CityView.model_validate(city) for city in list_active_cities(db)]


@router.get(
    "/world/cities/{city_id}/districts",
    response_model=list[DistrictView],
    tags=["world"],
)
def city_districts(city_id: str, db: Db, _: CurrentUser) -> list[DistrictView]:
    return [DistrictView.model_validate(item) for item in list_city_districts(db, city_id)]


@router.post("/worlds/{world_id}/join", response_model=ProfileView, tags=["worlds"])
def join_world(
    world_id: str,
    payload: JoinWorldRequest,
    db: Db,
    user: CurrentUser,
    key: IdempotencyKey,
    settings: AppSettings,
) -> PlayerProfile:
    return join_world_service(
        db,
        user,
        world_id=world_id,
        codename=payload.codename,
        archetype=payload.archetype,
        home_district_id=payload.home_district_id,
        idempotency_key=key,
        settings=settings,
    )


@router.get("/profiles/me", response_model=ProfileView, tags=["profiles"])
def profile_me(profile: CurrentProfile) -> PlayerProfile:
    return profile


@router.get("/players/me", response_model=ProfileView, tags=["players"])
def player_me(profile: CurrentProfile) -> PlayerProfile:
    return profile


@router.post("/players/me/select-city", response_model=ProfileView, tags=["players"])
def player_select_city(
    payload: SelectCityRequest,
    db: Db,
    user: CurrentUser,
    key: IdempotencyKey,
    settings: AppSettings,
) -> PlayerProfile:
    return select_city(
        db,
        user,
        city_id=payload.city_id,
        codename=payload.codename,
        archetype=payload.archetype,
        home_district_id=payload.home_district_id,
        idempotency_key=key,
        settings=settings,
    )


@router.get("/players/me/resources", response_model=ResourceView, tags=["players"])
def player_resources(profile: CurrentProfile) -> ResourceView:
    return ResourceView.model_validate(profile.resources)


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


@router.get(
    "/companies/config",
    response_model=CompanyConfigurationView,
    tags=["companies"],
)
def companies_config(settings: AppSettings, _: CurrentProfile) -> dict[str, Any]:
    return company_configuration(settings)


@router.get("/companies", response_model=list[CompanyView], tags=["companies"])
def companies(db: Db, profile: CurrentProfile) -> list[Company]:
    return list_owned_companies(db, profile)


@router.post(
    "/companies",
    response_model=CompanyView,
    status_code=201,
    tags=["companies"],
)
def company_create(
    payload: CreateCompanyRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> Company:
    return create_company(
        db,
        profile,
        name=payload.name,
        industry=payload.industry,
        district_id=payload.district_id,
        idempotency_key=key,
        settings=settings,
        request_id=request_id(request),
    )


@router.get(
    "/companies/{company_id}",
    response_model=CompanyDetailView,
    tags=["companies"],
)
def company_detail(company_id: str, db: Db, profile: CurrentProfile) -> CompanyDetailView:
    company = get_company(db, profile, company_id)
    metrics, investments, ownership = company_history(db, company.id)
    return CompanyDetailView(
        **CompanyView.model_validate(company).model_dump(),
        ownership=[CompanyOwnershipView.model_validate(item) for item in ownership],
        investments=[CompanyInvestmentView.model_validate(item) for item in investments],
        metrics_history=[CompanyMetricView.model_validate(item) for item in metrics],
    )


@router.post(
    "/companies/{company_id}/investments",
    response_model=CompanyView,
    tags=["companies"],
)
def company_invest(
    company_id: str,
    payload: CompanyInvestmentRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Company:
    return invest_in_company(
        db,
        profile,
        company_id=company_id,
        investment_type=payload.investment_type,
        idempotency_key=key,
        request_id=request_id(request),
    )


@router.get(
    "/companies/{company_id}/ownership",
    response_model=list[CompanyOwnershipView],
    tags=["companies"],
)
def company_ownership(
    company_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[CompanyOwnershipView]:
    company = get_company(db, profile, company_id)
    _, _, ownership = company_history(db, company.id)
    return [CompanyOwnershipView.model_validate(item) for item in ownership]


@router.get(
    "/companies/{company_id}/specialist-effects",
    response_model=SpecialistEffectsView,
    tags=["companies", "specialists"],
)
def company_specialist_effect_summary(
    company_id: str,
    db: Db,
    profile: CurrentProfile,
) -> SpecialistEffectsView:
    get_company(db, profile, company_id)
    return SpecialistEffectsView(**company_specialist_effects(db, company_id).as_dict())


@router.get(
    "/companies/{company_id}/economy-reports",
    response_model=list[CompanyEconomyReportView],
    tags=["economy"],
)
def company_economy_reports(
    company_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=168)] = 24,
) -> list[CompanyEconomyReportView]:
    return [
        CompanyEconomyReportView.model_validate(report)
        for report in list_company_economy_reports(
            db,
            profile,
            company_id,
            limit=limit,
        )
    ]


@router.get(
    "/exchange/config",
    response_model=ExchangeConfigurationView,
    tags=["exchange"],
)
def exchange_config(
    settings: AppSettings,
    _profile: CurrentProfile,
) -> ExchangeConfigurationView:
    return ExchangeConfigurationView(**exchange_configuration(settings))


@router.get(
    "/companies/{company_id}/ipo-eligibility",
    response_model=IpoEligibilityView,
    tags=["companies", "exchange"],
)
def company_ipo_eligibility(
    company_id: str,
    db: Db,
    profile: CurrentProfile,
    settings: AppSettings,
) -> IpoEligibilityView:
    result = ipo_eligibility(db, profile, company_id, settings)
    return IpoEligibilityView(
        eligible=result.eligible,
        reasons=list(result.reasons),
        metrics=result.metrics,
    )


@router.post(
    "/companies/{company_id}/ipo",
    response_model=ExchangeListingView,
    status_code=201,
    tags=["companies", "exchange"],
)
def company_ipo(
    company_id: str,
    payload: CreateIpoRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> ExchangeListingView:
    listing = create_ipo(
        db,
        profile,
        company_id=company_id,
        symbol=payload.symbol,
        total_shares=payload.total_shares,
        offered_shares=payload.offered_shares,
        idempotency_key=key,
        request_id=request_id(request),
        settings=settings,
    )
    return ExchangeListingView.model_validate(listing)


@router.get(
    "/exchange/listings",
    response_model=list[ExchangeListingView],
    tags=["exchange"],
)
def exchange_listings(
    db: Db,
    profile: CurrentProfile,
) -> list[ExchangeListingView]:
    return [
        ExchangeListingView.model_validate(listing)
        for listing in list_exchange_listings(db, profile)
    ]


@router.get(
    "/exchange/listings/{listing_id}",
    response_model=ExchangeListingView,
    tags=["exchange"],
)
def exchange_listing_detail(
    listing_id: str,
    db: Db,
    profile: CurrentProfile,
) -> ExchangeListingView:
    return ExchangeListingView.model_validate(get_exchange_listing(db, profile, listing_id))


@router.get(
    "/exchange/listings/{listing_id}/order-book",
    response_model=ExchangeOrderBookView,
    tags=["exchange"],
)
def exchange_order_book(
    listing_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ExchangeOrderBookView:
    buys, sells = listing_order_book(db, profile, listing_id, limit=limit)
    return ExchangeOrderBookView(
        buys=[ExchangeOrderView.model_validate(order) for order in buys],
        sells=[ExchangeOrderView.model_validate(order) for order in sells],
    )


@router.get(
    "/exchange/listings/{listing_id}/trades",
    response_model=list[ExchangeTradeView],
    tags=["exchange"],
)
def exchange_trades(
    listing_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ExchangeTradeView]:
    return [
        ExchangeTradeView.model_validate(trade)
        for trade in listing_trades(db, profile, listing_id, limit=limit)
    ]


@router.get(
    "/exchange/listings/{listing_id}/prices",
    response_model=list[PriceSnapshotView],
    tags=["exchange"],
)
def exchange_price_history(
    listing_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=1_000)] = 200,
) -> list[PriceSnapshotView]:
    return [
        PriceSnapshotView.model_validate(snapshot)
        for snapshot in listing_price_history(db, profile, listing_id, limit=limit)
    ]


@router.get(
    "/exchange/listings/{listing_id}/shareholders",
    response_model=list[ShareholderView],
    tags=["exchange"],
)
def exchange_shareholders(
    listing_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ShareholderView]:
    return [
        ShareholderView.model_validate(shareholder)
        for shareholder in listing_shareholders(db, profile, listing_id, limit=limit)
    ]


@router.get(
    "/exchange/listings/{listing_id}/reports",
    response_model=list[CompanyEconomyReportView],
    tags=["exchange"],
)
def exchange_company_reports(
    listing_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=168)] = 24,
) -> list[CompanyEconomyReportView]:
    return [
        CompanyEconomyReportView.model_validate(report)
        for report in listing_company_reports(db, profile, listing_id, limit=limit)
    ]


@router.post(
    "/exchange/orders",
    response_model=ExchangeOrderView,
    status_code=201,
    tags=["exchange"],
)
def exchange_order_create(
    payload: ExchangeOrderRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> ExchangeOrderView:
    _check_trading_limit(profile.id, settings)
    order = place_order(
        db,
        profile,
        listing_id=payload.listing_id,
        side=payload.side,
        order_type=payload.order_type,
        quantity=payload.quantity,
        limit_price_cents=payload.limit_price_cents,
        expires_at=payload.expires_at,
        idempotency_key=key,
        request_id=request_id(request),
        settings=settings,
    )
    return ExchangeOrderView.model_validate(order)


@router.delete(
    "/exchange/orders/{order_id}",
    response_model=ExchangeOrderView,
    tags=["exchange"],
)
def exchange_order_cancel(
    order_id: str,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> ExchangeOrderView:
    _check_trading_limit(profile.id, settings)
    return ExchangeOrderView.model_validate(
        cancel_order(
            db,
            profile,
            order_id,
            idempotency_key=key,
            request_id=request_id(request),
        )
    )


@router.get(
    "/exchange/orders/me",
    response_model=list[ExchangeOrderView],
    tags=["exchange"],
)
def exchange_own_orders(
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[ExchangeOrderView]:
    return [
        ExchangeOrderView.model_validate(order)
        for order in list_profile_orders(db, profile, limit=limit)
    ]


@router.get(
    "/exchange/portfolio",
    response_model=list[PortfolioItemView],
    tags=["exchange"],
)
def exchange_portfolio(
    db: Db,
    profile: CurrentProfile,
) -> list[PortfolioItemView]:
    return [
        PortfolioItemView.model_validate(position) for position in profile_portfolio(db, profile)
    ]


@router.get(
    "/exchange/listings/{listing_id}/dividends",
    response_model=list[DividendDeclarationView],
    tags=["exchange"],
)
def exchange_dividends(
    listing_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[DividendDeclarationView]:
    return [
        DividendDeclarationView.model_validate(dividend)
        for dividend in list_dividends(db, profile, listing_id, limit=limit)
    ]


@router.post(
    "/companies/{company_id}/dividends",
    response_model=DividendDeclarationView,
    status_code=201,
    tags=["companies", "exchange"],
)
def company_dividend_declare(
    company_id: str,
    payload: DividendRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> DividendDeclarationView:
    listing = get_company_exchange_listing(db, profile, company_id)
    dividend = declare_dividend(
        db,
        profile,
        listing_id=listing.id,
        per_share_cents=payload.per_share_cents,
        idempotency_key=key,
        request_id=request_id(request),
    )
    return DividendDeclarationView.model_validate(dividend)


@router.get(
    "/economy/status",
    response_model=EconomyStatusView,
    tags=["economy"],
)
def economy_status(db: Db, profile: CurrentProfile) -> EconomyStatusView:
    last_tick = latest_economy_tick(db, profile.world_id)
    return EconomyStatusView(
        last_tick=(EconomyTickView.model_validate(last_tick) if last_tick is not None else None),
        next_scheduled_at=next_economy_tick_at(last_tick),
    )


@router.get(
    "/economy/markets",
    response_model=list[CitySectorMarketView],
    tags=["economy"],
)
def economy_markets(
    db: Db,
    profile: CurrentProfile,
) -> list[CitySectorMarketView]:
    return [
        CitySectorMarketView.model_validate(market)
        for market in list_city_sector_markets(db, profile)
    ]


@router.get(
    "/economy/competitors",
    response_model=list[CompanyView],
    tags=["economy"],
)
def economy_competitors(db: Db, profile: CurrentProfile) -> list[Company]:
    return list_local_companies(db, profile)


@router.get(
    "/economy/markets/{market_id}/reports",
    response_model=list[MarketEconomyReportView],
    tags=["economy"],
)
def economy_market_reports(
    market_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=168)] = 24,
) -> list[MarketEconomyReportView]:
    return [
        MarketEconomyReportView.model_validate(report)
        for report in list_market_economy_reports(
            db,
            profile,
            market_id,
            limit=limit,
        )
    ]


@router.post(
    "/admin/economy/ticks",
    response_model=EconomyTickView,
    tags=["admin", "economy"],
)
def economy_tick_manual(
    payload: ManualEconomyTickRequest,
    db: Db,
    _: Annotated[User, Depends(require_admin)],
) -> EconomyTickView:
    return EconomyTickView.model_validate(
        run_economy_tick(
            db,
            payload.world_id,
            at=payload.period_start,
        )
    )


@router.post(
    "/admin/specialists/payroll",
    response_model=SpecialistPayrollTickView,
    tags=["admin", "specialists"],
)
def specialist_payroll_manual(
    payload: ManualSpecialistPayrollRequest,
    db: Db,
    _: Annotated[User, Depends(require_admin)],
) -> SpecialistPayrollTickView:
    return SpecialistPayrollTickView.model_validate(
        run_specialist_payroll(
            db,
            payload.world_id,
            at=payload.period_start,
        )
    )


@router.get(
    "/admin/ai/players",
    response_model=list[AiProfileView],
    tags=["admin", "ai"],
)
def ai_players(
    db: Db,
    _: Annotated[User, Depends(require_admin)],
    world_id: str | None = None,
) -> list[AiProfileView]:
    return [AiProfileView.model_validate(profile) for profile in list_ai_profiles(db, world_id)]


@router.patch(
    "/admin/ai/players/{profile_id}",
    response_model=AiProfileView,
    tags=["admin", "ai"],
)
def ai_player_pause(
    profile_id: str,
    payload: AiPauseRequest,
    request: Request,
    db: Db,
    admin: Annotated[User, Depends(require_admin)],
) -> AiProfileView:
    return AiProfileView.model_validate(
        set_ai_paused(
            db,
            profile_id,
            paused=payload.paused,
            actor_user_id=admin.id,
            request_id=request_id(request),
        )
    )


@router.post(
    "/admin/ai/ticks",
    response_model=AiDecisionTickView,
    tags=["admin", "ai"],
)
def ai_tick_manual(
    payload: ManualAiTickRequest,
    db: Db,
    settings: AppSettings,
    _: Annotated[User, Depends(require_admin)],
) -> AiDecisionTickView:
    return AiDecisionTickView.model_validate(
        run_ai_tick(
            db,
            payload.world_id,
            settings=settings,
            at=payload.period_start,
        )
    )


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
    return list_profile_specialists(db, profile)


@router.get(
    "/specialist-market",
    response_model=list[SpecialistMarketCandidateView],
    tags=["specialists"],
)
def specialist_market(db: Db, profile: CurrentProfile) -> list[SpecialistMarketCandidateView]:
    candidates = list_market_candidates(db, profile)
    safe_commit(db)
    return [SpecialistMarketCandidateView.model_validate(candidate) for candidate in candidates]


@router.post(
    "/specialist-market/{candidate_id}/hire",
    response_model=SpecialistView,
    status_code=201,
    tags=["specialists"],
)
def specialist_hire(
    candidate_id: str,
    payload: HireSpecialistRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Specialist:
    return hire_specialist(
        db,
        profile,
        candidate_id=candidate_id,
        company_id=payload.company_id,
        idempotency_key=key,
        request_id=request_id(request),
    )


@router.post(
    "/specialists/{specialist_id}/assign",
    response_model=SpecialistView,
    tags=["specialists"],
)
def specialist_assign(
    specialist_id: str,
    payload: AssignSpecialistRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Specialist:
    return assign_specialist(
        db,
        profile,
        specialist_id=specialist_id,
        company_id=payload.company_id,
        idempotency_key=key,
        request_id=request_id(request),
    )


@router.post(
    "/specialists/{specialist_id}/release",
    response_model=SpecialistView,
    tags=["specialists"],
)
def specialist_release(
    specialist_id: str,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Specialist:
    return release_specialist(
        db,
        profile,
        specialist_id=specialist_id,
        idempotency_key=key,
        request_id=request_id(request),
    )


@router.get(
    "/specialists/{specialist_id}/payroll-reports",
    response_model=list[SpecialistPayrollReportView],
    tags=["specialists"],
)
def specialist_payroll_reports(
    specialist_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: Annotated[int, Query(ge=1, le=168)] = 24,
) -> list[SpecialistPayrollReportView]:
    return [
        SpecialistPayrollReportView.model_validate(report)
        for report in list_specialist_payroll_reports(
            db,
            profile,
            specialist_id,
            limit=limit,
        )
    ]


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
        city_id=profile.city_id,
        name=payload.name,
        tag=payload.tag.upper(),
        archetype=payload.archetype,
        description=payload.description,
        governance_model=payload.governance_model,
    )
    db.add(organization)
    db.flush()
    ensure_cartel_account(db, organization)
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
    instances = event_feed(db, profile.world_id)
    if instances:
        return [
            {
                "id": item.id,
                "event_key": item.event_key,
                "title": item.title,
                "description": item.description,
                "status": item.status,
                "scope_type": item.scope_type,
                "scope_id": item.scope_id,
                "effects": item.effect_config_json,
                "starts_at": item.starts_at,
                "ends_at": item.ends_at,
            }
            for item in instances
        ]
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
def notifications(
    db: Db,
    user: CurrentUser,
    unread_only: bool = False,
    category: Annotated[str | None, Query(pattern=r"^(critical|strategic|social|summary)$")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, Any]]:
    statement = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    if category is not None:
        statement = statement.where(Notification.category == category)
    return [
        {
            "id": item.id,
            "event_type": item.event_type,
            "category": item.category,
            "title": item.title,
            "body": item.body,
            "metadata_json": item.metadata_json,
            "read_at": item.read_at,
            "created_at": item.created_at,
        }
        for item in db.scalars(statement.order_by(Notification.created_at.desc()).limit(limit))
    ]


@router.get("/notifications/unread-count", tags=["notifications"])
def unread_notification_count(db: Db, user: CurrentUser) -> dict[str, int]:
    return {
        "unread_count": int(
            db.scalar(
                select(func.count())
                .select_from(Notification)
                .where(
                    Notification.user_id == user.id,
                    Notification.read_at.is_(None),
                )
            )
            or 0
        )
    }


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
    if item.read_at is None:
        item.read_at = datetime.now(UTC)
    db.commit()
    return MessageResponse(message="Notification marked as read.")


@router.post(
    "/notifications/read-all",
    response_model=MessageResponse,
    tags=["notifications"],
)
def read_all_notifications(db: Db, user: CurrentUser) -> MessageResponse:
    now = datetime.now(UTC)
    for item in db.scalars(
        select(Notification)
        .where(
            Notification.user_id == user.id,
            Notification.read_at.is_(None),
        )
        .with_for_update()
    ):
        item.read_at = now
    db.commit()
    return MessageResponse(message="All notifications marked as read.")


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
                "amount": str(item.amount),
                "balance_after": str(item.balance_after),
                "reason": item.reason,
                "created_at": item.created_at,
            }
            for item in db.scalars(
                select(LedgerEntry)
                .where(
                    LedgerEntry.owner_type == "profile",
                    LedgerEntry.owner_id.in_(profile_ids),
                )
                .order_by(LedgerEntry.created_at, LedgerEntry.id)
            )
        ],
    }


@router.delete("/privacy/account", response_model=MessageResponse, tags=["privacy"])
def delete_account(request: Request, db: Db, user: CurrentUser) -> MessageResponse:
    now = datetime.now(UTC)
    original_email = user.email
    pseudonym_email = f"deleted-{user.id}@shadowgrid.invalid"
    user.disabled_at = now
    user.email = pseudonym_email
    user.display_name = "Deleted player"
    user.locale = "en"
    user.email_verified = False
    user.password_hash = hash_password(secrets.token_urlsafe(48))
    user.totp_secret = None
    db.query(RefreshSession).filter(RefreshSession.user_id == user.id).update(
        {
            RefreshSession.revoked_at: now,
            RefreshSession.user_agent: "deleted-account",
        }
    )
    db.query(OneTimeToken).filter(OneTimeToken.user_id == user.id).update(
        {OneTimeToken.consumed_at: now}
    )
    db.query(EmailOutbox).filter(
        func.lower(EmailOutbox.recipient) == original_email.lower()
    ).update(
        {
            EmailOutbox.recipient: pseudonym_email,
            EmailOutbox.subject: "Deleted account email",
            EmailOutbox.body: "Content removed during account deletion.",
            EmailOutbox.status: "cancelled",
        }
    )
    db.query(OrganizationInvite).filter(
        func.lower(OrganizationInvite.email) == original_email.lower()
    ).update(
        {
            OrganizationInvite.email: pseudonym_email,
            OrganizationInvite.status: "revoked",
        }
    )
    audit(
        db,
        user.id,
        "privacy.account_pseudonymized",
        "user",
        user.id,
        request_id(request),
        {"direct_identifiers_removed": True, "sessions_revoked": True},
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
