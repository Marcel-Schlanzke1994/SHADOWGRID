from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy import select

from shadowgrid.dependencies import (
    CurrentProfile,
    CurrentUser,
    Db,
    IdempotencyKey,
    request_id,
    require_admin,
)
from shadowgrid.domain import audit, safe_commit
from shadowgrid.engagement import (
    acknowledge_return_briefing,
    aggregate_engagement_metrics,
    command_center,
    create_open_plan,
    ensure_engagement_setting,
    ensure_notification_preferences,
    evaluate_guardrails,
    finish_session,
    generate_return_briefing,
    goal_view,
    goal_window_view,
    initialize_engagement,
    latest_session_summary,
    list_engagement_metrics,
    list_open_plans,
    select_goal,
    start_session,
    swap_goal,
    update_engagement_setting,
    update_notification_preference,
    update_open_plan,
    update_rollout,
)
from shadowgrid.engagement_schemas import (
    AdaptiveHelpResponse,
    AdaptiveHelpView,
    CartelChronicleView,
    CommandCenterView,
    DelegationCreateRequest,
    DelegationView,
    DoctrineCatalogItem,
    DoctrineSelectRequest,
    DoctrineStateView,
    EngagementMetricRequest,
    EngagementMetricView,
    EngagementSettingUpdate,
    EngagementSettingView,
    GoalView,
    GoalWindowView,
    GuardrailEvaluationRequest,
    GuardrailEvaluationView,
    MasteryProgressView,
    MembershipPauseRequest,
    MembershipPauseView,
    MentorshipAnswerRequest,
    MentorshipCreateRequest,
    MentorshipRefreshRequest,
    MentorshipView,
    NotificationCategory,
    NotificationPreferenceUpdate,
    NotificationPreferenceView,
    OpenPlanCreateRequest,
    OpenPlanUpdateRequest,
    OpenPlanView,
    OutcomeReportView,
    ReturnBriefingView,
    RolloutUpdateRequest,
    RolloutView,
    SessionFinishRequest,
    SessionStartRequest,
    SessionSummaryView,
    SessionView,
    SuccessChainView,
    SwapGoalRequest,
)
from shadowgrid.errors import DomainError
from shadowgrid.models import GoalChoiceWindow, MentoringMilestone, Mentorship, User
from shadowgrid.progression import (
    accept_mentorship,
    adaptive_help,
    choose_doctrine,
    create_delegation,
    current_doctrine,
    current_membership_pause,
    doctrine_catalog,
    ensure_mastery_progress,
    list_cartel_chronicle,
    list_delegations,
    list_mentorships,
    list_outcome_reports,
    pause_membership,
    propose_mentorship,
    refresh_mentorship,
    respond_to_help,
    resume_membership,
    success_chain,
)

router = APIRouter(prefix="/engagement", tags=["engagement"])


def _mentorship_view(db: Db, mentorship: Mentorship) -> MentorshipView:
    milestones = list(
        db.scalars(
            select(MentoringMilestone.milestone_key)
            .where(MentoringMilestone.mentorship_id == mentorship.id)
            .order_by(MentoringMilestone.achieved_at)
        )
    )
    return MentorshipView.model_validate(mentorship).model_copy(update={"milestones": milestones})


@router.post("/initialize", response_model=GoalWindowView)
def initialize(
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
    request: Request,
) -> GoalWindowView:
    window = initialize_engagement(
        db,
        user,
        profile,
        idempotency_key=idempotency_key,
    )
    audit(
        db,
        user.id,
        "engagement.initialized",
        "goal_choice_window",
        window.id,
        request_id(request),
    )
    safe_commit(db)
    return GoalWindowView.model_validate(goal_window_view(db, window))


@router.get("/doctrines", response_model=list[DoctrineCatalogItem])
def doctrines() -> list[DoctrineCatalogItem]:
    return [DoctrineCatalogItem.model_validate(item) for item in doctrine_catalog()]


@router.get("/doctrine", response_model=DoctrineStateView | None)
def doctrine_current(db: Db, profile: CurrentProfile) -> DoctrineStateView | None:
    doctrine = current_doctrine(db, profile)
    return DoctrineStateView.model_validate(doctrine) if doctrine is not None else None


@router.put("/doctrine", response_model=DoctrineStateView)
def doctrine_select(
    payload: DoctrineSelectRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> DoctrineStateView:
    doctrine = choose_doctrine(
        db,
        profile,
        doctrine_key=payload.doctrine_key,
        idempotency_key=idempotency_key,
    )
    audit(
        db,
        user.id,
        "engagement.doctrine_selected",
        "player_doctrine",
        doctrine.id,
        request_id(request),
        {"doctrine_key": doctrine.doctrine_key, "version": doctrine.version},
    )
    safe_commit(db)
    return DoctrineStateView.model_validate(doctrine)


@router.get("/mastery", response_model=list[MasteryProgressView])
def mastery(db: Db, profile: CurrentProfile) -> list[MasteryProgressView]:
    result = ensure_mastery_progress(db, profile)
    safe_commit(db)
    return [MasteryProgressView.model_validate(item) for item in result]


@router.get("/outcome-reports", response_model=list[OutcomeReportView])
def outcome_reports(db: Db, profile: CurrentProfile) -> list[OutcomeReportView]:
    return [OutcomeReportView.model_validate(item) for item in list_outcome_reports(db, profile)]


@router.get("/adaptive-help", response_model=list[AdaptiveHelpView])
def help_offers(db: Db, profile: CurrentProfile) -> list[AdaptiveHelpView]:
    offers = adaptive_help(db, profile)
    safe_commit(db)
    return [AdaptiveHelpView.model_validate(item) for item in offers]


@router.patch("/adaptive-help/{offer_id}", response_model=AdaptiveHelpView)
def help_respond(
    offer_id: str,
    payload: AdaptiveHelpResponse,
    db: Db,
    profile: CurrentProfile,
) -> AdaptiveHelpView:
    offer = respond_to_help(db, profile, offer_id, payload.status)
    safe_commit(db)
    return AdaptiveHelpView.model_validate(offer)


@router.get("/success-chain", response_model=SuccessChainView)
def personal_success_chain(db: Db, profile: CurrentProfile) -> SuccessChainView:
    chain = success_chain(db, profile)
    safe_commit(db)
    return SuccessChainView.model_validate(chain)


@router.get("/mentorships", response_model=list[MentorshipView])
def mentorship_list(db: Db, profile: CurrentProfile) -> list[MentorshipView]:
    return [_mentorship_view(db, item) for item in list_mentorships(db, profile)]


@router.post("/mentorships", response_model=MentorshipView)
def mentorship_create(
    payload: MentorshipCreateRequest,
    request: Request,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> MentorshipView:
    mentorship = propose_mentorship(
        db,
        profile,
        mentee_profile_id=payload.mentee_profile_id,
        idempotency_key=idempotency_key,
    )
    audit(
        db,
        user.id,
        "mentoring.proposed",
        "mentorship",
        mentorship.id,
        request_id(request),
    )
    safe_commit(db)
    return _mentorship_view(db, mentorship)


@router.post("/mentorships/{mentorship_id}/answer", response_model=MentorshipView)
def mentorship_answer(
    mentorship_id: str,
    payload: MentorshipAnswerRequest,
    db: Db,
    profile: CurrentProfile,
) -> MentorshipView:
    mentorship = accept_mentorship(db, profile, mentorship_id, accept=payload.accept)
    safe_commit(db)
    return _mentorship_view(db, mentorship)


@router.post("/mentorships/{mentorship_id}/refresh", response_model=MentorshipView)
def mentorship_refresh(
    mentorship_id: str,
    payload: MentorshipRefreshRequest,
    db: Db,
    profile: CurrentProfile,
) -> MentorshipView:
    mentorship = refresh_mentorship(
        db,
        profile,
        mentorship_id,
        positive_feedback=payload.positive_feedback,
    )
    safe_commit(db)
    return _mentorship_view(db, mentorship)


@router.post(
    "/social/cartels/{cartel_id}/delegations",
    response_model=DelegationView,
)
def delegation_create(
    cartel_id: str,
    payload: DelegationCreateRequest,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> DelegationView:
    delegation = create_delegation(
        db,
        profile,
        organization_id=cartel_id,
        delegate_profile_id=payload.delegate_profile_id,
        role_key=payload.role_key,
        duration_days=payload.duration_days,
        idempotency_key=idempotency_key,
    )
    safe_commit(db)
    return DelegationView.model_validate(delegation)


@router.get(
    "/social/cartels/{cartel_id}/delegations",
    response_model=list[DelegationView],
)
def delegations(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[DelegationView]:
    result = list_delegations(db, profile, cartel_id)
    safe_commit(db)
    return [DelegationView.model_validate(item) for item in result]


@router.post(
    "/social/cartels/{cartel_id}/pause",
    response_model=MembershipPauseView,
)
def cartel_pause(
    cartel_id: str,
    payload: MembershipPauseRequest,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> MembershipPauseView:
    pause = pause_membership(
        db,
        profile,
        organization_id=cartel_id,
        duration_days=payload.duration_days,
        private_reason=payload.private_reason,
        idempotency_key=idempotency_key,
    )
    safe_commit(db)
    return MembershipPauseView.model_validate(pause)


@router.get(
    "/social/cartels/{cartel_id}/pause",
    response_model=MembershipPauseView | None,
)
def cartel_current_pause(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> MembershipPauseView | None:
    pause = current_membership_pause(db, profile, cartel_id)
    safe_commit(db)
    return MembershipPauseView.model_validate(pause) if pause is not None else None


@router.post(
    "/social/cartels/{cartel_id}/resume",
    response_model=MembershipPauseView,
)
def cartel_resume(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> MembershipPauseView:
    pause = resume_membership(db, profile, organization_id=cartel_id)
    safe_commit(db)
    return MembershipPauseView.model_validate(pause)


@router.get(
    "/social/cartels/{cartel_id}/chronicle",
    response_model=list[CartelChronicleView],
)
def cartel_chronicle(
    cartel_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[CartelChronicleView]:
    return [
        CartelChronicleView.model_validate(item)
        for item in list_cartel_chronicle(db, profile, cartel_id)
    ]


@router.get("/goals/current", response_model=GoalWindowView)
def current_goals(db: Db, profile: CurrentProfile) -> GoalWindowView:
    window = db.scalar(
        select(GoalChoiceWindow)
        .where(
            GoalChoiceWindow.profile_id == profile.id,
            GoalChoiceWindow.status.in_(("open", "catch_up")),
        )
        .order_by(GoalChoiceWindow.starts_at.desc())
        .limit(1)
    )
    if window is None:
        raise DomainError(
            409,
            "engagement.initialization_required",
            "Initialize the engagement layer before requesting personal goals",
        )
    return GoalWindowView.model_validate(goal_window_view(db, window))


@router.post("/goals/{goal_id}/select", response_model=GoalView)
def goal_select(
    goal_id: str,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> GoalView:
    goal = select_goal(
        db,
        user,
        profile,
        goal_id,
        idempotency_key=idempotency_key,
    )
    safe_commit(db)
    return GoalView.model_validate(goal_view(db, goal))


@router.post("/goals/{goal_id}/swap", response_model=GoalView)
def goal_swap(
    goal_id: str,
    payload: SwapGoalRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> GoalView:
    replacement = swap_goal(
        db,
        user,
        profile,
        goal_id,
        payload.replacement_goal_id,
        idempotency_key=idempotency_key,
    )
    safe_commit(db)
    return GoalView.model_validate(goal_view(db, replacement))


@router.get("/open-plans", response_model=list[OpenPlanView])
def open_plans(db: Db, profile: CurrentProfile) -> list[OpenPlanView]:
    return [OpenPlanView.model_validate(item) for item in list_open_plans(db, profile)]


@router.post("/open-plans", response_model=OpenPlanView)
def open_plan_create(
    payload: OpenPlanCreateRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> OpenPlanView:
    plan = create_open_plan(
        db,
        user,
        profile,
        category=payload.category,
        title=payload.title,
        next_step=payload.next_step,
        target_path=payload.target_path,
        priority=payload.priority,
        idempotency_key=idempotency_key,
    )
    safe_commit(db)
    return OpenPlanView.model_validate(plan)


@router.patch("/open-plans/{plan_id}", response_model=OpenPlanView)
def open_plan_update(
    plan_id: str,
    payload: OpenPlanUpdateRequest,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> OpenPlanView:
    plan = update_open_plan(
        db,
        user,
        profile,
        plan_id,
        status=payload.status,
        idempotency_key=idempotency_key,
    )
    safe_commit(db)
    return OpenPlanView.model_validate(plan)


@router.get("/command-center", response_model=CommandCenterView)
def engagement_command_center(db: Db, profile: CurrentProfile) -> CommandCenterView:
    return CommandCenterView.model_validate(command_center(db, profile))


@router.post("/sessions", response_model=SessionView)
def session_start(
    payload: SessionStartRequest,
    db: Db,
    profile: CurrentProfile,
) -> SessionView:
    session = start_session(db, profile, client_session_key=payload.client_session_key)
    safe_commit(db)
    return SessionView.model_validate(session)


@router.post("/sessions/{session_id}/finish", response_model=SessionSummaryView)
def session_finish(
    session_id: str,
    payload: SessionFinishRequest,
    db: Db,
    profile: CurrentProfile,
) -> SessionSummaryView:
    summary = finish_session(
        db,
        profile,
        session_id,
        decision_keys=payload.decision_keys,
    )
    safe_commit(db)
    return SessionSummaryView.model_validate(summary)


@router.get("/sessions/latest-summary", response_model=SessionSummaryView | None)
def session_latest_summary(db: Db, profile: CurrentProfile) -> SessionSummaryView | None:
    summary = latest_session_summary(db, profile)
    return SessionSummaryView.model_validate(summary) if summary is not None else None


@router.post("/return-briefings", response_model=ReturnBriefingView)
def return_briefing_generate(db: Db, profile: CurrentProfile) -> ReturnBriefingView:
    briefing = generate_return_briefing(db, profile)
    safe_commit(db)
    return ReturnBriefingView.model_validate(briefing)


@router.post("/return-briefings/{briefing_id}/acknowledge", response_model=ReturnBriefingView)
def return_briefing_acknowledge(
    briefing_id: str,
    db: Db,
    profile: CurrentProfile,
) -> ReturnBriefingView:
    briefing = acknowledge_return_briefing(db, profile, briefing_id)
    safe_commit(db)
    return ReturnBriefingView.model_validate(briefing)


@router.get("/notification-preferences", response_model=list[NotificationPreferenceView])
def notification_preferences(
    db: Db,
    profile: CurrentProfile,
) -> list[NotificationPreferenceView]:
    preferences = ensure_notification_preferences(db, profile)
    safe_commit(db)
    return [NotificationPreferenceView.model_validate(item) for item in preferences]


@router.put(
    "/notification-preferences/{category}",
    response_model=NotificationPreferenceView,
)
def notification_preference_update(
    payload: NotificationPreferenceUpdate,
    db: Db,
    profile: CurrentProfile,
    category: Annotated[NotificationCategory, Path()],
) -> NotificationPreferenceView:
    preference = update_notification_preference(
        db,
        profile,
        category,
        live_enabled=payload.live_enabled,
        digest_frequency=payload.digest_frequency,
        quiet_start_minute=payload.quiet_start_minute,
        quiet_end_minute=payload.quiet_end_minute,
        timezone=payload.timezone,
    )
    safe_commit(db)
    return NotificationPreferenceView.model_validate(preference)


@router.get("/settings", response_model=EngagementSettingView)
def settings(db: Db, profile: CurrentProfile) -> EngagementSettingView:
    setting = ensure_engagement_setting(db, profile)
    safe_commit(db)
    return EngagementSettingView.model_validate(setting)


@router.put("/settings", response_model=EngagementSettingView)
def settings_update(
    payload: EngagementSettingUpdate,
    db: Db,
    profile: CurrentProfile,
) -> EngagementSettingView:
    setting = update_engagement_setting(
        db,
        profile,
        adaptive_help_enabled=payload.adaptive_help_enabled,
        session_summary_enabled=payload.session_summary_enabled,
        ranking_visible=payload.ranking_visible,
        information_density=payload.information_density,
    )
    safe_commit(db)
    return EngagementSettingView.model_validate(setting)


@router.post("/admin/guardrails/evaluate", response_model=GuardrailEvaluationView)
def guardrails_evaluate(
    payload: GuardrailEvaluationRequest,
    request: Request,
    db: Db,
    idempotency_key: IdempotencyKey,
    user: Annotated[User, Depends(require_admin)],
    world_id: str | None = None,
) -> GuardrailEvaluationView:
    evaluation = evaluate_guardrails(
        db,
        world_id=world_id,
        idempotency_key=idempotency_key,
        wellbeing_status=payload.wellbeing_status,
        wellbeing_signals=payload.wellbeing_signals.model_dump(),
        technical_status=payload.technical_status,
        accessibility_status=payload.accessibility_status,
        voluntary_return_status=payload.voluntary_return_status,
    )
    audit(
        db,
        user.id,
        "engagement.guardrails_evaluated",
        "engagement_guardrail_evaluation",
        evaluation.id,
        request_id(request),
        {"passed": evaluation.passed},
    )
    safe_commit(db)
    return GuardrailEvaluationView.model_validate(evaluation)


@router.post("/admin/metrics/daily", response_model=EngagementMetricView)
def engagement_metric_generate(
    payload: EngagementMetricRequest,
    request: Request,
    db: Db,
    idempotency_key: IdempotencyKey,
    user: Annotated[User, Depends(require_admin)],
    world_id: str | None = None,
) -> EngagementMetricView:
    metric = aggregate_engagement_metrics(
        db,
        world_id=world_id,
        idempotency_key=idempotency_key,
        metric_date=payload.metric_date,
        satisfaction_bps=payload.satisfaction_bps,
        fairness_bps=payload.fairness_bps,
        survey_response_count=payload.survey_response_count,
    )
    audit(
        db,
        user.id,
        "engagement.metrics_aggregated",
        "engagement_metric_daily",
        metric.id,
        request_id(request),
        {"scope_key": metric.scope_key, "metric_date": metric.metric_date.isoformat()},
    )
    safe_commit(db)
    return EngagementMetricView.model_validate(metric)


@router.get("/admin/metrics/daily", response_model=list[EngagementMetricView])
def engagement_metrics_list(
    db: Db,
    _: Annotated[User, Depends(require_admin)],
    world_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=90)] = 30,
) -> list[EngagementMetricView]:
    return [
        EngagementMetricView.model_validate(item)
        for item in list_engagement_metrics(db, world_id=world_id, limit=limit)
    ]


@router.put("/admin/rollouts/{feature_key}", response_model=RolloutView)
def rollout_update(
    payload: RolloutUpdateRequest,
    db: Db,
    user: Annotated[User, Depends(require_admin)],
    feature_key: Annotated[str, Path(pattern=r"^[a-z][a-z0-9_.-]{2,79}$")],
) -> RolloutView:
    rollout = update_rollout(
        db,
        user,
        feature_key=feature_key,
        cohort_bps=payload.cohort_bps,
    )
    safe_commit(db)
    return RolloutView.model_validate(rollout)
