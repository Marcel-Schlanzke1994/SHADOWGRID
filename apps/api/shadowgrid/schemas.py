from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from shadowgrid.localization import normalize_account_locale


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
    email: EmailStr | None = None
    display_name: str = Field(min_length=2, max_length=40)
    password: str = Field(min_length=12, max_length=128)
    locale: str = Field(default="en", min_length=2, max_length=16)
    terms_accepted: bool

    @field_validator("locale")
    @classmethod
    def supported_locale(cls, value: str) -> str:
        return normalize_account_locale(value)

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
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, min_length=2, max_length=40)
    password: str = Field(min_length=1, max_length=128)
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")

    @model_validator(mode="after")
    def require_identifier(self) -> LoginRequest:
        if self.email is None and self.display_name is None:
            raise ValueError("email or display_name is required")
        return self


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


class SelectCityRequest(JoinWorldRequest):
    city_id: str


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
    city_id: str | None
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
    recovery_until: datetime | None
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


class CompanyIndustryConfigView(BaseModel):
    enterprise_value_cents: int
    revenue_cents: int
    cost_cents: int
    employees: int
    capacity: int
    quality: int
    market_share_bps: int
    reputation_bps: int
    compliance_bps: int
    innovation_bps: int
    risk_bps: int


class CompanyInvestmentConfigView(BaseModel):
    cost_cents: int
    metric: str
    increase: int


class CompanyConfigurationView(BaseModel):
    founding_cost_cents: int
    industries: dict[str, CompanyIndustryConfigView]
    investments: dict[str, CompanyInvestmentConfigView]


class CreateCompanyRequest(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    industry: str
    district_id: str

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not any(character.isalpha() for character in normalized):
            raise ValueError("company name must contain at least one letter")
        allowed_punctuation = {" ", "&", ".", "-", "'", "’"}
        if any(
            not character.isalnum() and character not in allowed_punctuation
            for character in normalized
        ):
            raise ValueError("company name contains unsupported characters")
        return normalized


class CompanyInvestmentRequest(BaseModel):
    investment_type: str


class CompanyView(ORMModel):
    id: str
    world_id: str
    founder_profile_id: str
    district_id: str
    industry: str
    name: str
    status: str
    account_balance_cents: int
    enterprise_value_cents: int
    revenue_cents: int
    cost_cents: int
    profit_cents: int
    debt_cents: int
    employees: int
    capacity: int
    quality: int
    market_share_bps: int
    reputation_bps: int
    compliance_bps: int
    innovation_bps: int
    risk_bps: int
    investigation_pressure_bps: int
    is_local_simulation: bool
    version: int
    created_at: datetime
    updated_at: datetime


class CompanyOwnershipView(ORMModel):
    id: str
    company_id: str
    owner_profile_id: str
    ownership_bps: int
    created_at: datetime


class CompanyInvestmentView(ORMModel):
    id: str
    company_id: str
    investor_profile_id: str
    investment_type: str
    amount_cents: int
    metric_before: int
    metric_after: int
    created_at: datetime


class CompanyMetricView(ORMModel):
    id: str
    company_id: str
    version: int
    reason: str
    reference_id: str
    enterprise_value_cents: int
    account_balance_cents: int
    revenue_cents: int
    cost_cents: int
    profit_cents: int
    capacity: int
    quality: int
    compliance_bps: int
    innovation_bps: int
    created_at: datetime


class CompanyDetailView(CompanyView):
    ownership: list[CompanyOwnershipView]
    investments: list[CompanyInvestmentView]
    metrics_history: list[CompanyMetricView]


class EconomyTickView(ORMModel):
    id: str
    world_id: str
    period_key: str
    period_start: datetime
    period_end: datetime
    status: str
    company_count: int
    market_count: int
    started_at: datetime
    completed_at: datetime | None

    @field_validator(
        "period_start",
        "period_end",
        "started_at",
        "completed_at",
        mode="before",
    )
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class EconomyStatusView(BaseModel):
    last_tick: EconomyTickView | None
    next_scheduled_at: datetime


class ManualEconomyTickRequest(BaseModel):
    world_id: str
    period_start: datetime | None = None

    @field_validator("period_start")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("period_start must include a timezone")
        return value


class CitySectorMarketView(ORMModel):
    id: str
    world_id: str
    city_id: str
    industry: str
    demand_units: int
    unit_revenue_cents: int
    variable_cost_per_unit_cents: int
    fixed_cost_cents: int
    version: int


class MarketEconomyReportView(ORMModel):
    id: str
    tick_id: str
    market_id: str
    demand_units: int
    allocated_units: int
    unfilled_units: int
    allocated_share_bps: int
    company_count: int
    total_revenue_cents: int
    total_cost_cents: int
    total_profit_cents: int
    inputs_json: dict[str, Any]
    created_at: datetime


class CompanyEconomyReportView(ORMModel):
    id: str
    tick_id: str
    market_report_id: str
    company_id: str
    settlement_transaction_id: str | None
    attractiveness_points: int
    allocated_units: int
    market_share_bps: int
    revenue_cents: int
    cost_cents: int
    profit_cents: int
    cash_delta_cents: int
    debt_delta_cents: int
    enterprise_value_before_cents: int
    enterprise_value_after_cents: int
    inputs_json: dict[str, Any]
    modifiers_json: dict[str, Any]
    created_at: datetime


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
    level: int
    energy: int
    experience_points: int
    skills_json: dict[str, int]
    competence: int
    loyalty: int
    ambition: int
    stress: int
    exposure: int
    salary: Decimal
    salary_cents: int
    status: str
    employer_company_id: str | None
    assigned_operation_id: str | None
    cooldown_until: datetime | None
    hired_at: datetime | None


class SpecialistMarketCandidateView(ORMModel):
    id: str
    world_id: str
    city_id: str
    market_cycle_key: str
    role: str
    name: str
    level: int
    salary_cents: int
    loyalty: int
    energy: int
    skills_json: dict[str, int]
    status: str
    available_until: datetime


class HireSpecialistRequest(BaseModel):
    company_id: str


class AssignSpecialistRequest(BaseModel):
    company_id: str


class SpecialistEffectsView(BaseModel):
    active_specialists: int
    capacity_bonus_units: int
    revenue_bonus_bps: int
    cost_reduction_bps: int
    attractiveness_bonus_points: int


class SpecialistPayrollTickView(ORMModel):
    id: str
    world_id: str
    economy_tick_id: str
    period_key: str
    status: str
    specialist_count: int
    started_at: datetime
    completed_at: datetime | None


class ManualSpecialistPayrollRequest(BaseModel):
    world_id: str
    period_start: datetime | None = None

    @field_validator("period_start")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("period_start must include a timezone")
        return value


class SpecialistPayrollReportView(ORMModel):
    id: str
    payroll_tick_id: str
    specialist_id: str
    company_id: str
    transaction_id: str | None
    salary_due_cents: int
    salary_paid_cents: int
    unpaid_cents: int
    loyalty_before: int
    loyalty_after: int
    energy_before: int
    energy_after: int
    level_before: int
    level_after: int
    created_at: datetime


class AiProfileView(ORMModel):
    id: str
    world_id: str
    city_id: str | None
    codename: str
    is_local_ai: bool
    ai_strategy: str | None
    ai_paused: bool
    ai_seed: int | None


class AiPauseRequest(BaseModel):
    paused: bool


class ManualAiTickRequest(BaseModel):
    world_id: str
    period_start: datetime | None = None

    @field_validator("period_start")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("period_start must include a timezone")
        return value


class AiDecisionTickView(ORMModel):
    id: str
    world_id: str
    economy_tick_id: str | None
    period_key: str
    status: str
    profile_count: int
    started_at: datetime
    completed_at: datetime | None


class ExchangeConfigurationView(BaseModel):
    min_enterprise_value_cents: int
    profitable_periods: int
    min_compliance_bps: int
    min_employees: int
    max_investigation_pressure_bps: int
    ipo_fee_cents: int
    order_rate_limit_per_minute: int
    max_price_deviation_bps: int


class IpoEligibilityView(BaseModel):
    eligible: bool
    reasons: list[str]
    metrics: dict[str, int]


class CreateIpoRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z0-9]+$")
    total_shares: int = Field(ge=2, le=100_000_000_000)
    offered_shares: int = Field(ge=1, le=100_000_000_000)


class ExchangeListingView(ORMModel):
    id: str
    world_id: str
    company_id: str
    company_name: str
    company_industry: str
    symbol: str
    status: str
    total_shares: int
    offered_shares: int
    initial_price_cents: int
    last_price_cents: int
    enterprise_value_cents: int
    profit_cents: int
    debt_cents: int
    ipo_fee_cents: int
    listed_at: datetime
    updated_at: datetime


class ExchangeOrderRequest(BaseModel):
    listing_id: str
    side: Literal["buy", "sell"]
    order_type: Literal["market", "limit"]
    quantity: int = Field(ge=1, le=100_000_000_000)
    limit_price_cents: int | None = Field(default=None, ge=1, le=100_000_000_000)
    expires_at: datetime | None = None

    @field_validator("expires_at")
    @classmethod
    def require_exchange_expiry_timezone(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        return value


class ExchangeOrderView(ORMModel):
    id: str
    listing_id: str
    share_class_id: str
    side: str
    order_type: str
    limit_price_cents: int | None
    original_quantity: int
    remaining_quantity: int
    reserved_cash_cents: int
    reserved_shares: int
    status: str
    expires_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExchangeOrderBookView(BaseModel):
    buys: list[ExchangeOrderView]
    sells: list[ExchangeOrderView]


class ExchangeTradeView(ORMModel):
    id: str
    listing_id: str
    share_class_id: str
    buy_order_id: str
    sell_order_id: str
    buyer_profile_id: str
    seller_profile_id: str | None
    seller_company_id: str | None
    quantity: int
    price_cents: int
    gross_cents: int
    executed_at: datetime


class PriceSnapshotView(ORMModel):
    id: str
    listing_id: str
    trade_id: str
    price_cents: int
    volume: int
    captured_at: datetime


class PortfolioItemView(ORMModel):
    holding_id: str
    listing_id: str
    company_id: str
    company_name: str
    symbol: str
    share_class: str
    quantity: int
    reserved_quantity: int
    available_quantity: int
    average_cost_cents: int
    last_price_cents: int
    market_value_cents: int
    voting_rights: int


class ShareholderView(ORMModel):
    holding_id: str
    profile_id: str
    codename: str
    quantity: int
    ownership_bps: int
    voting_rights: int


class DividendRequest(BaseModel):
    per_share_cents: int = Field(ge=1, le=1_000_000_000)


class DividendDeclarationView(ORMModel):
    id: str
    listing_id: str
    share_class_id: str
    declared_by_profile_id: str
    per_share_cents: int
    total_paid_cents: int
    eligible_shares: int
    status: str
    snapshot_at: datetime
    paid_at: datetime
    created_at: datetime


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
    city_id: str | None
    name: str
    tag: str
    archetype: str
    description: str
    governance_model: str
    stability: int
    reputation: int
    investigation_pressure: int
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
        pattern=r"^(candidate|member|district_lead|intelligence_lead|diplomacy_lead|finance_lead|war_lead|recruitment_lead|deputy)$"
    )


class CreateOrganizationRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    tag: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z0-9]+$")
    archetype: str
    description: str = Field(default="", max_length=500)
    governance_model: str = Field(
        default="directorate",
        pattern=r"^(directorate|council|federation|collective)$",
    )


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
