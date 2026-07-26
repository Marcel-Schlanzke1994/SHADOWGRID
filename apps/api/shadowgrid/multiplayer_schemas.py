from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field

from shadowgrid.schemas import ORMModel


class CityView(ORMModel):
    id: str
    world_id: str
    slug: str
    name: str
    region_key: str
    instance_key: str
    status: str
    max_players: int
    active_players: int = 0
    active_cartels: int = 0


class CityMarketView(ORMModel):
    resource_key: str
    price: Decimal
    supply: Decimal
    demand: Decimal
    version: int
    updated_at: datetime


class PvpTargetView(BaseModel):
    profile_id: str
    codename: str
    city_id: str
    cartel_id: str | None
    cartel_name: str | None
    public_reputation: dict[str, int]
    estimated_strength: str
    known_businesses: int
    known_district_presence: list[str]
    last_public_activity: datetime
    treaty_status: str | None
    protection_status: str
    recommendation: str


class PvpPreviewRequest(BaseModel):
    defender_profile_id: str
    operation_type: str
    district_id: str | None = None
    risk_posture: str = Field(default="balanced", pattern=r"^(cautious|balanced|aggressive)$")


class PvpPreviewView(BaseModel):
    defender_profile_id: str
    operation_type: str
    estimated_cost_cash: Decimal
    estimated_cost_influence: Decimal
    estimated_minutes: int
    estimated_success_band: str
    repetition_multiplier: Decimal
    reward_multiplier: Decimal
    protection_status: str
    treaty_status: str | None
    can_launch: bool
    reasons: list[str]


class PvpOperationCreate(PvpPreviewRequest):
    pass


class PvpDefenseRequest(BaseModel):
    action_type: str
    commitment: dict[str, Any] = {}


class PvpSupportRequest(BaseModel):
    side: str = Field(pattern=r"^(attacker|defender)$")
    cash: Decimal = Field(default=Decimal("0"), ge=0, le=25_000)
    influence: Decimal = Field(default=Decimal("0"), ge=0, le=10)


class PvpOperationView(ORMModel):
    id: str
    world_id: str
    city_id: str
    attacker_profile_id: str
    attacker_cartel_id: str | None
    defender_profile_id: str
    defender_cartel_id: str | None
    operation_type: str
    target_type: str
    target_id: str
    district_id: str | None
    risk_posture: str
    status: str
    starts_at: datetime
    warning_at: datetime
    response_deadline_at: datetime
    resolves_at: datetime
    resolved_at: datetime | None
    result_payload: dict[str, Any] | None
    my_side: str = "participant"
    defense_submitted: bool = False
    my_report_id: str | None = None


class PvpReportView(ORMModel):
    id: str
    operation_id: str
    profile_id: str
    perspective: str
    summary: str
    confidence: int
    details_json: dict[str, Any]
    created_at: datetime


class PvpProtectionView(BaseModel):
    status: str
    protected_until: datetime | None
    recovery_until: datetime | None
    offensive_lock: bool
    reasons: list[str]


class PvpReputationView(ORMModel):
    profile_id: str
    reliability: int
    economic_strength: int
    diplomacy: int
    aggression: int
    defense: int
    stability: int
    treaty_breaches: int
    attack_count: int
    defense_count: int


class TerritoryClaimRequest(BaseModel):
    claim_type: str = Field(default="influence", pattern=r"^(influence|defense|seasonal)$")


class TerritoryContributionRequest(BaseModel):
    contribution_type: str = Field(
        default="influence",
        pattern=r"^(influence|economic|information|social|digital|logistics)$",
    )
    amount: Decimal = Field(ge=1, le=25)


class TerritoryChallengeRequest(BaseModel):
    amount: Decimal = Field(default=Decimal("5"), ge=1, le=25)


class TerritoryControlPointView(ORMModel):
    id: str
    point_type: str
    controlling_cartel_id: str | None
    control_value: Decimal
    status: str
    version: int


class TerritoryClaimView(ORMModel):
    id: str
    district_id: str
    cartel_id: str
    status: str
    claim_strength: Decimal
    visibility: int
    expires_at: datetime
    version: int


class TerritoryView(BaseModel):
    district_id: str
    district_name: str
    status: str
    controlling_cartel_id: str | None
    active_claims: list[TerritoryClaimView]
    control_points: list[TerritoryControlPointView]


class CartelWarProposeRequest(BaseModel):
    defender_cartel_id: str
    war_type: str = Field(
        default="district_control",
        pattern=r"^(district_control|market_leadership|member_defense|treaty_enforcement|seasonal)$",
    )
    city_id: str | None = None
    district_id: str | None = None
    declaration_reason: str = Field(min_length=10, max_length=500)
    demand: str = Field(min_length=3, max_length=300)
    peace_conditions: str = Field(min_length=3, max_length=300)


class CriticalReauthRequest(BaseModel):
    password: str = Field(min_length=1, max_length=128)


class CartelWarJoinRequest(BaseModel):
    side: str = Field(pattern=r"^(attacker|defender)$")


class CartelWarCommitRequest(BaseModel):
    resource_type: str = Field(pattern=r"^(cash|capital)$")
    amount: Decimal = Field(gt=0, le=1_000_000)


class CartelWarOperationRequest(BaseModel):
    operation_type: str = Field(
        pattern=r"^(territorial|economic|operations|intelligence|stability)$"
    )
    district_id: str | None = None
    cash: Decimal = Field(default=Decimal("0"), ge=0, le=100_000)
    influence: Decimal = Field(default=Decimal("0"), ge=0, le=20)


class CeasefireOfferRequest(BaseModel):
    terms: dict[str, Any] = {}


class CartelWarView(ORMModel):
    id: str
    world_id: str
    attacker_cartel_id: str
    defender_cartel_id: str
    war_type: str
    war_status: str
    city_id: str | None
    objective_config: dict[str, Any]
    rules_config: dict[str, Any]
    declaration_reason: str
    preparation_starts_at: datetime | None
    active_starts_at: datetime | None
    active_ends_at: datetime | None
    aftermath_ends_at: datetime | None
    attacker_score: Decimal
    defender_score: Decimal
    winner_cartel_id: str | None
    resolution_type: str | None
    my_cartel_id: str | None = None
    my_side: str | None = None


class CartelWarScoreView(ORMModel):
    cartel_id: str
    territorial: Decimal
    economic: Decimal
    operations: Decimal
    intelligence: Decimal
    participation: Decimal
    stability: Decimal
    penalties: Decimal
    total: Decimal
    version: int


class CartelWarEventView(ORMModel):
    id: str
    event_type: str
    actor_cartel_id: str | None
    public_payload: dict[str, Any]
    created_at: datetime


class AllianceCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    tag: str = Field(min_length=2, max_length=12, pattern=r"^[A-Za-z0-9]+$")
    charter: str = Field(default="", max_length=1_000)
    governance_model: str = Field(
        default="council", pattern=r"^(autocratic|council|democratic|contribution)$"
    )


class AllianceInviteRequest(BaseModel):
    cartel_id: str
    contribution_limit: Decimal = Field(default=Decimal("25"), ge=0, le=100)


class AllianceTreatyRequest(BaseModel):
    treaty_type: str = Field(
        pattern=r"^(defense_pact|intelligence_exchange|trade_cooperation|mediation|seasonal_goal)$"
    )
    counterparty_type: str = Field(pattern=r"^(cartel|alliance)$")
    counterparty_id: str
    duration_days: int = Field(default=14, ge=1, le=90)
    terms: dict[str, Any] = {}


class AllianceView(ORMModel):
    id: str
    world_id: str
    name: str
    tag: str
    charter: str
    governance_model: str
    trust_score: int
    member_limit: int
    status: str
    member_count: int = 0
    my_cartel_id: str | None = None
    my_role: str | None = None


class ChatChannelView(ORMModel):
    id: str
    channel_type: str
    scope_id: str
    name: str
    moderated: bool
    status: str


class ChatMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1_000)


class ChatMessageView(ORMModel):
    id: str
    channel_id: str
    sender_profile_id: str
    body: str
    moderation_state: str
    created_at: datetime


class DirectMessageCreate(BaseModel):
    recipient_profile_id: str
    body: str = Field(min_length=1, max_length=1_000)


class DirectMessageView(ORMModel):
    id: str
    sender_profile_id: str
    recipient_profile_id: str
    body: str
    status: str
    read_at: datetime | None
    created_at: datetime


class UserBlockRequest(BaseModel):
    blocked_profile_id: str


class ModerationReportCreate(BaseModel):
    target_type: str = Field(pattern=r"^(profile|chat_message|direct_message|cartel)$")
    target_id: str
    category: str = Field(
        pattern=r"^(spam|harassment|real_threat|personal_data|cheating|market_abuse|other)$"
    )
    description: str = Field(default="", max_length=1_000)


class MarketOfferCreate(BaseModel):
    resource_type: str = Field(
        pattern=r"^(capital|influence|intelligence|logistics_capacity|personnel_capacity)$"
    )
    amount: Decimal = Field(gt=0, le=1_000)
    unit_price: Decimal = Field(gt=0, le=100_000)


class MarketOfferView(ORMModel):
    id: str
    city_id: str
    seller_profile_id: str
    resource_type: str
    amount: Decimal
    unit_price: Decimal
    status: str
    expires_at: datetime
    created_at: datetime


class MarketTradeView(ORMModel):
    id: str
    offer_id: str
    seller_profile_id: str
    buyer_profile_id: str
    resource_type: str
    amount: Decimal
    total_price: Decimal
    review_state: str
    created_at: datetime
