from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from sqlalchemy import func, or_, select

from shadowgrid.dependencies import (
    AppSettings,
    CurrentProfile,
    CurrentUser,
    Db,
    IdempotencyKey,
    request_id,
)
from shadowgrid.domain import membership_with_permission, safe_commit
from shadowgrid.models import (
    Alliance,
    CartelWar,
    CartelWarEvent,
    CartelWarScore,
    ChatChannel,
    City,
    CityMarket,
    MarketOffer,
    MarketTrade,
    OrganizationMembership,
    PlayerMessage,
    PlayerProfile,
    PvpDefenseAction,
    PvpOperation,
    PvpOperationParticipant,
    PvpReport,
    PvpReputation,
    TerritoryHistory,
)
from shadowgrid.multiplayer_domain import (
    abandon_territory,
    accept_ceasefire,
    active_membership,
    advance_cartel_war,
    cancel_pvp_operation,
    claim_territory,
    commit_war_resources,
    contribute_territory,
    declare_cartel_war,
    defend_pvp_operation,
    get_or_create_reputation,
    join_cartel_war,
    launch_pvp_operation,
    launch_war_operation,
    offer_ceasefire,
    preview_pvp,
    propose_cartel_war,
    protection_for_profile,
    pvp_targets,
    resolve_pvp_operation,
    support_pvp_operation,
    surrender_cartel_war,
    territories,
    war_for_profile,
)
from shadowgrid.multiplayer_schemas import (
    AllianceCreateRequest,
    AllianceInviteRequest,
    AllianceTreatyRequest,
    AllianceView,
    CartelWarCommitRequest,
    CartelWarEventView,
    CartelWarJoinRequest,
    CartelWarOperationRequest,
    CartelWarProposeRequest,
    CartelWarScoreView,
    CartelWarView,
    CeasefireOfferRequest,
    ChatChannelView,
    ChatMessageCreate,
    ChatMessageView,
    CityMarketView,
    CityView,
    CriticalReauthRequest,
    DirectMessageCreate,
    DirectMessageView,
    MarketOfferCreate,
    MarketOfferView,
    MarketTradeView,
    ModerationReportCreate,
    PvpDefenseRequest,
    PvpOperationCreate,
    PvpOperationView,
    PvpPreviewRequest,
    PvpPreviewView,
    PvpProtectionView,
    PvpReportView,
    PvpReputationView,
    PvpSupportRequest,
    PvpTargetView,
    TerritoryChallengeRequest,
    TerritoryClaimRequest,
    TerritoryClaimView,
    TerritoryContributionRequest,
    TerritoryView,
    UserBlockRequest,
)
from shadowgrid.multiplayer_social import (
    accept_alliance_invitation,
    accept_market_offer,
    accessible_chat_channels,
    alliance_view,
    block_profile,
    channel_messages,
    create_alliance,
    create_alliance_treaty,
    create_market_offer,
    create_moderation_report,
    direct_messages,
    invite_cartel_to_alliance,
    leave_alliance,
    list_alliances,
    list_market_offers,
    send_chat_message,
    send_direct_message,
)
from shadowgrid.schemas import MessageResponse
from shadowgrid.security import verify_password

router = APIRouter()


def _operation_view(db: Db, operation: PvpOperation, profile: PlayerProfile) -> PvpOperationView:
    side = "attacker" if operation.attacker_profile_id == profile.id else "defender"
    submitted = bool(
        db.scalar(
            select(PvpDefenseAction.id).where(
                PvpDefenseAction.operation_id == operation.id,
                PvpDefenseAction.profile_id == profile.id,
            )
        )
    )
    report_id = operation.attacker_report_id if side == "attacker" else operation.defender_report_id
    return PvpOperationView.model_validate(operation).model_copy(
        update={
            "my_side": side,
            "defense_submitted": submitted,
            "my_report_id": report_id,
        }
    )


def _war_view(db: Db, war: CartelWar, profile: PlayerProfile) -> CartelWarView:
    membership = active_membership(db, profile.id)
    cartel_id = membership.organization_id if membership else None
    side: str | None = None
    if cartel_id == war.attacker_cartel_id:
        side = "attacker"
    elif cartel_id == war.defender_cartel_id:
        side = "defender"
    return CartelWarView.model_validate(war).model_copy(
        update={"my_cartel_id": cartel_id, "my_side": side}
    )


@router.get("/cities", response_model=list[CityView], tags=["multiplayer-world"])
def city_list(db: Db, profile: CurrentProfile) -> list[CityView]:
    cities = db.scalars(select(City).where(City.world_id == profile.world_id).order_by(City.name))
    views: list[CityView] = []
    for city in cities:
        players = (
            db.scalar(
                select(func.count())
                .select_from(PlayerProfile)
                .where(PlayerProfile.city_id == city.id)
            )
            or 0
        )
        cartels = (
            db.scalar(
                select(func.count(func.distinct(OrganizationMembership.organization_id)))
                .select_from(OrganizationMembership)
                .join(PlayerProfile, PlayerProfile.id == OrganizationMembership.profile_id)
                .where(
                    PlayerProfile.city_id == city.id,
                    OrganizationMembership.status == "active",
                )
            )
            or 0
        )
        views.append(
            CityView.model_validate(city).model_copy(
                update={"active_players": int(players), "active_cartels": int(cartels)}
            )
        )
    return views


@router.get(
    "/cities/{city_id}/market",
    response_model=list[CityMarketView],
    tags=["multiplayer-world"],
)
def city_market(city_id: str, db: Db, profile: CurrentProfile) -> list[CityMarket]:
    if city_id != profile.city_id:
        raise HTTPException(
            status_code=403,
            detail={"code": "city.access_denied", "message": "City market access denied"},
        )
    return list(
        db.scalars(
            select(CityMarket)
            .where(CityMarket.city_id == city_id)
            .order_by(CityMarket.resource_key)
        )
    )


@router.get("/pvp/targets", response_model=list[PvpTargetView], tags=["pvp"])
def pvp_target_list(db: Db, profile: CurrentProfile) -> list[PvpTargetView]:
    targets = pvp_targets(db, profile)
    safe_commit(db)
    return targets


@router.post("/pvp/preview", response_model=PvpPreviewView, tags=["pvp"])
def pvp_preview(payload: PvpPreviewRequest, db: Db, profile: CurrentProfile) -> PvpPreviewView:
    return preview_pvp(
        db,
        profile,
        payload.defender_profile_id,
        payload.operation_type,
        payload.district_id,
        payload.risk_posture,
    )


@router.post("/pvp/operations", response_model=PvpOperationView, status_code=201, tags=["pvp"])
def pvp_operation_create(
    payload: PvpOperationCreate,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
    settings: AppSettings,
) -> PvpOperationView:
    operation = launch_pvp_operation(
        db,
        user,
        profile,
        payload.defender_profile_id,
        payload.operation_type,
        payload.district_id,
        payload.risk_posture,
        key,
        request_id(request),
        settings,
    )
    safe_commit(db)
    db.refresh(operation)
    return _operation_view(db, operation, profile)


@router.get("/pvp/operations", response_model=list[PvpOperationView], tags=["pvp"])
def pvp_operation_list(db: Db, profile: CurrentProfile) -> list[PvpOperationView]:
    operations = db.scalars(
        select(PvpOperation)
        .where(
            PvpOperation.world_id == profile.world_id,
            or_(
                PvpOperation.attacker_profile_id == profile.id,
                PvpOperation.defender_profile_id == profile.id,
                PvpOperation.id.in_(
                    select(PvpOperationParticipant.operation_id).where(
                        PvpOperationParticipant.profile_id == profile.id
                    )
                ),
            ),
        )
        .order_by(PvpOperation.created_at.desc())
    )
    return [_operation_view(db, operation, profile) for operation in operations]


@router.get("/pvp/operations/{operation_id}", response_model=PvpOperationView, tags=["pvp"])
def pvp_operation_get(operation_id: str, db: Db, profile: CurrentProfile) -> PvpOperationView:
    operation = db.get(PvpOperation, operation_id)
    if operation is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "pvp.operation_not_found", "message": "PvP operation not found"},
        )
    if profile.id not in {
        operation.attacker_profile_id,
        operation.defender_profile_id,
    }:
        participant = db.scalar(
            select(PvpOperationParticipant.id).where(
                PvpOperationParticipant.operation_id == operation_id,
                PvpOperationParticipant.profile_id == profile.id,
            )
        )
        if participant is None:
            raise HTTPException(
                status_code=404,
                detail={"code": "pvp.operation_not_found", "message": "PvP operation not found"},
            )
    return _operation_view(db, operation, profile)


@router.post("/pvp/operations/{operation_id}/defend", response_model=PvpOperationView, tags=["pvp"])
def pvp_operation_defend(
    operation_id: str,
    payload: PvpDefenseRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> PvpOperationView:
    operation = defend_pvp_operation(
        db,
        user,
        profile,
        operation_id,
        payload.action_type,
        payload.commitment,
        request_id(request),
    )
    safe_commit(db)
    return _operation_view(db, operation, profile)


@router.post(
    "/pvp/operations/{operation_id}/support", response_model=PvpOperationView, tags=["pvp"]
)
def pvp_operation_support(
    operation_id: str,
    payload: PvpSupportRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> PvpOperationView:
    operation = support_pvp_operation(
        db,
        user,
        profile,
        operation_id,
        payload.side,
        payload.cash,
        payload.influence,
        key,
        request_id(request),
    )
    safe_commit(db)
    return _operation_view(db, operation, profile)


@router.post("/pvp/operations/{operation_id}/cancel", response_model=PvpOperationView, tags=["pvp"])
def pvp_operation_cancel(
    operation_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> PvpOperationView:
    operation = cancel_pvp_operation(db, user, profile, operation_id, request_id(request))
    safe_commit(db)
    return _operation_view(db, operation, profile)


@router.post(
    "/pvp/operations/{operation_id}/resolve", response_model=PvpOperationView, tags=["pvp"]
)
def pvp_operation_resolve(
    operation_id: str,
    db: Db,
    profile: CurrentProfile,
    settings: AppSettings,
) -> PvpOperationView:
    operation = db.scalar(
        select(PvpOperation).where(PvpOperation.id == operation_id).with_for_update()
    )
    if operation is None or profile.id not in {
        operation.attacker_profile_id,
        operation.defender_profile_id,
    }:
        raise HTTPException(
            status_code=404,
            detail={"code": "pvp.operation_not_found", "message": "PvP operation not found"},
        )
    if settings.app_env != "test" and operation.resolves_at > datetime.now(UTC):
        raise HTTPException(
            status_code=409,
            detail={"code": "pvp.not_due", "message": "Operation is not due for resolution"},
        )
    resolve_pvp_operation(db, operation, settings)
    safe_commit(db)
    return _operation_view(db, operation, profile)


@router.get("/pvp/reports/{report_id}", response_model=PvpReportView, tags=["pvp"])
def pvp_report(report_id: str, db: Db, profile: CurrentProfile) -> PvpReport:
    report = db.get(PvpReport, report_id)
    if report is None or report.profile_id != profile.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "pvp.report_not_found", "message": "PvP report not found"},
        )
    return report


@router.get("/pvp/protection", response_model=PvpProtectionView, tags=["pvp"])
def pvp_protection(db: Db, profile: CurrentProfile) -> PvpProtectionView:
    return protection_for_profile(db, profile)


@router.get("/pvp/reputation/{profile_id}", response_model=PvpReputationView, tags=["pvp"])
def pvp_reputation(profile_id: str, db: Db, profile: CurrentProfile) -> PvpReputation:
    target = db.get(PlayerProfile, profile_id)
    if target is None or target.world_id != profile.world_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "profile.not_found", "message": "Profile not found"},
        )
    reputation = get_or_create_reputation(db, target)
    safe_commit(db)
    return reputation


@router.get("/territories", response_model=list[TerritoryView], tags=["territories"])
def territory_list(db: Db, profile: CurrentProfile) -> list[TerritoryView]:
    return territories(db, profile)


@router.get("/territories/{district_id}", response_model=TerritoryView, tags=["territories"])
def territory_get(district_id: str, db: Db, profile: CurrentProfile) -> TerritoryView:
    item = next(
        (value for value in territories(db, profile) if value.district_id == district_id), None
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "territory.not_found", "message": "Territory not found"},
        )
    return item


@router.post(
    "/territories/{district_id}/claim",
    response_model=TerritoryClaimView,
    status_code=201,
    tags=["territories"],
)
def territory_claim(
    district_id: str,
    _payload: TerritoryClaimRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Any:
    claim = claim_territory(db, user, profile, district_id, key, request_id(request))
    safe_commit(db)
    return claim


@router.post(
    "/territories/{district_id}/support",
    response_model=TerritoryClaimView,
    tags=["territories"],
)
def territory_support(
    district_id: str,
    payload: TerritoryContributionRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Any:
    claim = contribute_territory(
        db,
        user,
        profile,
        district_id,
        payload.contribution_type,
        payload.amount,
        key,
        request_id(request),
    )
    safe_commit(db)
    return claim


@router.post(
    "/territories/{district_id}/challenge",
    response_model=TerritoryClaimView,
    tags=["territories"],
)
def territory_challenge(
    district_id: str,
    payload: TerritoryChallengeRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> Any:
    claim = contribute_territory(
        db,
        user,
        profile,
        district_id,
        "influence",
        payload.amount,
        key,
        request_id(request),
        challenge=True,
    )
    safe_commit(db)
    return claim


@router.post(
    "/territories/{district_id}/abandon",
    response_model=TerritoryClaimView,
    tags=["territories"],
)
def territory_abandon(
    district_id: str,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> Any:
    claim = abandon_territory(db, user, profile, district_id, request_id(request))
    safe_commit(db)
    return claim


@router.get("/territories/{district_id}/history", tags=["territories"])
def territory_history(district_id: str, db: Db, profile: CurrentProfile) -> list[dict[str, Any]]:
    history = db.scalars(
        select(TerritoryHistory)
        .where(
            TerritoryHistory.world_id == profile.world_id,
            TerritoryHistory.district_id == district_id,
        )
        .order_by(TerritoryHistory.created_at.desc())
        .limit(100)
    )
    return [
        {
            "id": item.id,
            "event_type": item.event_type,
            "previous_cartel_id": item.previous_cartel_id,
            "new_cartel_id": item.new_cartel_id,
            "payload": item.payload_json,
            "created_at": item.created_at,
        }
        for item in history
    ]


@router.get("/cartel-wars", response_model=list[CartelWarView], tags=["cartel-wars"])
def cartel_war_list(db: Db, profile: CurrentProfile) -> list[CartelWarView]:
    wars = list(
        db.scalars(
            select(CartelWar)
            .where(CartelWar.world_id == profile.world_id)
            .order_by(CartelWar.created_at.desc())
        )
    )
    for war in wars:
        advance_cartel_war(db, war)
    safe_commit(db)
    return [_war_view(db, war, profile) for war in wars]


@router.post(
    "/cartel-wars/propose",
    response_model=CartelWarView,
    status_code=201,
    tags=["cartel-wars"],
)
def cartel_war_propose(
    payload: CartelWarProposeRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> CartelWarView:
    war = propose_cartel_war(
        db,
        user,
        profile,
        payload.defender_cartel_id,
        payload.war_type,
        payload.city_id,
        payload.district_id,
        payload.declaration_reason,
        payload.demand,
        payload.peace_conditions,
        request_id(request),
    )
    safe_commit(db)
    return _war_view(db, war, profile)


@router.post("/cartel-wars/{war_id}/declare", response_model=CartelWarView, tags=["cartel-wars"])
def cartel_war_declare(
    war_id: str,
    payload: CriticalReauthRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    settings: AppSettings,
) -> CartelWarView:
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "auth.reauthentication_failed",
                "message": "Recent authentication required",
            },
        )
    war = declare_cartel_war(db, user, profile, war_id, request_id(request), settings)
    safe_commit(db)
    return _war_view(db, war, profile)


@router.get("/cartel-wars/{war_id}", response_model=CartelWarView, tags=["cartel-wars"])
def cartel_war_get(war_id: str, db: Db, profile: CurrentProfile) -> CartelWarView:
    war = db.get(CartelWar, war_id)
    if war is None or war.world_id != profile.world_id:
        raise HTTPException(
            status_code=404, detail={"code": "war.not_found", "message": "Cartel war not found"}
        )
    advance_cartel_war(db, war)
    safe_commit(db)
    return _war_view(db, war, profile)


@router.post("/cartel-wars/{war_id}/join", tags=["cartel-wars"])
def cartel_war_join(
    war_id: str, payload: CartelWarJoinRequest, db: Db, profile: CurrentProfile
) -> dict[str, Any]:
    participant = join_cartel_war(db, profile, war_id, payload.side)
    safe_commit(db)
    return {
        "participant_id": participant.id,
        "war_id": participant.war_id,
        "side": participant.side,
        "status": participant.status,
    }


@router.post(
    "/cartel-wars/{war_id}/commit-resources",
    response_model=CartelWarView,
    tags=["cartel-wars"],
)
def cartel_war_commit(
    war_id: str,
    payload: CartelWarCommitRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> CartelWarView:
    war = commit_war_resources(
        db,
        user,
        profile,
        war_id,
        payload.resource_type,
        payload.amount,
        key,
        request_id(request),
    )
    safe_commit(db)
    return _war_view(db, war, profile)


@router.post("/cartel-wars/{war_id}/launch-operation", tags=["cartel-wars"])
def cartel_war_operation(
    war_id: str,
    payload: CartelWarOperationRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> dict[str, Any]:
    operation = launch_war_operation(
        db,
        user,
        profile,
        war_id,
        payload.operation_type,
        payload.district_id,
        payload.cash,
        payload.influence,
        key,
        request_id(request),
    )
    safe_commit(db)
    return {
        "id": operation.id,
        "war_id": operation.war_id,
        "operation_type": operation.operation_type,
        "score_delta": operation.score_delta,
        "status": operation.status,
    }


@router.post("/cartel-wars/{war_id}/offer-ceasefire", tags=["cartel-wars"])
def cartel_war_offer_ceasefire(
    war_id: str, payload: CeasefireOfferRequest, db: Db, profile: CurrentProfile
) -> dict[str, Any]:
    treaty = offer_ceasefire(db, profile, war_id, payload.terms)
    safe_commit(db)
    return {"treaty_id": treaty.id, "status": treaty.status}


@router.post("/cartel-wars/{war_id}/accept-ceasefire", tags=["cartel-wars"])
def cartel_war_accept_ceasefire(war_id: str, db: Db, profile: CurrentProfile) -> dict[str, Any]:
    treaty = accept_ceasefire(db, profile, war_id)
    safe_commit(db)
    return {"treaty_id": treaty.id, "status": treaty.status}


@router.post("/cartel-wars/{war_id}/surrender", response_model=CartelWarView, tags=["cartel-wars"])
def cartel_war_surrender(
    war_id: str,
    payload: CriticalReauthRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> CartelWarView:
    if not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "auth.reauthentication_failed",
                "message": "Recent authentication required",
            },
        )
    war = surrender_cartel_war(db, profile, war_id)
    safe_commit(db)
    return _war_view(db, war, profile)


@router.get(
    "/cartel-wars/{war_id}/score",
    response_model=list[CartelWarScoreView],
    tags=["cartel-wars"],
)
def cartel_war_score(war_id: str, db: Db, profile: CurrentProfile) -> list[CartelWarScore]:
    war_for_profile(db, war_id, profile)
    return list(
        db.scalars(
            select(CartelWarScore)
            .where(CartelWarScore.war_id == war_id)
            .order_by(CartelWarScore.total.desc())
        )
    )


@router.get(
    "/cartel-wars/{war_id}/events",
    response_model=list[CartelWarEventView],
    tags=["cartel-wars"],
)
def cartel_war_events(war_id: str, db: Db, profile: CurrentProfile) -> list[CartelWarEvent]:
    war = db.get(CartelWar, war_id)
    if war is None or war.world_id != profile.world_id:
        raise HTTPException(
            status_code=404, detail={"code": "war.not_found", "message": "Cartel war not found"}
        )
    return list(
        db.scalars(
            select(CartelWarEvent)
            .where(CartelWarEvent.war_id == war_id)
            .order_by(CartelWarEvent.created_at.desc())
            .limit(200)
        )
    )


@router.get("/cartel-wars/{war_id}/reports", tags=["cartel-wars"])
def cartel_war_reports(war_id: str, db: Db, profile: CurrentProfile) -> list[dict[str, Any]]:
    membership = membership_with_permission(db, profile.id, "wars.view_reports")
    war = war_for_profile(db, war_id, profile)
    return [
        {
            "id": item.id,
            "event_type": item.event_type,
            "public": item.public_payload,
            "cartel_private": item.private_payload
            if item.actor_cartel_id == membership.organization_id
            else {},
            "created_at": item.created_at,
        }
        for item in db.scalars(
            select(CartelWarEvent)
            .where(CartelWarEvent.war_id == war.id)
            .order_by(CartelWarEvent.created_at.desc())
        )
    ]


@router.get("/alliances", response_model=list[AllianceView], tags=["alliances"])
def alliance_list(db: Db, profile: CurrentProfile) -> list[AllianceView]:
    return list_alliances(db, profile)


@router.post("/alliances", response_model=AllianceView, status_code=201, tags=["alliances"])
def alliance_create(
    payload: AllianceCreateRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> AllianceView:
    alliance = create_alliance(
        db,
        user,
        profile,
        payload.name,
        payload.tag,
        payload.charter,
        payload.governance_model,
        request_id(request),
    )
    safe_commit(db)
    return alliance_view(db, alliance, profile)


@router.get("/alliances/{alliance_id}", response_model=AllianceView, tags=["alliances"])
def alliance_get(alliance_id: str, db: Db, profile: CurrentProfile) -> AllianceView:
    alliance = db.get(Alliance, alliance_id)
    if alliance is None or alliance.world_id != profile.world_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "alliance.not_found", "message": "Alliance not found"},
        )
    return alliance_view(db, alliance, profile)


@router.post("/alliances/{alliance_id}/invite", tags=["alliances"])
def alliance_invite(
    alliance_id: str,
    payload: AllianceInviteRequest,
    db: Db,
    profile: CurrentProfile,
) -> MessageResponse:
    invite_cartel_to_alliance(
        db, profile, alliance_id, payload.cartel_id, payload.contribution_limit
    )
    safe_commit(db)
    return MessageResponse(message="Alliance invitation created.")


@router.post("/alliances/{alliance_id}/accept", tags=["alliances"])
def alliance_accept(alliance_id: str, db: Db, profile: CurrentProfile) -> MessageResponse:
    accept_alliance_invitation(db, profile, alliance_id)
    safe_commit(db)
    return MessageResponse(message="Alliance invitation accepted.")


@router.post("/alliances/{alliance_id}/leave", tags=["alliances"])
def alliance_leave(alliance_id: str, db: Db, profile: CurrentProfile) -> MessageResponse:
    leave_alliance(db, profile, alliance_id)
    safe_commit(db)
    return MessageResponse(message="Alliance departure scheduled.")


@router.post("/alliances/{alliance_id}/treaties", tags=["alliances"])
def alliance_treaty_create(
    alliance_id: str,
    payload: AllianceTreatyRequest,
    db: Db,
    profile: CurrentProfile,
) -> dict[str, Any]:
    treaty = create_alliance_treaty(
        db,
        profile,
        alliance_id,
        payload.treaty_type,
        payload.counterparty_type,
        payload.counterparty_id,
        payload.duration_days,
        payload.terms,
    )
    safe_commit(db)
    return {"id": treaty.id, "status": treaty.status, "expires_at": treaty.expires_at}


@router.get("/chat/channels", response_model=list[ChatChannelView], tags=["chat"])
def chat_channel_list(db: Db, profile: CurrentProfile) -> list[ChatChannel]:
    channels = accessible_chat_channels(db, profile)
    safe_commit(db)
    return channels


@router.get(
    "/chat/channels/{channel_id}/messages",
    response_model=list[ChatMessageView],
    tags=["chat"],
)
def chat_message_list(
    channel_id: str,
    db: Db,
    profile: CurrentProfile,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[Any]:
    return channel_messages(db, profile, channel_id, limit)


@router.post(
    "/chat/channels/{channel_id}/messages",
    response_model=ChatMessageView,
    status_code=201,
    tags=["chat"],
)
def chat_message_create(
    channel_id: str,
    payload: ChatMessageCreate,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> Any:
    message = send_chat_message(db, user, profile, channel_id, payload.body)
    safe_commit(db)
    return message


@router.get("/messages", response_model=list[DirectMessageView], tags=["chat"])
def direct_message_list(db: Db, profile: CurrentProfile) -> list[PlayerMessage]:
    return direct_messages(db, profile)


@router.post("/messages", response_model=DirectMessageView, status_code=201, tags=["chat"])
def direct_message_create(
    payload: DirectMessageCreate, db: Db, profile: CurrentProfile
) -> PlayerMessage:
    message = send_direct_message(db, profile, payload.recipient_profile_id, payload.body)
    safe_commit(db)
    return message


@router.post("/blocks", tags=["chat"])
def user_block_create(payload: UserBlockRequest, db: Db, user: CurrentUser) -> MessageResponse:
    block_profile(db, user, payload.blocked_profile_id)
    safe_commit(db)
    return MessageResponse(message="Profile blocked.")


@router.post("/moderation/reports", status_code=201, tags=["moderation"])
def moderation_report_create(
    payload: ModerationReportCreate,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
) -> MessageResponse:
    create_moderation_report(
        db,
        user,
        profile,
        payload.target_type,
        payload.target_id,
        payload.category,
        payload.description,
    )
    safe_commit(db)
    return MessageResponse(message="Report submitted for manual review.")


@router.get("/market/offers", response_model=list[MarketOfferView], tags=["market"])
def market_offer_list(db: Db, profile: CurrentProfile) -> list[MarketOffer]:
    return list_market_offers(db, profile)


@router.post("/market/offers", response_model=MarketOfferView, status_code=201, tags=["market"])
def market_offer_create(
    payload: MarketOfferCreate,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> MarketOffer:
    offer = create_market_offer(
        db,
        profile,
        payload.resource_type,
        payload.amount,
        payload.unit_price,
        key,
    )
    safe_commit(db)
    return offer


@router.post(
    "/market/offers/{offer_id}/accept",
    response_model=MarketTradeView,
    tags=["market"],
)
def market_offer_accept(
    offer_id: str,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> MarketTrade:
    trade = accept_market_offer(db, profile, offer_id, key)
    safe_commit(db)
    return trade
