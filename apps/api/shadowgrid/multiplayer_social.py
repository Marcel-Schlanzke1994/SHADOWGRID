from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from shadowgrid.domain import apply_profile_resource, as_decimal, audit, membership_with_permission
from shadowgrid.models import (
    Alliance,
    AllianceMembership,
    AllianceRole,
    AllianceTreaty,
    AntiCheatRiskEvent,
    CartelWarParticipant,
    ChatChannel,
    ChatMembership,
    ChatMessage,
    CityMarket,
    MarketOffer,
    MarketTrade,
    ModerationReport,
    Organization,
    OrganizationMembership,
    PlayerMessage,
    PlayerProfile,
    User,
    UserBlock,
    as_utc,
)
from shadowgrid.multiplayer_domain import active_membership, emit_realtime
from shadowgrid.multiplayer_schemas import AllianceView


def alliance_view(db: Session, alliance: Alliance, profile: PlayerProfile) -> AllianceView:
    cartel_membership = active_membership(db, profile.id)
    alliance_membership = (
        db.scalar(
            select(AllianceMembership).where(
                AllianceMembership.alliance_id == alliance.id,
                AllianceMembership.cartel_id == cartel_membership.organization_id,
            )
        )
        if cartel_membership
        else None
    )
    count = (
        db.scalar(
            select(func.count())
            .select_from(AllianceMembership)
            .where(
                AllianceMembership.alliance_id == alliance.id,
                AllianceMembership.status == "active",
            )
        )
        or 0
    )
    return AllianceView.model_validate(alliance).model_copy(
        update={
            "member_count": int(count),
            "my_cartel_id": cartel_membership.organization_id if cartel_membership else None,
            "my_role": alliance_membership.role
            if alliance_membership and alliance_membership.status == "active"
            else None,
        }
    )


def list_alliances(db: Session, profile: PlayerProfile) -> list[AllianceView]:
    return [
        alliance_view(db, alliance, profile)
        for alliance in db.scalars(
            select(Alliance)
            .where(Alliance.world_id == profile.world_id, Alliance.status == "active")
            .order_by(Alliance.name)
        )
    ]


def create_alliance(
    db: Session,
    user: User,
    profile: PlayerProfile,
    name: str,
    tag: str,
    charter: str,
    governance_model: str,
    request_id: str,
) -> Alliance:
    cartel = membership_with_permission(db, profile.id, "alliances.propose")
    existing = db.scalar(
        select(AllianceMembership).where(
            AllianceMembership.cartel_id == cartel.organization_id,
            AllianceMembership.status.in_(("active", "invited", "leaving")),
        )
    )
    if existing:
        raise HTTPException(
            status_code=409,
            detail={"code": "alliance.already_member", "message": "Cartel already has an alliance"},
        )
    alliance = Alliance(
        world_id=profile.world_id,
        name=name,
        tag=tag.upper(),
        charter=charter,
        governance_model=governance_model,
    )
    db.add(alliance)
    db.flush()
    db.add_all(
        [
            AllianceMembership(
                world_id=profile.world_id,
                alliance_id=alliance.id,
                cartel_id=cartel.organization_id,
                status="active",
                role="chair",
                joined_at=datetime.now(UTC),
            ),
            AllianceRole(
                world_id=profile.world_id,
                alliance_id=alliance.id,
                role_key="chair",
                permissions_json=["*"],
            ),
            AllianceRole(
                world_id=profile.world_id,
                alliance_id=alliance.id,
                role_key="member",
                permissions_json=["alliances.view", "alliances.support"],
            ),
        ]
    )
    audit(
        db,
        user.id,
        "alliance.created",
        "alliance",
        alliance.id,
        request_id,
        {"founding_cartel_id": cartel.organization_id},
    )
    return alliance


def _actor_alliance_membership(
    db: Session, profile: PlayerProfile, alliance_id: str, *, require_chair: bool = False
) -> tuple[OrganizationMembership, AllianceMembership]:
    cartel = active_membership(db, profile.id)
    if cartel is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "alliance.cartel_required", "message": "Cartel membership required"},
        )
    membership = db.scalar(
        select(AllianceMembership).where(
            AllianceMembership.alliance_id == alliance_id,
            AllianceMembership.cartel_id == cartel.organization_id,
            AllianceMembership.status == "active",
        )
    )
    if membership is None or (require_chair and membership.role != "chair"):
        raise HTTPException(
            status_code=403,
            detail={"code": "alliance.permission_denied", "message": "Alliance permission denied"},
        )
    return cartel, membership


def invite_cartel_to_alliance(
    db: Session,
    profile: PlayerProfile,
    alliance_id: str,
    invited_cartel_id: str,
    contribution_limit: Decimal,
) -> AllianceMembership:
    cartel, _ = _actor_alliance_membership(db, profile, alliance_id, require_chair=True)
    alliance = db.scalar(select(Alliance).where(Alliance.id == alliance_id).with_for_update())
    invited = db.get(Organization, invited_cartel_id)
    if alliance is None or invited is None or invited.world_id != profile.world_id:
        raise HTTPException(
            status_code=404,
            detail={"code": "alliance.not_found", "message": "Alliance or cartel not found"},
        )
    count = (
        db.scalar(
            select(func.count())
            .select_from(AllianceMembership)
            .where(
                AllianceMembership.alliance_id == alliance.id,
                AllianceMembership.status.in_(("active", "invited")),
            )
        )
        or 0
    )
    if count >= alliance.member_limit:
        raise HTTPException(
            status_code=409,
            detail={"code": "alliance.member_limit", "message": "Alliance member limit reached"},
        )
    existing = db.scalar(
        select(AllianceMembership).where(
            AllianceMembership.alliance_id == alliance.id,
            AllianceMembership.cartel_id == invited.id,
        )
    )
    if existing:
        return existing
    membership = AllianceMembership(
        world_id=profile.world_id,
        alliance_id=alliance.id,
        cartel_id=invited.id,
        status="invited",
        role="member",
        contribution_limit=contribution_limit,
        invited_by_cartel_id=cartel.organization_id,
    )
    db.add(membership)
    target_profiles = list(
        db.scalars(
            select(OrganizationMembership.profile_id).where(
                OrganizationMembership.organization_id == invited.id,
                OrganizationMembership.status == "active",
            )
        )
    )
    emit_realtime(
        db,
        profile.world_id,
        "alliance.invitation_received",
        {"alliance_id": alliance.id},
        target_profiles,
    )
    return membership


def accept_alliance_invitation(
    db: Session, profile: PlayerProfile, alliance_id: str
) -> AllianceMembership:
    cartel = membership_with_permission(db, profile.id, "alliances.accept")
    membership = db.scalar(
        select(AllianceMembership)
        .where(
            AllianceMembership.alliance_id == alliance_id,
            AllianceMembership.cartel_id == cartel.organization_id,
            AllianceMembership.status == "invited",
        )
        .with_for_update()
    )
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "alliance.invitation_not_found", "message": "Invitation not found"},
        )
    membership.status = "active"
    membership.joined_at = datetime.now(UTC)
    emit_realtime(
        db,
        profile.world_id,
        "alliance.member_joined",
        {"alliance_id": alliance_id, "cartel_id": cartel.organization_id},
    )
    return membership


def leave_alliance(db: Session, profile: PlayerProfile, alliance_id: str) -> AllianceMembership:
    cartel = membership_with_permission(db, profile.id, "alliances.terminate")
    membership = db.scalar(
        select(AllianceMembership)
        .where(
            AllianceMembership.alliance_id == alliance_id,
            AllianceMembership.cartel_id == cartel.organization_id,
            AllianceMembership.status == "active",
        )
        .with_for_update()
    )
    if membership is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "alliance.membership_not_found", "message": "Membership not found"},
        )
    if membership.role == "chair":
        other = db.scalar(
            select(AllianceMembership).where(
                AllianceMembership.alliance_id == alliance_id,
                AllianceMembership.status == "active",
                AllianceMembership.id != membership.id,
            )
        )
        if other is None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "alliance.chair_transfer_required",
                    "message": "Invite another cartel before the founding chair leaves",
                },
            )
        other.role = "chair"
    membership.status = "leaving"
    membership.leave_effective_at = datetime.now(UTC) + timedelta(hours=24)
    return membership


def create_alliance_treaty(
    db: Session,
    profile: PlayerProfile,
    alliance_id: str,
    treaty_type: str,
    counterparty_type: str,
    counterparty_id: str,
    duration_days: int,
    terms: dict[str, Any],
) -> AllianceTreaty:
    _actor_alliance_membership(db, profile, alliance_id, require_chair=True)
    treaty = AllianceTreaty(
        world_id=profile.world_id,
        alliance_id=alliance_id,
        treaty_type=treaty_type,
        counterparty_type=counterparty_type,
        counterparty_id=counterparty_id,
        terms_json=terms,
        status="active",
        starts_at=datetime.now(UTC),
        expires_at=datetime.now(UTC) + timedelta(days=duration_days),
    )
    db.add(treaty)
    emit_realtime(
        db,
        profile.world_id,
        "alliance.treaty_changed",
        {"alliance_id": alliance_id, "treaty_type": treaty_type},
    )
    return treaty


def _ensure_channel(
    db: Session,
    profile: PlayerProfile,
    channel_type: str,
    scope_id: str,
    name: str,
) -> ChatChannel:
    channel = db.scalar(
        select(ChatChannel).where(
            ChatChannel.world_id == profile.world_id,
            ChatChannel.channel_type == channel_type,
            ChatChannel.scope_id == scope_id,
        )
    )
    if channel is None:
        channel = ChatChannel(
            world_id=profile.world_id,
            channel_type=channel_type,
            scope_id=scope_id,
            name=name,
        )
        db.add(channel)
        db.flush()
    membership = db.scalar(
        select(ChatMembership).where(
            ChatMembership.channel_id == channel.id,
            ChatMembership.profile_id == profile.id,
        )
    )
    if membership is None:
        db.add(
            ChatMembership(
                world_id=profile.world_id,
                channel_id=channel.id,
                profile_id=profile.id,
            )
        )
    return channel


def accessible_chat_channels(db: Session, profile: PlayerProfile) -> list[ChatChannel]:
    channels: list[ChatChannel] = []
    if profile.city_id:
        channels.append(
            _ensure_channel(db, profile, "city", profile.city_id, "Metropolitan coordination")
        )
    cartel = active_membership(db, profile.id)
    if cartel:
        channels.append(
            _ensure_channel(db, profile, "cartel", cartel.organization_id, "Cartel channel")
        )
        alliance_membership = db.scalar(
            select(AllianceMembership).where(
                AllianceMembership.cartel_id == cartel.organization_id,
                AllianceMembership.status == "active",
            )
        )
        if alliance_membership:
            channels.append(
                _ensure_channel(
                    db,
                    profile,
                    "alliance",
                    alliance_membership.alliance_id,
                    "Alliance channel",
                )
            )
        for war_id in db.scalars(
            select(CartelWarParticipant.war_id).where(
                CartelWarParticipant.profile_id == profile.id,
                CartelWarParticipant.status == "active",
            )
        ):
            channels.append(_ensure_channel(db, profile, "war", war_id, "War room"))
    return channels


def _moderation_state(body: str) -> tuple[str, int]:
    normalized = body.casefold()
    real_threat_markers = (
        "real address",
        "private address",
        "doxx",
        "outside the game",
        "in real life",
        "real weapon",
    )
    if any(marker in normalized for marker in real_threat_markers):
        return "held", 90
    spam_score = max(0, body.count("http://") + body.count("https://") - 1) * 20
    return ("review", min(70, spam_score)) if spam_score else ("visible", 0)


def send_chat_message(
    db: Session,
    user: User,
    profile: PlayerProfile,
    channel_id: str,
    body: str,
) -> ChatMessage:
    membership = db.scalar(
        select(ChatMembership).where(
            ChatMembership.channel_id == channel_id,
            ChatMembership.profile_id == profile.id,
        )
    )
    if membership is None:
        accessible_chat_channels(db, profile)
        db.flush()
        membership = db.scalar(
            select(ChatMembership).where(
                ChatMembership.channel_id == channel_id,
                ChatMembership.profile_id == profile.id,
            )
        )
    now = datetime.now(UTC)
    if membership is None or (
        membership.muted_until is not None and as_utc(membership.muted_until) > now
    ):
        raise HTTPException(
            status_code=403,
            detail={"code": "chat.access_denied", "message": "Channel access denied"},
        )
    recent = (
        db.scalar(
            select(func.count())
            .select_from(ChatMessage)
            .where(
                ChatMessage.sender_profile_id == profile.id,
                ChatMessage.created_at > now - timedelta(minutes=1),
            )
        )
        or 0
    )
    if recent >= 15:
        db.add(
            AntiCheatRiskEvent(
                world_id=profile.world_id,
                profile_id=profile.id,
                event_type="chat_rate_pattern",
                risk_score=25,
                evidence_json={"window_seconds": 60, "message_count": int(recent)},
            )
        )
        raise HTTPException(
            status_code=429,
            detail={"code": "chat.rate_limited", "message": "Message rate limit reached"},
        )
    moderation_state, risk = _moderation_state(body)
    stored_body = body if moderation_state == "visible" else "Message held for moderator review."
    message = ChatMessage(
        world_id=profile.world_id,
        channel_id=channel_id,
        sender_profile_id=profile.id,
        body=stored_body,
        moderation_state=moderation_state,
    )
    db.add(message)
    db.flush()
    if risk:
        db.add(
            ModerationReport(
                world_id=profile.world_id,
                reporter_user_id=None,
                target_user_id=user.id,
                target_type="chat_message",
                target_id=message.id,
                category="automated_safety_review",
                description="Automated multiplayer safety rule matched; original content was not retained.",
                risk_score=risk,
            )
        )
    if moderation_state == "visible":
        recipients = list(
            db.scalars(
                select(ChatMembership.profile_id).where(ChatMembership.channel_id == channel_id)
            )
        )
        emit_realtime(
            db,
            profile.world_id,
            "chat.message_created",
            {"channel_id": channel_id, "message_id": message.id},
            recipients,
        )
    else:
        emit_realtime(
            db,
            profile.world_id,
            "chat.moderation_action",
            {"channel_id": channel_id, "message_id": message.id},
            [profile.id],
        )
    return message


def channel_messages(
    db: Session, profile: PlayerProfile, channel_id: str, limit: int = 100
) -> list[ChatMessage]:
    membership = db.scalar(
        select(ChatMembership).where(
            ChatMembership.channel_id == channel_id,
            ChatMembership.profile_id == profile.id,
        )
    )
    if membership is None:
        raise HTTPException(
            status_code=403,
            detail={"code": "chat.access_denied", "message": "Channel access denied"},
        )
    return list(
        db.scalars(
            select(ChatMessage)
            .where(
                ChatMessage.channel_id == channel_id,
                ChatMessage.moderation_state == "visible",
                ChatMessage.deleted_at.is_(None),
            )
            .order_by(ChatMessage.created_at.desc())
            .limit(limit)
        )
    )[::-1]


def send_direct_message(
    db: Session,
    profile: PlayerProfile,
    recipient_profile_id: str,
    body: str,
) -> PlayerMessage:
    recipient = db.get(PlayerProfile, recipient_profile_id)
    if recipient is None or recipient.world_id != profile.world_id or recipient.id == profile.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "message.recipient_not_found", "message": "Recipient not found"},
        )
    block = db.scalar(
        select(UserBlock).where(
            or_(
                (UserBlock.blocker_user_id == recipient.user_id)
                & (UserBlock.blocked_user_id == profile.user_id),
                (UserBlock.blocker_user_id == profile.user_id)
                & (UserBlock.blocked_user_id == recipient.user_id),
            )
        )
    )
    if block:
        raise HTTPException(
            status_code=403,
            detail={"code": "message.blocked", "message": "Direct messaging is unavailable"},
        )
    state, risk = _moderation_state(body)
    stored_body = body if state == "visible" else "Message held for moderator review."
    message = PlayerMessage(
        world_id=profile.world_id,
        sender_profile_id=profile.id,
        recipient_profile_id=recipient.id,
        body=stored_body,
        status="delivered" if state == "visible" else "held",
    )
    db.add(message)
    db.flush()
    if risk:
        db.add(
            ModerationReport(
                world_id=profile.world_id,
                reporter_user_id=None,
                target_user_id=profile.user_id,
                target_type="direct_message",
                target_id=message.id,
                category="automated_safety_review",
                description="Automated multiplayer safety rule matched; original content was not retained.",
                risk_score=risk,
            )
        )
    if state == "visible":
        emit_realtime(
            db,
            profile.world_id,
            "chat.message_created",
            {"direct_message_id": message.id},
            [recipient.id],
        )
    return message


def direct_messages(db: Session, profile: PlayerProfile) -> list[PlayerMessage]:
    return list(
        db.scalars(
            select(PlayerMessage)
            .where(
                or_(
                    PlayerMessage.sender_profile_id == profile.id,
                    PlayerMessage.recipient_profile_id == profile.id,
                ),
                PlayerMessage.status != "held",
            )
            .order_by(PlayerMessage.created_at.desc())
            .limit(200)
        )
    )


def block_profile(db: Session, user: User, blocked_profile_id: str) -> UserBlock:
    blocked = db.get(PlayerProfile, blocked_profile_id)
    if blocked is None or blocked.user_id == user.id:
        raise HTTPException(
            status_code=404,
            detail={"code": "block.profile_not_found", "message": "Profile not found"},
        )
    existing = db.scalar(
        select(UserBlock).where(
            UserBlock.blocker_user_id == user.id,
            UserBlock.blocked_user_id == blocked.user_id,
        )
    )
    if existing:
        return existing
    block = UserBlock(blocker_user_id=user.id, blocked_user_id=blocked.user_id)
    db.add(block)
    return block


def create_moderation_report(
    db: Session,
    user: User,
    profile: PlayerProfile,
    target_type: str,
    target_id: str,
    category: str,
    description: str,
) -> ModerationReport:
    report = ModerationReport(
        world_id=profile.world_id,
        reporter_user_id=user.id,
        target_user_id=None,
        target_type=target_type,
        target_id=target_id,
        category=category,
        description=description,
        risk_score=90 if category == "real_threat" else 30,
    )
    db.add(report)
    return report


def list_market_offers(db: Session, profile: PlayerProfile) -> list[MarketOffer]:
    if profile.city_id is None:
        return []
    return list(
        db.scalars(
            select(MarketOffer)
            .where(
                MarketOffer.world_id == profile.world_id,
                MarketOffer.city_id == profile.city_id,
                MarketOffer.status == "open",
                MarketOffer.expires_at > datetime.now(UTC),
            )
            .order_by(MarketOffer.created_at.desc())
        )
    )


def create_market_offer(
    db: Session,
    profile: PlayerProfile,
    resource_type: str,
    amount: Decimal,
    unit_price: Decimal,
    idempotency_key: str,
) -> MarketOffer:
    if profile.city_id is None:
        raise HTTPException(
            status_code=409,
            detail={"code": "market.city_required", "message": "City membership required"},
        )
    existing = db.scalar(
        select(MarketOffer).where(
            MarketOffer.seller_profile_id == profile.id,
            MarketOffer.idempotency_key == idempotency_key,
        )
    )
    if existing:
        return existing
    market = db.scalar(
        select(CityMarket).where(
            CityMarket.city_id == profile.city_id,
            CityMarket.resource_key == resource_type,
        )
    )
    if market is None:
        raise HTTPException(
            status_code=422,
            detail={"code": "market.resource_not_tradable", "message": "Resource is not tradable"},
        )
    reference_price = as_decimal(market.price)
    protected = as_utc(profile.protected_until) > datetime.now(UTC)
    lower = Decimal("0.75") if protected else Decimal("0.50")
    upper = Decimal("1.25") if protected else Decimal("2.00")
    if unit_price < reference_price * lower or unit_price > reference_price * upper:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "market.price_outlier",
                "message": "Price is outside safe market limits",
            },
        )
    apply_profile_resource(
        db,
        profile.id,
        resource_type,
        -amount,
        reason="market_offer_reservation",
        reference_type="market_offer",
        reference_id=profile.city_id,
        idempotency_key=idempotency_key,
    )
    offer = MarketOffer(
        world_id=profile.world_id,
        city_id=profile.city_id,
        seller_profile_id=profile.id,
        resource_type=resource_type,
        amount=amount,
        unit_price=unit_price,
        idempotency_key=idempotency_key,
        expires_at=datetime.now(UTC) + timedelta(hours=24),
    )
    db.add(offer)
    return offer


def accept_market_offer(
    db: Session,
    buyer: PlayerProfile,
    offer_id: str,
    idempotency_key: str,
) -> MarketTrade:
    offer = db.scalar(select(MarketOffer).where(MarketOffer.id == offer_id).with_for_update())
    if offer is not None:
        existing = db.scalar(select(MarketTrade).where(MarketTrade.offer_id == offer.id))
        if existing is not None and existing.buyer_profile_id == buyer.id:
            return existing
    if (
        offer is None
        or offer.status != "open"
        or as_utc(offer.expires_at) <= datetime.now(UTC)
        or offer.city_id != buyer.city_id
        or offer.seller_profile_id == buyer.id
    ):
        raise HTTPException(
            status_code=404,
            detail={"code": "market.offer_not_found", "message": "Open offer not found"},
        )
    total = (as_decimal(offer.amount) * as_decimal(offer.unit_price)).quantize(Decimal("0.01"))
    daily_total = db.scalar(
        select(func.coalesce(func.sum(MarketTrade.total_price), 0)).where(
            MarketTrade.buyer_profile_id == buyer.id,
            MarketTrade.created_at > datetime.now(UTC) - timedelta(days=1),
        )
    )
    if as_decimal(daily_total or 0) + total > Decimal("250000"):
        raise HTTPException(
            status_code=409,
            detail={"code": "market.daily_limit", "message": "Daily transfer limit reached"},
        )
    apply_profile_resource(
        db,
        buyer.id,
        "cash",
        -total,
        reason="market_purchase",
        reference_type="market_offer",
        reference_id=offer.id,
        idempotency_key=idempotency_key,
    )
    apply_profile_resource(
        db,
        offer.seller_profile_id,
        "cash",
        total,
        reason="market_sale",
        reference_type="market_offer",
        reference_id=offer.id,
        idempotency_key=idempotency_key,
    )
    apply_profile_resource(
        db,
        buyer.id,
        offer.resource_type,
        offer.amount,
        reason="market_purchase",
        reference_type="market_offer",
        reference_id=offer.id,
        idempotency_key=idempotency_key,
    )
    market = db.scalar(
        select(CityMarket).where(
            CityMarket.city_id == offer.city_id,
            CityMarket.resource_key == offer.resource_type,
        )
    )
    deviation = (
        abs(as_decimal(offer.unit_price) - as_decimal(market.price)) / as_decimal(market.price)
        if market and as_decimal(market.price) > 0
        else Decimal("0")
    )
    review_state = "review" if deviation > Decimal("0.50") else "clear"
    trade = MarketTrade(
        world_id=offer.world_id,
        city_id=offer.city_id,
        offer_id=offer.id,
        seller_profile_id=offer.seller_profile_id,
        buyer_profile_id=buyer.id,
        resource_type=offer.resource_type,
        amount=offer.amount,
        total_price=total,
        review_state=review_state,
    )
    db.add(trade)
    offer.status = "filled"
    if review_state == "review":
        db.add(
            AntiCheatRiskEvent(
                world_id=offer.world_id,
                profile_id=buyer.id,
                related_profile_id=offer.seller_profile_id,
                event_type="market_price_deviation",
                risk_score=35,
                evidence_json={"offer_id": offer.id, "deviation_band": "high"},
            )
        )
    emit_realtime(
        db,
        offer.world_id,
        "market.offer_filled",
        {"offer_id": offer.id},
        [buyer.id, offer.seller_profile_id],
    )
    return trade
