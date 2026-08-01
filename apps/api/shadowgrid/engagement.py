from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from threading import RLock
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import event as sqlalchemy_event
from sqlalchemy import func, select
from sqlalchemy.orm import Session, SessionTransaction

from shadowgrid.balance_simulation import run_simulation
from shadowgrid.domain import create_notification, get_idempotent, remember_idempotent
from shadowgrid.errors import DomainError
from shadowgrid.models import (
    Account,
    AccountLedgerEntry,
    CollectionItem,
    Company,
    CompanyEconomyReport,
    CompanyOwnership,
    EngagementEvent,
    EngagementGuardrailEvaluation,
    EngagementMetricDaily,
    EngagementRollout,
    EngagementSetting,
    GoalChoiceWindow,
    GoalInstance,
    GoalProgress,
    GoalReward,
    GoalTemplate,
    Mentorship,
    NarrativeChronicleEntry,
    NotificationPreference,
    OrganizationMembership,
    PlayerCollection,
    PlayerOpenPlan,
    PlayerProfile,
    PlayerSeasonGoal,
    PlayerSession,
    ResourceBalance,
    ReturnBriefing,
    ReturnContract,
    SessionSummary,
    User,
    WorldEventInstance,
    as_utc,
)

OpportunityCategory = Literal["urgent", "strategic", "discoverable"]
BERLIN = ZoneInfo("Europe/Berlin")
NOTIFICATION_CATEGORIES = ("critical", "strategic", "social", "summary")
_INITIALIZE_LOCK = RLock()
_EVENT_LOCK = RLock()


def _hold_local_lock_until_transaction_end(db: Session, lock: RLock) -> Callable[[], None]:
    """Mirror PostgreSQL row-lock lifetime for the local SQLite process."""
    if db.get_bind().dialect.name != "sqlite":
        return lambda: None

    lock.acquire()
    released = False

    def release(_: Session, transaction: SessionTransaction) -> None:
        nonlocal released
        if transaction.parent is None and not released:
            released = True
            lock.release()

    sqlalchemy_event.listen(db, "after_transaction_end", release)

    def release_after_failure() -> None:
        nonlocal released
        if not released:
            released = True
            lock.release()

    return release_after_failure


@dataclass(frozen=True)
class GoalTemplateDefinition:
    template_key: str
    category: str
    title_key: str
    description_key: str
    event_type: str
    target_value: int
    doctrine_keys: tuple[str, ...]
    reward_type: str
    reward_key: str
    catch_up_weeks: int = 2


GOAL_TEMPLATE_DEFINITIONS = (
    GoalTemplateDefinition(
        "establish_company",
        "economic",
        "engagementGoalEstablishCompanyTitle",
        "engagementGoalEstablishCompanyDescription",
        "company.founded",
        1,
        ("industrial_captain", "innovator", "opportunist"),
        "chronicle",
        "company_founder",
    ),
    GoalTemplateDefinition(
        "build_stable_growth",
        "economic",
        "engagementGoalStableGrowthTitle",
        "engagementGoalStableGrowthDescription",
        "company.first_profit",
        2,
        ("industrial_captain", "financial_architect"),
        "knowledge",
        "stable_growth_report",
    ),
    GoalTemplateDefinition(
        "develop_specialists",
        "long_term",
        "engagementGoalSpecialistsTitle",
        "engagementGoalSpecialistsDescription",
        "specialist.assigned",
        2,
        ("innovator", "industrial_captain"),
        "mastery",
        "people_leadership_evidence",
    ),
    GoalTemplateDefinition(
        "support_cartel_project",
        "social",
        "engagementGoalCartelProjectTitle",
        "engagementGoalCartelProjectDescription",
        "cartel.project_contributed",
        2,
        ("networker",),
        "chronicle",
        "cartel_contributor",
    ),
    GoalTemplateDefinition(
        "compare_intelligence",
        "exploration",
        "engagementGoalIntelligenceTitle",
        "engagementGoalIntelligenceDescription",
        "intelligence.report_acquired",
        2,
        ("information_strategist", "opportunist"),
        "knowledge",
        "intelligence_comparison",
    ),
    GoalTemplateDefinition(
        "investigate_world_event",
        "risk",
        "engagementGoalWorldEventTitle",
        "engagementGoalWorldEventDescription",
        "world_event.responded",
        2,
        ("opportunist", "information_strategist"),
        "chronicle",
        "world_event_investigator",
    ),
    GoalTemplateDefinition(
        "complete_ipo",
        "long_term",
        "engagementGoalIpoTitle",
        "engagementGoalIpoDescription",
        "exchange.ipo_completed",
        1,
        ("financial_architect", "industrial_captain"),
        "cosmetic",
        "exchange_pioneer_emblem",
        4,
    ),
    GoalTemplateDefinition(
        "shape_season_legacy",
        "season",
        "engagementGoalSeasonLegacyTitle",
        "engagementGoalSeasonLegacyDescription",
        "season.closed",
        1,
        (),
        "chronicle",
        "season_legacy_entry",
        8,
    ),
)


def ensure_goal_catalog(db: Session) -> list[GoalTemplate]:
    existing = {
        item.template_key: item
        for item in db.scalars(select(GoalTemplate).where(GoalTemplate.version == 1))
    }
    for definition in GOAL_TEMPLATE_DEFINITIONS:
        if definition.template_key in existing:
            continue
        template = GoalTemplate(
            template_key=definition.template_key,
            version=1,
            category=definition.category,
            title_key=definition.title_key,
            description_key=definition.description_key,
            event_type=definition.event_type,
            target_value=definition.target_value,
            unit_key="engagementUnitDecision",
            catch_up_weeks=definition.catch_up_weeks,
            doctrine_keys_json=list(definition.doctrine_keys),
            reward_type=definition.reward_type,
            reward_key=definition.reward_key,
            active=True,
        )
        db.add(template)
        existing[definition.template_key] = template
    db.flush()
    return [existing[item.template_key] for item in GOAL_TEMPLATE_DEFINITIONS]


def _window_bounds(at: datetime) -> tuple[datetime, datetime, datetime]:
    local = as_utc(at).astimezone(BERLIN)
    start_local = (local - timedelta(days=local.weekday())).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    end_local = start_local + timedelta(days=7)
    catch_up_local = end_local + timedelta(days=14)
    return (
        start_local.astimezone(UTC),
        end_local.astimezone(UTC),
        catch_up_local.astimezone(UTC),
    )


def ensure_goal_window(
    db: Session,
    profile: PlayerProfile,
    *,
    at: datetime | None = None,
) -> GoalChoiceWindow:
    now = as_utc(at or datetime.now(UTC))
    starts_at, ends_at, catch_up_until = _window_bounds(now)
    windows = list(
        db.scalars(
            select(GoalChoiceWindow)
            .where(GoalChoiceWindow.profile_id == profile.id)
            .with_for_update()
        )
    )
    current: GoalChoiceWindow | None = None
    for window in windows:
        if as_utc(window.starts_at) == starts_at:
            current = window
        if as_utc(window.catch_up_until) <= now:
            window.status = "closed"
        elif as_utc(window.ends_at) <= now:
            window.status = "catch_up"
    if current is None:
        current = GoalChoiceWindow(
            profile_id=profile.id,
            starts_at=starts_at,
            ends_at=ends_at,
            catch_up_until=catch_up_until,
            max_choices=3,
            status="open",
        )
        db.add(current)
        db.flush()
    templates = ensure_goal_catalog(db)
    existing_template_ids = set(
        db.scalars(
            select(GoalInstance.template_id).where(GoalInstance.choice_window_id == current.id)
        )
    )
    for template in templates:
        if template.id in existing_template_ids or not template.active:
            continue
        db.add(
            GoalInstance(
                template_id=template.id,
                profile_id=profile.id,
                choice_window_id=current.id,
                status="offered",
                target_value=template.target_value,
                progress_value=0,
                recommended_for_doctrine=False,
                idempotency_key=f"offer:{current.id}:{template.id}",
            )
        )
    db.flush()
    return current


def initialize_engagement(
    db: Session,
    user: User,
    profile: PlayerProfile,
    *,
    idempotency_key: str,
) -> GoalChoiceWindow:
    # PostgreSQL serializes this through the profile row lock below. The in-process
    # lock gives the local SQLite target the same one-time initialization semantics.
    release_after_failure = _hold_local_lock_until_transaction_end(db, _INITIALIZE_LOCK)
    succeeded = False
    try:
        result = _initialize_engagement_locked(
            db,
            user,
            profile,
            idempotency_key=idempotency_key,
        )
        succeeded = True
        return result
    finally:
        if not succeeded:
            release_after_failure()


def _initialize_engagement_locked(
    db: Session,
    user: User,
    profile: PlayerProfile,
    *,
    idempotency_key: str,
) -> GoalChoiceWindow:
    previous = get_idempotent(db, user.id, idempotency_key, "engagement.initialize")
    if previous is not None:
        existing = db.get(GoalChoiceWindow, previous.resource_id)
        if existing is not None and existing.profile_id == profile.id:
            return existing
    locked_profile = db.scalar(
        select(PlayerProfile).where(PlayerProfile.id == profile.id).with_for_update()
    )
    if locked_profile is None:
        raise DomainError(409, "profile.missing", "Player profile does not exist")
    window = ensure_goal_window(db, locked_profile)
    ensure_notification_preferences(db, locked_profile)
    ensure_engagement_setting(db, locked_profile)
    remember_idempotent(
        db,
        user.id,
        idempotency_key,
        "engagement.initialize",
        window.id,
        {"goal_window_id": window.id},
    )
    return window


def goal_view(db: Session, goal: GoalInstance) -> dict[str, Any]:
    template = db.get(GoalTemplate, goal.template_id)
    window = db.get(GoalChoiceWindow, goal.choice_window_id)
    if template is None or window is None:
        raise RuntimeError("Goal instance dependencies are missing")
    return {
        "id": goal.id,
        "template_key": template.template_key,
        "category": template.category,
        "title_key": template.title_key,
        "description_key": template.description_key,
        "unit_key": template.unit_key,
        "status": goal.status,
        "target_value": goal.target_value,
        "progress_value": goal.progress_value,
        "recommended_for_doctrine": goal.recommended_for_doctrine,
        "choice_window_id": goal.choice_window_id,
        "selected_at": goal.selected_at,
        "completed_at": goal.completed_at,
        "catch_up_until": window.catch_up_until,
        "reward_type": template.reward_type,
        "reward_key": template.reward_key,
    }


def goal_window_view(db: Session, window: GoalChoiceWindow) -> dict[str, Any]:
    goals = list(
        db.scalars(
            select(GoalInstance)
            .where(GoalInstance.choice_window_id == window.id)
            .order_by(GoalInstance.recommended_for_doctrine.desc(), GoalInstance.created_at)
        )
    )
    selected_count = sum(goal.status in {"active", "completed"} for goal in goals)
    return {
        "id": window.id,
        "starts_at": window.starts_at,
        "ends_at": window.ends_at,
        "catch_up_until": window.catch_up_until,
        "max_choices": window.max_choices,
        "status": window.status,
        "selected_count": selected_count,
        "goals": [goal_view(db, goal) for goal in goals],
    }


def _goal_for_profile(
    db: Session,
    profile: PlayerProfile,
    goal_id: str,
    *,
    lock: bool,
) -> GoalInstance:
    statement = select(GoalInstance).where(
        GoalInstance.id == goal_id,
        GoalInstance.profile_id == profile.id,
    )
    if lock:
        statement = statement.with_for_update()
    goal = db.scalar(statement)
    if goal is None:
        raise DomainError(404, "engagement.goal_not_found", "Personal goal not found")
    return goal


def _apply_event_to_goal(db: Session, goal: GoalInstance, event: EngagementEvent) -> None:
    if goal.status != "active" or goal.progress_value >= goal.target_value:
        return
    template = db.get(GoalTemplate, goal.template_id)
    if template is None or template.event_type != event.event_type:
        return
    existing = db.scalar(
        select(GoalProgress.id).where(
            GoalProgress.goal_instance_id == goal.id,
            GoalProgress.event_id == event.id,
        )
    )
    if existing is not None:
        return
    raw_delta = event.payload_json.get("progress_value", 1)
    delta = raw_delta if isinstance(raw_delta, int) and raw_delta > 0 else 1
    progress_after = min(goal.target_value, goal.progress_value + delta)
    applied_delta = progress_after - goal.progress_value
    if applied_delta <= 0:
        return
    goal.progress_value = progress_after
    db.add(
        GoalProgress(
            goal_instance_id=goal.id,
            event_id=event.id,
            delta_value=applied_delta,
            progress_after=progress_after,
        )
    )
    if progress_after == goal.target_value:
        goal.status = "completed"
        goal.completed_at = event.occurred_at
        reward = db.scalar(
            select(GoalReward).where(
                GoalReward.goal_instance_id == goal.id,
                GoalReward.reward_key == template.reward_key,
            )
        )
        if reward is None:
            db.add(
                GoalReward(
                    goal_instance_id=goal.id,
                    reward_type=template.reward_type,
                    reward_key=template.reward_key,
                    metadata_json={"template_key": template.template_key},
                )
            )
            profile = db.get(PlayerProfile, goal.profile_id)
            if profile is not None:
                create_notification(
                    db,
                    profile.user_id,
                    "engagement.goal.completed",
                    "Personal goal completed",
                    "Your chosen goal is complete. Its non-economic reward is ready.",
                    {
                        "goal_id": goal.id,
                        "template_key": template.template_key,
                        "reward_type": template.reward_type,
                        "reward_key": template.reward_key,
                    },
                    category="summary",
                )


def _replay_goal_events(db: Session, goal: GoalInstance) -> None:
    window = db.get(GoalChoiceWindow, goal.choice_window_id)
    template = db.get(GoalTemplate, goal.template_id)
    if window is None or template is None:
        raise RuntimeError("Goal replay dependencies are missing")
    events = list(
        db.scalars(
            select(EngagementEvent)
            .where(
                EngagementEvent.profile_id == goal.profile_id,
                EngagementEvent.event_type == template.event_type,
                EngagementEvent.occurred_at >= window.starts_at,
            )
            .order_by(EngagementEvent.occurred_at, EngagementEvent.id)
        )
    )
    for event in events:
        _apply_event_to_goal(db, goal, event)


def select_goal(
    db: Session,
    user: User,
    profile: PlayerProfile,
    goal_id: str,
    *,
    idempotency_key: str,
) -> GoalInstance:
    previous = get_idempotent(db, user.id, idempotency_key, "engagement.goal.select")
    if previous is not None:
        existing = db.get(GoalInstance, previous.resource_id)
        if existing is not None and existing.profile_id == profile.id:
            return existing
    goal = _goal_for_profile(db, profile, goal_id, lock=True)
    if goal.status != "offered":
        raise DomainError(409, "engagement.goal_unavailable", "Goal is not available to select")
    window = db.scalar(
        select(GoalChoiceWindow)
        .where(GoalChoiceWindow.id == goal.choice_window_id)
        .with_for_update()
    )
    if window is None or as_utc(window.catch_up_until) <= datetime.now(UTC):
        raise DomainError(409, "engagement.goal_window_closed", "Goal choice window is closed")
    selected_count = int(
        db.scalar(
            select(func.count(GoalInstance.id)).where(
                GoalInstance.choice_window_id == window.id,
                GoalInstance.status.in_(("active", "completed")),
            )
        )
        or 0
    )
    if selected_count >= window.max_choices:
        raise DomainError(409, "engagement.goal_limit", "Choose at most three personal goals")
    goal.status = "active"
    goal.selected_at = datetime.now(UTC)
    _replay_goal_events(db, goal)
    remember_idempotent(
        db,
        user.id,
        idempotency_key,
        "engagement.goal.select",
        goal.id,
        {"goal_id": goal.id},
    )
    return goal


def swap_goal(
    db: Session,
    user: User,
    profile: PlayerProfile,
    goal_id: str,
    replacement_goal_id: str,
    *,
    idempotency_key: str,
) -> GoalInstance:
    previous = get_idempotent(db, user.id, idempotency_key, "engagement.goal.swap")
    if previous is not None:
        existing = db.get(GoalInstance, previous.resource_id)
        if existing is not None and existing.profile_id == profile.id:
            return existing
    current = _goal_for_profile(db, profile, goal_id, lock=True)
    replacement = _goal_for_profile(db, profile, replacement_goal_id, lock=True)
    if current.status != "active" or replacement.status != "offered":
        raise DomainError(
            409,
            "engagement.goal_swap_invalid",
            "Only an active goal can be exchanged for an offered goal",
        )
    if current.choice_window_id != replacement.choice_window_id:
        raise DomainError(
            409,
            "engagement.goal_window_mismatch",
            "Goals must belong to the same choice window",
        )
    window = db.get(GoalChoiceWindow, current.choice_window_id)
    if window is None or as_utc(window.catch_up_until) <= datetime.now(UTC):
        raise DomainError(409, "engagement.goal_window_closed", "Goal choice window is closed")
    now = datetime.now(UTC)
    current.status = "swapped"
    current.swapped_at = now
    replacement.status = "active"
    replacement.selected_at = now
    _replay_goal_events(db, replacement)
    remember_idempotent(
        db,
        user.id,
        idempotency_key,
        "engagement.goal.swap",
        replacement.id,
        {"goal_id": replacement.id, "replaced_goal_id": current.id},
    )
    return replacement


def record_engagement_event(
    db: Session,
    *,
    profile_id: str,
    event_type: str,
    source_type: str,
    source_id: str,
    idempotency_key: str,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> EngagementEvent:
    release_after_failure = _hold_local_lock_until_transaction_end(db, _EVENT_LOCK)
    succeeded = False
    try:
        result = _record_engagement_event_locked(
            db,
            profile_id=profile_id,
            event_type=event_type,
            source_type=source_type,
            source_id=source_id,
            idempotency_key=idempotency_key,
            payload=payload,
            occurred_at=occurred_at,
        )
        succeeded = True
        return result
    finally:
        if not succeeded:
            release_after_failure()


def _record_engagement_event_locked(
    db: Session,
    *,
    profile_id: str,
    event_type: str,
    source_type: str,
    source_id: str,
    idempotency_key: str,
    payload: dict[str, Any] | None,
    occurred_at: datetime | None,
) -> EngagementEvent:
    profile = db.scalar(
        select(PlayerProfile).where(PlayerProfile.id == profile_id).with_for_update()
    )
    if profile is None:
        raise RuntimeError("Engagement event profile is missing")
    for pending in db.new:
        if (
            isinstance(pending, EngagementEvent)
            and pending.world_id == profile.world_id
            and pending.idempotency_key == idempotency_key
        ):
            return pending
    with db.no_autoflush:
        existing = db.scalar(
            select(EngagementEvent).where(
                EngagementEvent.world_id == profile.world_id,
                EngagementEvent.idempotency_key == idempotency_key,
            )
        )
    if existing is not None:
        return existing
    with db.no_autoflush:
        existing_source = db.scalar(
            select(EngagementEvent).where(
                EngagementEvent.profile_id == profile.id,
                EngagementEvent.event_type == event_type,
                EngagementEvent.source_type == source_type,
                EngagementEvent.source_id == source_id,
            )
        )
    if existing_source is not None:
        return existing_source
    event = EngagementEvent(
        world_id=profile.world_id,
        profile_id=profile.id,
        event_type=event_type,
        source_type=source_type,
        source_id=source_id,
        idempotency_key=idempotency_key,
        payload_json=payload or {},
        occurred_at=as_utc(occurred_at or datetime.now(UTC)),
    )
    db.add(event)
    db.flush()
    goals = list(
        db.scalars(
            select(GoalInstance)
            .join(GoalTemplate, GoalTemplate.id == GoalInstance.template_id)
            .where(
                GoalInstance.profile_id == profile.id,
                GoalInstance.status == "active",
                GoalTemplate.event_type == event_type,
            )
            .with_for_update()
        )
    )
    for goal in goals:
        _apply_event_to_goal(db, goal, event)
    from shadowgrid.legacy import project_legacy_event
    from shadowgrid.progression import project_engagement_learning

    project_engagement_learning(db, event)
    project_legacy_event(db, event)
    event.processed_at = datetime.now(UTC)
    return event


def list_open_plans(db: Session, profile: PlayerProfile) -> list[PlayerOpenPlan]:
    return list(
        db.scalars(
            select(PlayerOpenPlan)
            .where(PlayerOpenPlan.profile_id == profile.id)
            .order_by(
                (PlayerOpenPlan.status == "active").desc(),
                PlayerOpenPlan.priority.desc(),
                PlayerOpenPlan.updated_at.desc(),
            )
        )
    )


def create_open_plan(
    db: Session,
    user: User,
    profile: PlayerProfile,
    *,
    category: OpportunityCategory,
    title: str,
    next_step: str,
    target_path: str,
    priority: int,
    idempotency_key: str,
) -> PlayerOpenPlan:
    previous = get_idempotent(db, user.id, idempotency_key, "engagement.plan.create")
    if previous is not None:
        existing = db.get(PlayerOpenPlan, previous.resource_id)
        if existing is not None and existing.profile_id == profile.id:
            return existing
    active_count = int(
        db.scalar(
            select(func.count(PlayerOpenPlan.id)).where(
                PlayerOpenPlan.profile_id == profile.id,
                PlayerOpenPlan.status == "active",
            )
        )
        or 0
    )
    if active_count >= 12:
        raise DomainError(
            409,
            "engagement.open_plan_limit",
            "Complete or archive an open plan before adding another",
        )
    plan = PlayerOpenPlan(
        profile_id=profile.id,
        category=category,
        title=" ".join(title.split()),
        next_step=" ".join(next_step.split()),
        target_path=target_path,
        priority=priority,
        status="active",
        idempotency_key=idempotency_key,
    )
    db.add(plan)
    db.flush()
    remember_idempotent(
        db,
        user.id,
        idempotency_key,
        "engagement.plan.create",
        plan.id,
        {"plan_id": plan.id},
    )
    return plan


def update_open_plan(
    db: Session,
    user: User,
    profile: PlayerProfile,
    plan_id: str,
    *,
    status: str,
    idempotency_key: str,
) -> PlayerOpenPlan:
    previous = get_idempotent(db, user.id, idempotency_key, "engagement.plan.update")
    if previous is not None:
        existing = db.get(PlayerOpenPlan, previous.resource_id)
        if existing is not None and existing.profile_id == profile.id:
            return existing
    plan = db.scalar(
        select(PlayerOpenPlan)
        .where(PlayerOpenPlan.id == plan_id, PlayerOpenPlan.profile_id == profile.id)
        .with_for_update()
    )
    if plan is None:
        raise DomainError(404, "engagement.plan_not_found", "Open plan not found")
    if plan.status != "active" and status == "active":
        raise DomainError(409, "engagement.plan_closed", "Closed plans cannot be reopened")
    plan.status = status
    plan.completed_at = datetime.now(UTC) if status == "completed" else None
    remember_idempotent(
        db,
        user.id,
        idempotency_key,
        "engagement.plan.update",
        plan.id,
        {"plan_id": plan.id, "status": plan.status},
    )
    return plan


def command_center(db: Session, profile: PlayerProfile) -> dict[str, Any]:
    active_plans = list(
        db.scalars(
            select(PlayerOpenPlan)
            .where(
                PlayerOpenPlan.profile_id == profile.id,
                PlayerOpenPlan.status == "active",
            )
            .order_by(PlayerOpenPlan.priority.desc(), PlayerOpenPlan.updated_at.desc())
        )
    )
    active_goals = list(
        db.scalars(
            select(GoalInstance)
            .where(
                GoalInstance.profile_id == profile.id,
                GoalInstance.status == "active",
            )
            .order_by(GoalInstance.selected_at)
        )
    )
    offered_goals = list(
        db.scalars(
            select(GoalInstance)
            .where(
                GoalInstance.profile_id == profile.id,
                GoalInstance.status == "offered",
            )
            .order_by(GoalInstance.recommended_for_doctrine.desc(), GoalInstance.created_at)
        )
    )
    opportunities: list[dict[str, Any]] = []
    used_categories: set[str] = set()
    for plan in active_plans:
        if plan.category in used_categories:
            continue
        opportunities.append(
            {
                "category": plan.category,
                "source_type": "plan",
                "source_id": plan.id,
                "title": plan.title,
                "detail": plan.next_step,
                "target_path": plan.target_path,
                "priority": plan.priority,
            }
        )
        used_categories.add(plan.category)
    if "strategic" not in used_categories and active_goals:
        item = goal_view(db, active_goals[0])
        opportunities.append(
            {
                "category": "strategic",
                "source_type": "goal",
                "source_id": item["id"],
                "title": item["title_key"],
                "detail": item["description_key"],
                "target_path": "/engagement",
                "priority": 70,
            }
        )
        used_categories.add("strategic")
    if "discoverable" not in used_categories and offered_goals:
        item = goal_view(db, offered_goals[0])
        opportunities.append(
            {
                "category": "discoverable",
                "source_type": "goal",
                "source_id": item["id"],
                "title": item["title_key"],
                "detail": item["description_key"],
                "target_path": "/engagement",
                "priority": 40,
            }
        )
    category_order = {"urgent": 0, "strategic": 1, "discoverable": 2}
    opportunities.sort(
        key=lambda item: (category_order[str(item["category"])], -int(item["priority"]))
    )
    opportunities = opportunities[:3]
    return {
        "opportunities": opportunities,
        "active_goal_count": len(active_goals),
        "open_plan_count": len(active_plans),
        "natural_break_available": not any(item["category"] == "urgent" for item in opportunities),
    }


def _profile_snapshot(db: Session, profile: PlayerProfile) -> dict[str, Any]:
    balance = db.get(ResourceBalance, profile.id)
    if balance is None:
        raise RuntimeError("Profile resource balance is missing")
    return {
        "cash": str(Decimal(balance.cash)),
        "capital": str(Decimal(balance.capital)),
        "influence": str(Decimal(balance.influence)),
        "intelligence": str(Decimal(balance.intelligence)),
        "stability": profile.stability,
        "investigation_pressure": profile.investigation_pressure,
    }


def start_session(
    db: Session,
    profile: PlayerProfile,
    *,
    client_session_key: str,
) -> PlayerSession:
    existing = db.scalar(
        select(PlayerSession).where(
            PlayerSession.profile_id == profile.id,
            PlayerSession.client_session_key == client_session_key,
        )
    )
    if existing is not None:
        return existing
    now = datetime.now(UTC)
    old_sessions = list(
        db.scalars(
            select(PlayerSession)
            .where(
                PlayerSession.profile_id == profile.id,
                PlayerSession.status == "active",
            )
            .with_for_update()
        )
    )
    for old in old_sessions:
        old.status = "abandoned"
        old.ended_at = now
    session = PlayerSession(
        profile_id=profile.id,
        client_session_key=client_session_key,
        status="active",
        initial_snapshot_json=_profile_snapshot(db, profile),
        started_at=now,
        last_activity_at=now,
    )
    db.add(session)
    db.flush()
    return session


def _summary_changes(
    db: Session, profile: PlayerProfile, session: PlayerSession
) -> list[dict[str, Any]]:
    before = session.initial_snapshot_json
    after = _profile_snapshot(db, profile)
    changes: list[dict[str, Any]] = []
    for key in sorted(after):
        if before.get(key) != after[key]:
            changes.append({"field": key, "before": before.get(key), "after": after[key]})
    return changes


def finish_session(
    db: Session,
    profile: PlayerProfile,
    session_id: str,
    *,
    decision_keys: list[str],
) -> SessionSummary:
    session = db.scalar(
        select(PlayerSession)
        .where(PlayerSession.id == session_id, PlayerSession.profile_id == profile.id)
        .with_for_update()
    )
    if session is None:
        raise DomainError(404, "engagement.session_not_found", "Play session not found")
    existing = db.scalar(select(SessionSummary).where(SessionSummary.session_id == session.id))
    if existing is not None:
        return existing
    if session.status != "active":
        raise DomainError(409, "engagement.session_closed", "Play session is already closed")
    now = datetime.now(UTC)
    events = list(
        db.scalars(
            select(EngagementEvent)
            .where(
                EngagementEvent.profile_id == profile.id,
                EngagementEvent.occurred_at >= session.started_at,
                EngagementEvent.occurred_at <= now,
            )
            .order_by(EngagementEvent.occurred_at, EngagementEvent.id)
        )
    )
    decisions: list[dict[str, Any]] = [
        {
            "event_type": event.event_type,
            "source_type": event.source_type,
            "source_id": event.source_id,
            "occurred_at": event.occurred_at.isoformat(),
        }
        for event in events[:20]
    ]
    decisions.extend({"context_key": key} for key in decision_keys[: max(0, 20 - len(decisions))])
    plans = [
        {
            "id": plan.id,
            "category": plan.category,
            "title": plan.title,
            "next_step": plan.next_step,
            "target_path": plan.target_path,
        }
        for plan in list_open_plans(db, profile)
        if plan.status == "active"
    ][:12]
    center = command_center(db, profile)
    duration_seconds = max(0, int((now - as_utc(session.started_at)).total_seconds()))
    summary = SessionSummary(
        session_id=session.id,
        profile_id=profile.id,
        duration_seconds=duration_seconds,
        decisions_json=decisions,
        changes_json=_summary_changes(db, profile, session),
        open_plans_json=plans,
        next_entry_points_json=list(center["opportunities"]),
        natural_break_reached=bool(center["natural_break_available"]),
    )
    session.status = "completed"
    session.last_activity_at = now
    session.ended_at = now
    db.add(summary)
    db.flush()
    return summary


def latest_session_summary(db: Session, profile: PlayerProfile) -> SessionSummary | None:
    return db.scalar(
        select(SessionSummary)
        .where(SessionSummary.profile_id == profile.id)
        .order_by(SessionSummary.created_at.desc())
        .limit(1)
    )


def generate_return_briefing(db: Session, profile: PlayerProfile) -> ReturnBriefing:
    latest_session = db.scalar(
        select(PlayerSession)
        .where(
            PlayerSession.profile_id == profile.id,
            PlayerSession.status == "completed",
            PlayerSession.ended_at.is_not(None),
        )
        .order_by(PlayerSession.ended_at.desc())
        .limit(1)
    )
    since_at = (
        as_utc(latest_session.ended_at)
        if latest_session and latest_session.ended_at
        else as_utc(profile.created_at)
    )
    existing = db.scalar(
        select(ReturnBriefing).where(
            ReturnBriefing.profile_id == profile.id,
            ReturnBriefing.since_at == since_at,
        )
    )
    if existing is not None:
        return existing
    world_events = list(
        db.scalars(
            select(WorldEventInstance)
            .where(
                WorldEventInstance.world_id == profile.world_id,
                WorldEventInstance.starts_at >= since_at,
            )
            .order_by(WorldEventInstance.starts_at.desc())
            .limit(10)
        )
    )
    owned_company_ids = list(
        db.scalars(
            select(CompanyOwnership.company_id).where(
                CompanyOwnership.owner_profile_id == profile.id,
                CompanyOwnership.ownership_bps > 0,
            )
        )
    )
    company_reports = (
        list(
            db.scalars(
                select(CompanyEconomyReport)
                .where(
                    CompanyEconomyReport.company_id.in_(owned_company_ids),
                    CompanyEconomyReport.created_at >= since_at,
                )
                .order_by(CompanyEconomyReport.created_at.desc())
                .limit(20)
            )
        )
        if owned_company_ids
        else []
    )
    company_names = (
        {
            company.id: company.name
            for company in db.scalars(select(Company).where(Company.id.in_(owned_company_ids)))
        }
        if owned_company_ids
        else {}
    )
    goals = list(
        db.scalars(
            select(GoalInstance).where(
                GoalInstance.profile_id == profile.id,
                GoalInstance.status == "active",
            )
        )
    )
    engagement_events = list(
        db.scalars(
            select(EngagementEvent)
            .where(
                EngagementEvent.profile_id == profile.id,
                EngagementEvent.occurred_at >= since_at,
            )
            .order_by(EngagementEvent.occurred_at.desc())
            .limit(20)
        )
    )
    center = command_center(db, profile)
    briefing = ReturnBriefing(
        profile_id=profile.id,
        since_at=since_at,
        world_changes_json=[
            {
                "event_id": item.id,
                "event_key": item.event_key,
                "title": item.title,
                "status": item.status,
                "starts_at": item.starts_at.isoformat(),
                "ends_at": item.ends_at.isoformat(),
            }
            for item in world_events
        ],
        company_changes_json=[
            {
                "company_id": item.company_id,
                "company_name": company_names.get(item.company_id, item.company_id),
                "profit_cents": item.profit_cents,
                "created_at": item.created_at.isoformat(),
            }
            for item in company_reports
        ],
        relevant_decisions_json=[goal_view(db, item) for item in goals],
        available_content_json=[
            {
                "event_type": item.event_type,
                "source_type": item.source_type,
                "source_id": item.source_id,
                "occurred_at": item.occurred_at.isoformat(),
            }
            for item in engagement_events
        ],
        entry_points_json=list(center["opportunities"]),
    )
    db.add(briefing)
    db.flush()
    return briefing


def acknowledge_return_briefing(
    db: Session,
    profile: PlayerProfile,
    briefing_id: str,
) -> ReturnBriefing:
    briefing = db.scalar(
        select(ReturnBriefing)
        .where(ReturnBriefing.id == briefing_id, ReturnBriefing.profile_id == profile.id)
        .with_for_update()
    )
    if briefing is None:
        raise DomainError(404, "engagement.briefing_not_found", "Return briefing not found")
    if briefing.acknowledged_at is None:
        briefing.acknowledged_at = datetime.now(UTC)
    return briefing


def ensure_notification_preferences(
    db: Session,
    profile: PlayerProfile,
) -> list[NotificationPreference]:
    existing = {
        item.category: item
        for item in db.scalars(
            select(NotificationPreference).where(NotificationPreference.profile_id == profile.id)
        )
    }
    for category in NOTIFICATION_CATEGORIES:
        if category in existing:
            continue
        preference = NotificationPreference(
            profile_id=profile.id,
            category=category,
            live_enabled=True,
            digest_frequency="immediate" if category == "critical" else "daily",
            quiet_start_minute=1_320,
            quiet_end_minute=420,
            timezone="Europe/Berlin",
        )
        db.add(preference)
        existing[category] = preference
    db.flush()
    return [existing[category] for category in NOTIFICATION_CATEGORIES]


def update_notification_preference(
    db: Session,
    profile: PlayerProfile,
    category: str,
    *,
    live_enabled: bool,
    digest_frequency: str,
    quiet_start_minute: int,
    quiet_end_minute: int,
    timezone: str,
) -> NotificationPreference:
    try:
        ZoneInfo(timezone)
    except ZoneInfoNotFoundError as exc:
        raise DomainError(
            422,
            "engagement.timezone_invalid",
            "Notification timezone must be a valid IANA timezone",
        ) from exc
    ensure_notification_preferences(db, profile)
    preference = db.scalar(
        select(NotificationPreference)
        .where(
            NotificationPreference.profile_id == profile.id,
            NotificationPreference.category == category,
        )
        .with_for_update()
    )
    if preference is None:
        raise RuntimeError("Notification preference was not created")
    if category == "critical":
        preference.live_enabled = True
        preference.digest_frequency = "immediate"
    else:
        preference.live_enabled = live_enabled
        preference.digest_frequency = digest_frequency
    preference.quiet_start_minute = quiet_start_minute
    preference.quiet_end_minute = quiet_end_minute
    preference.timezone = timezone
    return preference


def ensure_engagement_setting(db: Session, profile: PlayerProfile) -> EngagementSetting:
    setting = db.scalar(select(EngagementSetting).where(EngagementSetting.profile_id == profile.id))
    if setting is None:
        setting = EngagementSetting(profile_id=profile.id)
        db.add(setting)
        db.flush()
    return setting


def update_engagement_setting(
    db: Session,
    profile: PlayerProfile,
    *,
    adaptive_help_enabled: bool,
    session_summary_enabled: bool,
    ranking_visible: bool,
    information_density: str,
) -> EngagementSetting:
    setting = ensure_engagement_setting(db, profile)
    setting.adaptive_help_enabled = adaptive_help_enabled
    setting.session_summary_enabled = session_summary_enabled
    setting.ranking_visible = ranking_visible
    setting.information_density = information_density
    return setting


def evaluate_guardrails(
    db: Session,
    *,
    world_id: str | None,
    idempotency_key: str,
    wellbeing_status: str,
    wellbeing_signals: dict[str, int],
    technical_status: str,
    accessibility_status: str,
    voluntary_return_status: str,
) -> EngagementGuardrailEvaluation:
    existing = db.scalar(
        select(EngagementGuardrailEvaluation).where(
            EngagementGuardrailEvaluation.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return existing
    simulation = run_simulation()
    cartel_dominance_bps = max(item.cartel_dominance_bps for item in simulation.seasons)
    newcomer_wealth_bps = min(item.new_to_early_wealth_bps for item in simulation.seasons)
    negative_account_count = int(
        db.scalar(
            select(func.count(Account.id)).where(
                Account.owner_type != "system",
                Account.balance_cents < 0,
            )
        )
        or 0
    )
    negative_resource_count = int(
        db.scalar(select(func.count(ResourceBalance.profile_id)).where(ResourceBalance.cash < 0))
        or 0
    )
    imbalanced_rows = list(
        db.execute(
            select(
                AccountLedgerEntry.transaction_id,
                func.sum(AccountLedgerEntry.amount_cents),
            )
            .group_by(AccountLedgerEntry.transaction_id)
            .having(func.sum(AccountLedgerEntry.amount_cents) != 0)
        ).all()
    )
    ledger_imbalance_cents = sum(abs(int(row[1] or 0)) for row in imbalanced_rows)
    reasons: list[str] = []
    if simulation.strategy_spread_bps > 2_000:
        reasons.append("strategy_spread_exceeds_2000_bps")
    if cartel_dominance_bps > 2_500:
        reasons.append("cartel_dominance_exceeds_2500_bps")
    if newcomer_wealth_bps < 8_000:
        reasons.append("newcomer_wealth_below_8000_bps")
    if ledger_imbalance_cents != 0:
        reasons.append("ledger_imbalance_detected")
    if negative_account_count + negative_resource_count != 0:
        reasons.append("negative_balance_detected")
    if wellbeing_status != "passed":
        reasons.append(f"wellbeing_{wellbeing_status}")
    if technical_status != "passed":
        reasons.append(f"technical_{technical_status}")
    if accessibility_status != "passed":
        reasons.append(f"accessibility_{accessibility_status}")
    if voluntary_return_status != "passed":
        reasons.append(f"voluntary_return_{voluntary_return_status}")
    signal_thresholds = {
        "very_long_sessions_delta_bps": 1_000,
        "push_disable_delta_bps": 500,
        "obligation_reports": 0,
        "fear_motivated_return_bps": 5_000,
        "absence_pressure_reports": 0,
        "exhaustion_after_session_bps": 5_000,
    }
    for signal, maximum in signal_thresholds.items():
        if wellbeing_signals[signal] > maximum:
            reasons.append(f"wellbeing_signal_{signal}")
    evaluation = EngagementGuardrailEvaluation(
        world_id=world_id,
        idempotency_key=idempotency_key,
        strategy_spread_bps=simulation.strategy_spread_bps,
        cartel_dominance_bps=cartel_dominance_bps,
        newcomer_wealth_bps=newcomer_wealth_bps,
        ledger_imbalance_cents=ledger_imbalance_cents,
        negative_balance_count=negative_account_count + negative_resource_count,
        wellbeing_status=wellbeing_status,
        technical_status=technical_status,
        accessibility_status=accessibility_status,
        voluntary_return_status=voluntary_return_status,
        wellbeing_signals_json=dict(wellbeing_signals),
        passed=not reasons,
        reasons_json=reasons,
    )
    db.add(evaluation)
    db.flush()
    return evaluation


def _basis_points(numerator: int, denominator: int) -> int:
    if denominator <= 0:
        return 0
    return min(10_000, max(0, (numerator * 10_000) // denominator))


def _milestone_return_bps(
    profiles: list[PlayerProfile],
    event_times: dict[str, list[datetime]],
    *,
    days: int,
    at: datetime,
) -> int:
    eligible = [
        profile for profile in profiles if as_utc(profile.created_at) + timedelta(days=days) <= at
    ]
    returned = sum(
        1
        for profile in eligible
        if any(
            occurred_at >= as_utc(profile.created_at) + timedelta(days=days)
            for occurred_at in event_times.get(profile.id, [])
        )
    )
    return _basis_points(returned, len(eligible))


def aggregate_engagement_metrics(
    db: Session,
    *,
    world_id: str | None,
    idempotency_key: str,
    metric_date: date | None = None,
    satisfaction_bps: int | None = None,
    fairness_bps: int | None = None,
    survey_response_count: int = 0,
    now: datetime | None = None,
) -> EngagementMetricDaily:
    existing = db.scalar(
        select(EngagementMetricDaily).where(
            EngagementMetricDaily.idempotency_key == idempotency_key
        )
    )
    if existing is not None:
        return existing
    timestamp = as_utc(now or datetime.now(UTC))
    day = metric_date or timestamp.date()
    scope_key = world_id or "global"
    daily = db.scalar(
        select(EngagementMetricDaily).where(
            EngagementMetricDaily.scope_key == scope_key,
            EngagementMetricDaily.metric_date == day,
            EngagementMetricDaily.cohort_key == "all",
        )
    )
    if daily is not None:
        return daily

    profile_query = select(PlayerProfile)
    if world_id is not None:
        profile_query = profile_query.where(PlayerProfile.world_id == world_id)
    profiles = list(db.scalars(profile_query))
    profile_ids = [profile.id for profile in profiles]
    event_times: dict[str, list[datetime]] = {profile.id: [] for profile in profiles}
    event_types: dict[str, set[str]] = {profile.id: set() for profile in profiles}
    if profile_ids:
        for profile_id, event_type, occurred_at in db.execute(
            select(
                EngagementEvent.profile_id,
                EngagementEvent.event_type,
                EngagementEvent.occurred_at,
            ).where(EngagementEvent.profile_id.in_(profile_ids))
        ):
            event_times[profile_id].append(as_utc(occurred_at))
            event_types[profile_id].add(event_type)
    active_profile_count = sum(
        1
        for profile in profiles
        if any(
            occurred_at >= timestamp - timedelta(days=7) for occurred_at in event_times[profile.id]
        )
    )
    meaningful_decision_count = sum(len(items) for items in event_times.values())
    diverse_profiles = sum(1 for items in event_types.values() if len(items) >= 2)

    goal_total = 0
    goal_completed = 0
    season_profiles: set[str] = set()
    social_profiles: set[str] = set()
    return_contracts: list[ReturnContract] = []
    story_progress_count = 0
    collection_owned_count = 0
    if profile_ids:
        goal_total = int(
            db.scalar(
                select(func.count())
                .select_from(GoalInstance)
                .where(GoalInstance.profile_id.in_(profile_ids))
            )
            or 0
        )
        goal_completed = int(
            db.scalar(
                select(func.count())
                .select_from(GoalInstance)
                .where(
                    GoalInstance.profile_id.in_(profile_ids),
                    GoalInstance.status == "completed",
                )
            )
            or 0
        )
        season_profiles = set(
            db.scalars(
                select(PlayerSeasonGoal.profile_id)
                .where(PlayerSeasonGoal.profile_id.in_(profile_ids))
                .distinct()
            )
        )
        social_profiles.update(
            db.scalars(
                select(OrganizationMembership.profile_id)
                .where(
                    OrganizationMembership.profile_id.in_(profile_ids),
                    OrganizationMembership.status == "active",
                )
                .distinct()
            )
        )
        for mentor_id, mentee_id in db.execute(
            select(Mentorship.mentor_profile_id, Mentorship.mentee_profile_id).where(
                (Mentorship.mentor_profile_id.in_(profile_ids))
                | (Mentorship.mentee_profile_id.in_(profile_ids)),
                Mentorship.status.in_(("active", "completed")),
            )
        ):
            if mentor_id in event_times:
                social_profiles.add(mentor_id)
            if mentee_id in event_times:
                social_profiles.add(mentee_id)
        return_contracts = list(
            db.scalars(select(ReturnContract).where(ReturnContract.profile_id.in_(profile_ids)))
        )
        story_progress_count = int(
            db.scalar(
                select(func.count())
                .select_from(NarrativeChronicleEntry)
                .where(
                    (NarrativeChronicleEntry.profile_id.in_(profile_ids))
                    | (NarrativeChronicleEntry.world_id == world_id)
                )
            )
            or 0
        )
        collection_owned_count = int(
            db.scalar(
                select(func.count())
                .select_from(PlayerCollection)
                .where(PlayerCollection.profile_id.in_(profile_ids))
            )
            or 0
        )

    def pause_return_bps(days: int) -> int:
        eligible = [item for item in return_contracts if item.absence_days >= days]
        returned = sum(1 for item in eligible if item.status in ("active", "completed"))
        return _basis_points(returned, len(eligible))

    summary_total = (
        int(
            db.scalar(
                select(func.count())
                .select_from(SessionSummary)
                .where(SessionSummary.profile_id.in_(profile_ids))
            )
            or 0
        )
        if profile_ids
        else 0
    )
    natural_break_count = (
        int(
            db.scalar(
                select(func.count())
                .select_from(SessionSummary)
                .where(
                    SessionSummary.profile_id.in_(profile_ids),
                    SessionSummary.natural_break_reached.is_(True),
                )
            )
            or 0
        )
        if profile_ids
        else 0
    )
    catalog_count = int(db.scalar(select(func.count()).select_from(CollectionItem)) or 0)
    survey_visible = survey_response_count >= 5
    metric = EngagementMetricDaily(
        world_id=world_id,
        scope_key=scope_key,
        metric_date=day,
        cohort_key="all",
        idempotency_key=idempotency_key,
        profile_count=len(profiles),
        active_profile_count=active_profile_count,
        d1_return_bps=_milestone_return_bps(profiles, event_times, days=1, at=timestamp),
        d7_return_bps=_milestone_return_bps(profiles, event_times, days=7, at=timestamp),
        d30_return_bps=_milestone_return_bps(profiles, event_times, days=30, at=timestamp),
        weekly_return_bps=_basis_points(active_profile_count, len(profiles)),
        goal_completion_bps=_basis_points(goal_completed, goal_total),
        meaningful_decision_count=meaningful_decision_count,
        strategy_diversity_bps=_basis_points(diverse_profiles, active_profile_count),
        season_participation_bps=_basis_points(len(season_profiles), len(profiles)),
        socially_engaged_bps=_basis_points(len(social_profiles), len(profiles)),
        pause_return_7_bps=pause_return_bps(7),
        pause_return_14_bps=pause_return_bps(14),
        pause_return_30_bps=pause_return_bps(30),
        satisfaction_bps=satisfaction_bps if survey_visible else None,
        fairness_bps=fairness_bps if survey_visible else None,
        survey_response_count=survey_response_count,
        natural_break_bps=_basis_points(natural_break_count, summary_total),
        story_progress_count=story_progress_count,
        collection_completion_bps=_basis_points(
            collection_owned_count, len(profiles) * catalog_count
        ),
    )
    db.add(metric)
    db.flush()
    return metric


def list_engagement_metrics(
    db: Session,
    *,
    world_id: str | None,
    limit: int = 30,
) -> list[EngagementMetricDaily]:
    query = select(EngagementMetricDaily)
    if world_id is None:
        query = query.where(EngagementMetricDaily.world_id.is_(None))
    else:
        query = query.where(EngagementMetricDaily.world_id == world_id)
    return list(db.scalars(query.order_by(EngagementMetricDaily.metric_date.desc()).limit(limit)))


def update_rollout(
    db: Session,
    user: User,
    *,
    feature_key: str,
    cohort_bps: int,
) -> EngagementRollout:
    latest = db.scalar(
        select(EngagementGuardrailEvaluation)
        .order_by(EngagementGuardrailEvaluation.evaluated_at.desc())
        .limit(1)
    )
    if latest is None or not latest.passed:
        raise DomainError(
            409,
            "engagement.guardrail_required",
            "A passing economic and wellbeing evaluation is required before rollout",
        )
    rollout = db.scalar(
        select(EngagementRollout)
        .where(EngagementRollout.feature_key == feature_key)
        .with_for_update()
    )
    if rollout is None:
        if cohort_bps != 0:
            raise DomainError(
                409,
                "engagement.rollout_order",
                "Begin with the internal cohort before staged rollout",
            )
        rollout = EngagementRollout(feature_key=feature_key)
        db.add(rollout)
        db.flush()
    allowed_next = {0: 500, 500: 2_000, 2_000: 5_000, 5_000: 10_000, 10_000: 10_000}
    if cohort_bps > rollout.cohort_bps and cohort_bps != allowed_next[rollout.cohort_bps]:
        raise DomainError(
            409,
            "engagement.rollout_order",
            "Rollout must advance through 5, 20, 50 and 100 percent cohorts",
        )
    rollout.cohort_bps = cohort_bps
    rollout.status = (
        "internal" if cohort_bps == 0 else "active" if cohort_bps == 10_000 else "staged"
    )
    rollout.last_evaluation_id = latest.id
    rollout.updated_by_user_id = user.id
    return rollout
