from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str | None = None
    fields: dict[str, str] | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
    server_time: datetime


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=12, max_length=128)
    locale: str = Field(default="en", min_length=2, max_length=16)
    terms_accepted: bool

    @field_validator("password")
    @classmethod
    def password_complexity(cls, value: str) -> str:
        groups = [
            any(c.islower() for c in value),
            any(c.isupper() for c in value),
            any(c.isdigit() for c in value),
        ]
        if sum(groups) < 3:
            raise ValueError("password must contain upper, lower and numeric characters")
        return value

    @field_validator("terms_accepted")
    @classmethod
    def require_terms(cls, value: bool) -> bool:
        if not value:
            raise ValueError("terms must be accepted")
        return value


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"  # noqa: S105 - OAuth token type, not a credential.
    expires_in: int


class UserView(ORMModel):
    id: str
    email: EmailStr
    display_name: str
    locale: str
    email_verified: bool
    is_admin: bool
    is_moderator: bool


class SessionView(ORMModel):
    id: str
    user_agent: str
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class PasswordForgotRequest(BaseModel):
    email: EmailStr


class PasswordResetRequest(BaseModel):
    token: str
    password: str = Field(min_length=12, max_length=128)


class VerifyEmailRequest(BaseModel):
    token: str


class WorldView(ORMModel):
    id: str
    slug: str
    name: str
    status: str
    starts_at: datetime
    ends_at: datetime
    season_number: int


class JoinWorldRequest(BaseModel):
    codename: str = Field(min_length=2, max_length=40)
    archetype: str
    home_district_id: str


class ResourceView(ORMModel):
    cash: Decimal
    capital: Decimal
    influence: Decimal
    intelligence: Decimal
    logistics_capacity: Decimal
    personnel_capacity: Decimal
    version: int


class ProfileView(ORMModel):
    id: str
    world_id: str
    codename: str
    archetype: str
    home_district_id: str | None
    tutorial_step: int
    loyalty: int
    legitimacy: int
    fear: int
    investigation_pressure: int
    stress: int
    stability: int
    operation_slots: int
    protected_until: datetime
    resources: ResourceView


class TutorialRequest(BaseModel):
    step: int = Field(ge=0, le=7)


class DistrictView(ORMModel):
    id: str
    slug: str
    name: str
    prosperity: int
    employment: int
    safety: int
    authority_presence: int
    digital_infrastructure: int
    property_value: int
    public_trust: int
    media_attention: int
    economic_activity: int
    social_stability: int
    map_x: int
    map_y: int
    map_points: str
    influence: dict[str, float] = {}


class BusinessView(ORMModel):
    id: str
    district_id: str
    business_type: str
    name: str
    level: int
    revenue: Decimal
    operating_cost: Decimal
    personnel_need: int
    logistics_need: int
    status: str
    compliance: int
    reputation: int
    market_share: int
    risk: int
    upgrade_finishes_at: datetime | None


class BuyBusinessRequest(BaseModel):
    business_type: str
    district_id: str
    name: str = Field(min_length=2, max_length=100)


class FacilityView(ORMModel):
    id: str
    facility_type: str
    level: int
    status: str
    finishes_at: datetime | None


class FacilityRequest(BaseModel):
    facility_type: str


class SpecialistView(ORMModel):
    id: str
    name: str
    role: str
    competence: int
    loyalty: int
    ambition: int
    stress: int
    exposure: int
    salary: Decimal
    status: str


class RecruitSpecialistRequest(BaseModel):
    role: str


class OperationView(ORMModel):
    id: str
    operation_type: str
    district_id: str
    specialist_id: str
    target: str
    budget: Decimal
    intelligence_spend: Decimal
    risk_posture: str
    secrecy: int
    status: str
    result: str | None
    outcome_json: dict[str, Any] | None
    started_at: datetime
    finishes_at: datetime
    resolved_at: datetime | None


class StartOperationRequest(BaseModel):
    operation_type: str
    district_id: str
    specialist_id: str
    target: str = Field(min_length=2, max_length=120)
    budget: Decimal = Field(ge=1_000, le=1_000_000)
    intelligence_spend: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    risk_posture: str = "balanced"
    secrecy: int = Field(default=50, ge=0, le=100)


class IntelReportView(ORMModel):
    id: str
    title: str
    summary: str
    target_type: str
    target_id: str
    visible_confidence: int
    source: str
    observed_at: datetime
    expires_at: datetime
    status: str


class OrganizationView(ORMModel):
    id: str
    world_id: str
    name: str
    tag: str
    archetype: str
    description: str
    stability: int
    treasury_cash: Decimal
    treasury_capital: Decimal
    member_limit: int
    my_role: str | None = None
    member_count: int = 0


class OrganizationMemberView(BaseModel):
    membership_id: str
    profile_id: str
    codename: str
    role: str
    status: str
    joined_at: datetime


class UpdateOrganizationRoleRequest(BaseModel):
    role: str = Field(
        pattern=r"^(candidate|member|district_lead|intelligence_lead|diplomacy_lead|finance_lead|deputy)$"
    )


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    tag: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z0-9]+$")
    archetype: str
    description: str = Field(default="", max_length=500)


class InviteRequest(BaseModel):
    email: EmailStr


class TreasuryRequest(BaseModel):
    resource_type: str = Field(pattern=r"^(cash|capital)$")
    amount: Decimal = Field(gt=0, le=10_000_000)


class TreatyView(ORMModel):
    id: str
    proposer_org_id: str
    recipient_org_id: str
    treaty_type: str
    terms_json: dict[str, Any]
    visibility: str
    status: str
    breach_score: int
    starts_at: datetime | None
    expires_at: datetime


class CreateTreatyRequest(BaseModel):
    recipient_org_id: str
    treaty_type: str
    duration_days: int = Field(ge=1, le=90)
    visibility: str = Field(default="public", pattern=r"^(public|secret)$")
    terms: dict[str, Any] = {}


class ResearchView(ORMModel):
    id: str
    research_key: str
    category: str
    status: str
    started_at: datetime
    finishes_at: datetime
    resolved_at: datetime | None


class StartResearchRequest(BaseModel):
    research_key: str


class RankingEntry(BaseModel):
    rank: int
    profile_id: str
    codename: str
    economic_power: float
    influence: float
    stability: float
    intelligence: float
    diplomacy: float
    resilience: float
    social_impact: float
    penalty: float
    score: float


class CursorPage(BaseModel):
    items: list[dict[str, Any]]
    next_cursor: str | None = None


class NetworkNode(BaseModel):
    id: str
    kind: str
    label: str
    uncertain: bool = False


class NetworkEdge(BaseModel):
    source: str
    target: str
    kind: str
    uncertain: bool = False


class NetworkView(BaseModel):
    nodes: list[NetworkNode]
    edges: list[NetworkEdge]


class MessageResponse(BaseModel):
    message: str


class HealthResponse(BaseModel):
    status: str
    version: str
    server_time: datetime
