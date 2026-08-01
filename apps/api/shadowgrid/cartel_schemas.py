from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CreateCartelRequest(BaseModel):
    name: str = Field(min_length=3, max_length=80)
    tag: str = Field(min_length=2, max_length=8, pattern=r"^[A-Za-z0-9]+$")
    archetype: str
    description: str = Field(default="", max_length=500)
    governance_model: str = Field(
        default="directorate",
        pattern=r"^(directorate|council|federation|collective)$",
    )


class CartelView(ORMModel):
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
    approval_threshold_cents: int
    single_spend_limit_cents: int
    status: str
    member_limit: int
    member_count: int = 0
    treasury_balance_cents: int = 0
    my_role: str | None = None
    my_permissions: list[str] = Field(default_factory=list)


class CartelMemberView(BaseModel):
    profile_id: str
    codename: str
    role: str
    status: str
    joined_at: datetime


class CartelInvitationRequest(BaseModel):
    email: EmailStr


class CartelInvitationView(ORMModel):
    id: str
    organization_id: str
    email: str
    status: str
    expires_at: datetime
    created_at: datetime
    cartel_name: str = ""
    cartel_tag: str = ""


class JoinCartelRequest(BaseModel):
    invitation_id: str


class UpdateCartelRoleRequest(BaseModel):
    role: str = Field(
        pattern=r"^(member|finance_lead|diplomat|strategist|intelligence_officer|economic_analyst|intelligence_coordinator|project_manager|trainer|archivist|event_planner)$"
    )


class LeadershipTransferRequest(BaseModel):
    target_profile_id: str


class TreasuryDepositRequest(BaseModel):
    amount_cents: int = Field(gt=0, le=1_000_000_000)


class CartelTreasuryView(BaseModel):
    cartel_id: str
    balance_cents: int
    reserved_cents: int
    approval_threshold_cents: int
    single_spend_limit_cents: int


class CartelExpenseRequest(BaseModel):
    amount_cents: int = Field(gt=0, le=10_000_000_000)
    purpose: str = Field(min_length=3, max_length=240)


class CartelExpenseView(ORMModel):
    id: str
    organization_id: str
    requested_by_profile_id: str
    approved_by_profile_id: str | None
    amount_cents: int
    purpose: str
    requires_approval: bool
    status: str
    transaction_id: str | None
    requested_at: datetime
    resolved_at: datetime | None


class CreateCartelProjectRequest(BaseModel):
    project_type: str = Field(
        pattern=r"^(logistics_hub|technology_center|media_campaign|compliance_network|trade_center)$"
    )
    district_id: str


class CartelProjectContributionRequest(BaseModel):
    resource_type: str = Field(pattern=r"^(cash|influence|intelligence)$")
    amount_units: int = Field(gt=0, le=1_000_000_000)


class CartelProjectView(ORMModel):
    id: str
    organization_id: str
    district_id: str
    project_type: str
    title: str
    status: str
    required_cash_cents: int
    required_influence: int
    required_intelligence: int
    contributed_cash_cents: int
    contributed_influence: int
    contributed_intelligence: int
    influence_kind: str
    influence_reward: int
    starts_at: datetime
    ends_at: datetime
    completed_at: datetime | None
    progress_bps: int = 0


class CartelInfluenceEntry(BaseModel):
    cartel_id: str
    cartel_name: str
    kind: str
    points: int


class DistrictCartelInfluenceView(BaseModel):
    district_id: str
    district_name: str
    status: str
    controlling_cartel_id: str | None
    controlling_cartel_name: str | None
    top_points: int
    entries: list[CartelInfluenceEntry]


class CartelRankingView(BaseModel):
    rank: int
    cartel_id: str
    name: str
    tag: str
    season_number: int
    score: int
    treasury_cents: int
    member_count: int
    completed_projects: int
    influence: int


class CartelActivityView(ORMModel):
    id: str
    action: str
    metadata_json: dict[str, object]
    created_at: datetime
