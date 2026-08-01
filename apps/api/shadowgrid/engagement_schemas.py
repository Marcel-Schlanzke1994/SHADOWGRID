from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

GoalCategory = Literal["economic", "social", "exploration", "risk", "long_term", "season"]
GoalStatus = Literal["offered", "active", "completed", "swapped", "declined", "expired"]
OpportunityCategory = Literal["urgent", "strategic", "discoverable"]
NotificationCategory = Literal["critical", "strategic", "social", "summary"]
DoctrineKey = Literal[
    "industrial_captain",
    "financial_architect",
    "innovator",
    "real_estate_strategist",
    "networker",
    "information_strategist",
    "opportunist",
]
MasteryArea = Literal[
    "company_management",
    "market_analysis",
    "capital_markets",
    "contract_management",
    "people_leadership",
    "real_estate",
    "cartel_leadership",
    "diplomacy",
    "intelligence",
    "risk_management",
    "season_strategy",
]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class GoalView(BaseModel):
    id: str
    template_key: str
    category: GoalCategory
    title_key: str
    description_key: str
    unit_key: str
    status: GoalStatus
    target_value: int
    progress_value: int
    recommended_for_doctrine: bool
    choice_window_id: str
    selected_at: datetime | None
    completed_at: datetime | None
    catch_up_until: datetime
    reward_type: str
    reward_key: str


class GoalWindowView(BaseModel):
    id: str
    starts_at: datetime
    ends_at: datetime
    catch_up_until: datetime
    max_choices: int
    status: Literal["open", "catch_up", "closed"]
    selected_count: int
    goals: list[GoalView]


class SwapGoalRequest(BaseModel):
    replacement_goal_id: str = Field(min_length=36, max_length=36)


class OpenPlanCreateRequest(BaseModel):
    category: OpportunityCategory
    title: str = Field(min_length=2, max_length=140)
    next_step: str = Field(min_length=2, max_length=280)
    target_path: str = Field(pattern=r"^/[A-Za-z0-9/_-]*$", max_length=180)
    priority: int = Field(default=50, ge=0, le=100)


class OpenPlanUpdateRequest(BaseModel):
    status: Literal["active", "completed", "archived"]


class OpenPlanView(ORMModel):
    id: str
    category: OpportunityCategory
    title: str
    next_step: str
    target_path: str
    status: Literal["active", "completed", "archived"]
    priority: int
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


class CommandCenterOpportunity(BaseModel):
    category: OpportunityCategory
    source_type: Literal["plan", "goal", "world_event", "system"]
    source_id: str
    title: str
    detail: str
    target_path: str
    priority: int


class CommandCenterView(BaseModel):
    opportunities: list[CommandCenterOpportunity] = Field(max_length=3)
    active_goal_count: int
    open_plan_count: int
    natural_break_available: bool


class SessionStartRequest(BaseModel):
    client_session_key: str = Field(min_length=8, max_length=80, pattern=r"^[A-Za-z0-9:_-]+$")


class SessionFinishRequest(BaseModel):
    decision_keys: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def unique_decisions(self) -> SessionFinishRequest:
        normalized = [item.strip() for item in self.decision_keys if item.strip()]
        if any(len(item) > 80 for item in normalized):
            raise ValueError("Decision keys must not exceed 80 characters")
        if len(set(normalized)) != len(normalized):
            raise ValueError("Decision keys must be unique")
        self.decision_keys = normalized
        return self


class SessionView(ORMModel):
    id: str
    profile_id: str
    client_session_key: str
    status: Literal["active", "completed", "abandoned"]
    started_at: datetime
    last_activity_at: datetime
    ended_at: datetime | None


class SessionSummaryView(ORMModel):
    id: str
    session_id: str
    duration_seconds: int
    decisions_json: list[dict[str, object]]
    changes_json: list[dict[str, object]]
    open_plans_json: list[dict[str, object]]
    next_entry_points_json: list[dict[str, object]]
    natural_break_reached: bool
    created_at: datetime


class ReturnBriefingView(ORMModel):
    id: str
    since_at: datetime
    world_changes_json: list[dict[str, object]]
    company_changes_json: list[dict[str, object]]
    relevant_decisions_json: list[dict[str, object]]
    available_content_json: list[dict[str, object]]
    entry_points_json: list[dict[str, object]]
    generated_at: datetime
    acknowledged_at: datetime | None


class NotificationPreferenceUpdate(BaseModel):
    live_enabled: bool
    digest_frequency: Literal["immediate", "daily", "weekly", "off"]
    quiet_start_minute: int = Field(ge=0, le=1439)
    quiet_end_minute: int = Field(ge=0, le=1439)
    timezone: str = Field(default="Europe/Berlin", min_length=3, max_length=64)


class NotificationPreferenceView(ORMModel):
    id: str
    category: NotificationCategory
    live_enabled: bool
    digest_frequency: Literal["immediate", "daily", "weekly", "off"]
    quiet_start_minute: int
    quiet_end_minute: int
    timezone: str
    updated_at: datetime


class EngagementSettingUpdate(BaseModel):
    adaptive_help_enabled: bool
    session_summary_enabled: bool
    ranking_visible: bool
    information_density: Literal["compact", "standard", "detailed"]


class EngagementSettingView(ORMModel):
    id: str
    adaptive_help_enabled: bool
    session_summary_enabled: bool
    ranking_visible: bool
    information_density: Literal["compact", "standard", "detailed"]
    updated_at: datetime


class WellbeingSignals(BaseModel):
    very_long_sessions_delta_bps: int = Field(ge=-10_000, le=10_000)
    push_disable_delta_bps: int = Field(ge=-10_000, le=10_000)
    obligation_reports: int = Field(ge=0)
    fear_motivated_return_bps: int = Field(ge=0, le=10_000)
    absence_pressure_reports: int = Field(ge=0)
    exhaustion_after_session_bps: int = Field(ge=0, le=10_000)


class GuardrailEvaluationRequest(BaseModel):
    wellbeing_status: Literal["passed", "failed", "insufficient_data"] = "insufficient_data"
    technical_status: Literal["passed", "failed", "insufficient_data"] = "insufficient_data"
    accessibility_status: Literal["passed", "failed", "insufficient_data"] = "insufficient_data"
    voluntary_return_status: Literal["passed", "failed", "insufficient_data"] = "insufficient_data"
    wellbeing_signals: WellbeingSignals


class GuardrailEvaluationView(ORMModel):
    id: str
    world_id: str | None
    strategy_spread_bps: int
    cartel_dominance_bps: int
    newcomer_wealth_bps: int
    ledger_imbalance_cents: int
    negative_balance_count: int
    wellbeing_status: str
    technical_status: str
    accessibility_status: str
    voluntary_return_status: str
    wellbeing_signals_json: dict[str, object]
    passed: bool
    reasons_json: list[str]
    evaluated_at: datetime


class EngagementMetricRequest(BaseModel):
    metric_date: date | None = None
    satisfaction_bps: int | None = Field(default=None, ge=0, le=10_000)
    fairness_bps: int | None = Field(default=None, ge=0, le=10_000)
    survey_response_count: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def validate_aggregate_survey(self) -> EngagementMetricRequest:
        supplied = self.satisfaction_bps is not None or self.fairness_bps is not None
        if supplied and (self.satisfaction_bps is None or self.fairness_bps is None):
            raise ValueError("satisfaction and fairness aggregates must be supplied together")
        if supplied and self.survey_response_count == 0:
            raise ValueError("aggregate survey values require a response count")
        return self


class EngagementMetricView(ORMModel):
    id: str
    world_id: str | None
    scope_key: str
    metric_date: date
    cohort_key: str
    profile_count: int
    active_profile_count: int
    d1_return_bps: int
    d7_return_bps: int
    d30_return_bps: int
    weekly_return_bps: int
    goal_completion_bps: int
    meaningful_decision_count: int
    strategy_diversity_bps: int
    season_participation_bps: int
    socially_engaged_bps: int
    pause_return_7_bps: int
    pause_return_14_bps: int
    pause_return_30_bps: int
    satisfaction_bps: int | None
    fairness_bps: int | None
    survey_response_count: int
    natural_break_bps: int
    story_progress_count: int
    collection_completion_bps: int
    generated_at: datetime


class RolloutUpdateRequest(BaseModel):
    cohort_bps: Literal[0, 500, 2000, 5000, 10000]


class RolloutView(ORMModel):
    id: str
    feature_key: str
    cohort_bps: int
    status: Literal["disabled", "internal", "staged", "active", "paused"]
    last_evaluation_id: str | None
    updated_at: datetime


class DoctrineCatalogItem(BaseModel):
    key: DoctrineKey
    title_key: str
    description_key: str
    focus_areas: list[MasteryArea]
    economic_bonus: Literal[False]
    reversible: Literal[True]


class DoctrineSelectRequest(BaseModel):
    doctrine_key: DoctrineKey


class DoctrineStateView(ORMModel):
    id: str
    doctrine_key: DoctrineKey
    version: int
    selected_at: datetime
    changed_at: datetime


class MasteryProgressView(ORMModel):
    id: str
    area_key: MasteryArea
    points: int
    level: int
    distinct_decisions_json: list[str]
    updated_at: datetime


class OutcomeReportView(ORMModel):
    id: str
    source_type: str
    source_id: str
    title_key: str
    controllable_factors_json: list[str]
    external_factors_json: list[str]
    worked_well_json: list[str]
    alternatives_json: list[str]
    knowledge_unlocked_json: list[str]
    created_at: datetime


class AdaptiveHelpView(ORMModel):
    id: str
    context_key: str
    explanation_key: str
    suggestion_key: str
    target_path: str
    status: Literal["offered", "accepted", "dismissed", "completed"]
    created_at: datetime
    responded_at: datetime | None


class AdaptiveHelpResponse(BaseModel):
    status: Literal["accepted", "dismissed", "completed"]


class SuccessChainView(ORMModel):
    id: str
    chain_key: str
    completed_steps: int
    total_steps: int
    status: Literal["active", "completed"]
    completed_event_types_json: list[str]
    updated_at: datetime
    completed_at: datetime | None


class MentorshipCreateRequest(BaseModel):
    mentee_profile_id: str = Field(min_length=36, max_length=36)


class MentorshipAnswerRequest(BaseModel):
    accept: bool


class MentorshipRefreshRequest(BaseModel):
    positive_feedback: bool | None = None


class MentorshipView(ORMModel):
    id: str
    mentor_profile_id: str
    mentee_profile_id: str
    status: Literal["proposed", "active", "paused", "completed", "declined", "cancelled"]
    mentor_opted_in: bool
    mentee_opted_in: bool
    feedback_positive: bool | None
    created_at: datetime
    accepted_at: datetime | None
    completed_at: datetime | None
    milestones: list[str] = Field(default_factory=list)


class DelegationCreateRequest(BaseModel):
    delegate_profile_id: str = Field(min_length=36, max_length=36)
    role_key: Literal[
        "economic_analyst",
        "diplomat",
        "intelligence_coordinator",
        "project_manager",
        "trainer",
        "archivist",
        "event_planner",
    ]
    duration_days: int = Field(ge=1, le=30)


class DelegationView(ORMModel):
    id: str
    organization_id: str
    grantor_membership_id: str
    delegate_membership_id: str
    role_key: str
    permissions_json: list[str]
    status: Literal["active", "revoked", "expired"]
    starts_at: datetime
    expires_at: datetime
    revoked_at: datetime | None


class MembershipPauseRequest(BaseModel):
    duration_days: int = Field(ge=1, le=180)
    private_reason: str | None = Field(default=None, max_length=240)


class MembershipPauseView(ORMModel):
    id: str
    membership_id: str
    status: Literal["active", "completed", "cancelled"]
    starts_at: datetime
    planned_until: datetime
    resumed_at: datetime | None


class CartelChronicleView(ORMModel):
    id: str
    organization_id: str
    actor_profile_id: str | None
    entry_type: str
    source_type: str
    source_id: str
    title_key: str
    body_key: str
    metadata_json: dict[str, object]
    created_at: datetime
