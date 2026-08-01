from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.domain import create_notification
from shadowgrid.errors import DomainError
from shadowgrid.game_config import ROLE_PERMISSIONS
from shadowgrid.models import (
    AdaptiveHelpOffer,
    CartelChronicleEntry,
    CartelDelegation,
    CartelMembershipPause,
    DoctrineSelection,
    EngagementEvent,
    EngagementSetting,
    GoalInstance,
    GoalTemplate,
    MasteryEntry,
    MasteryProgress,
    MentoringMilestone,
    Mentorship,
    OrganizationMembership,
    OutcomeReport,
    PersonalSuccessChain,
    PlayerDoctrine,
    PlayerProfile,
    as_utc,
)

DOCTRINES = {
    "industrial_captain": {
        "title_key": "engagementDoctrineIndustrialCaptain",
        "description_key": "engagementDoctrineIndustrialCaptainDescription",
        "focus_areas": ["company_management", "people_leadership"],
    },
    "financial_architect": {
        "title_key": "engagementDoctrineFinancialArchitect",
        "description_key": "engagementDoctrineFinancialArchitectDescription",
        "focus_areas": ["capital_markets", "market_analysis"],
    },
    "innovator": {
        "title_key": "engagementDoctrineInnovator",
        "description_key": "engagementDoctrineInnovatorDescription",
        "focus_areas": ["people_leadership", "company_management"],
    },
    "real_estate_strategist": {
        "title_key": "engagementDoctrineRealEstateStrategist",
        "description_key": "engagementDoctrineRealEstateStrategistDescription",
        "focus_areas": ["real_estate", "market_analysis"],
    },
    "networker": {
        "title_key": "engagementDoctrineNetworker",
        "description_key": "engagementDoctrineNetworkerDescription",
        "focus_areas": ["cartel_leadership", "diplomacy"],
    },
    "information_strategist": {
        "title_key": "engagementDoctrineInformationStrategist",
        "description_key": "engagementDoctrineInformationStrategistDescription",
        "focus_areas": ["intelligence", "risk_management"],
    },
    "opportunist": {
        "title_key": "engagementDoctrineOpportunist",
        "description_key": "engagementDoctrineOpportunistDescription",
        "focus_areas": ["risk_management", "season_strategy"],
    },
}

MASTERY_AREAS = (
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
)

EVENT_LEARNING: dict[str, tuple[str, str, int]] = {
    "company.founded": ("company_management", "found_company", 20),
    "company.first_profit": ("company_management", "stabilize_profit", 25),
    "specialist.assigned": ("people_leadership", "assign_specialist", 20),
    "exchange.ipo_completed": ("capital_markets", "complete_ipo", 35),
    "cartel.project_contributed": ("cartel_leadership", "project_contribution", 15),
    "intelligence.report_acquired": ("intelligence", "compare_report", 15),
    "world_event.responded": ("risk_management", "world_event_response", 20),
    "season.closed": ("season_strategy", "complete_season", 40),
}

OUTCOME_TITLES = {
    "company.founded": "engagementOutcomeCompanyFoundedTitle",
    "company.first_profit": "engagementOutcomeFirstProfitTitle",
    "specialist.assigned": "engagementOutcomeSpecialistAssignedTitle",
    "exchange.ipo_completed": "engagementOutcomeIpoCompletedTitle",
    "cartel.project_contributed": "engagementOutcomeCartelContributionTitle",
    "intelligence.report_acquired": "engagementOutcomeIntelligenceTitle",
    "world_event.responded": "engagementOutcomeWorldEventTitle",
    "season.closed": "engagementOutcomeSeasonClosedTitle",
}

KNOWLEDGE_KEYS = {
    area: "engagementKnowledge" + "".join(part.title() for part in area.split("_"))
    for area in MASTERY_AREAS
}

OUTCOME_REPORT_KEYS: dict[str, tuple[str, list[str], list[str], list[str], list[str]]] = {
    event_type: (
        OUTCOME_TITLES[event_type],
        ["engagementOutcomeControllableChoice", "engagementOutcomeControllablePreparation"],
        ["engagementOutcomeExternalWorld", "engagementOutcomeExternalMarket"],
        ["engagementOutcomeWorkedDiversification"],
        ["engagementOutcomeAlternativeReview"],
    )
    for event_type in EVENT_LEARNING
}

SUCCESS_EVENTS = ("company.founded", "company.first_profit", "specialist.assigned")

DELEGATABLE_ROLES: dict[str, list[str]] = {
    "economic_analyst": ["organization.view", "treasury.view", "audit.view"],
    "diplomat": ["organization.view", "diplomacy.view", "diplomacy.propose"],
    "intelligence_coordinator": [
        "organization.view",
        "intel.view_shared",
        "intel.share",
        "operations.view",
    ],
    "project_manager": ["organization.view", "projects.view", "projects.create"],
    "trainer": ["organization.view", "mentoring.view"],
    "archivist": ["organization.view", "chronicle.view", "chronicle.create"],
    "event_planner": ["organization.view", "projects.view", "operations.view"],
}


def doctrine_catalog() -> list[dict[str, object]]:
    return [
        {
            "key": key,
            "title_key": value["title_key"],
            "description_key": value["description_key"],
            "focus_areas": value["focus_areas"],
            "economic_bonus": False,
            "reversible": True,
        }
        for key, value in DOCTRINES.items()
    ]


def choose_doctrine(
    db: Session,
    profile: PlayerProfile,
    *,
    doctrine_key: str,
    idempotency_key: str,
) -> PlayerDoctrine:
    if doctrine_key not in DOCTRINES:
        raise DomainError(422, "engagement.invalid_doctrine", "Unsupported doctrine")
    existing_selection = db.scalar(
        select(DoctrineSelection).where(
            DoctrineSelection.profile_id == profile.id,
            DoctrineSelection.idempotency_key == idempotency_key,
        )
    )
    if existing_selection is not None:
        projection = db.scalar(
            select(PlayerDoctrine).where(PlayerDoctrine.profile_id == profile.id)
        )
        if projection is None or projection.selection_id != existing_selection.id:
            raise DomainError(409, "engagement.idempotency_conflict", "Doctrine key was reused")
        return projection
    projection = db.scalar(
        select(PlayerDoctrine).where(PlayerDoctrine.profile_id == profile.id).with_for_update()
    )
    previous = projection.doctrine_key if projection is not None else None
    selection = DoctrineSelection(
        profile_id=profile.id,
        doctrine_key=doctrine_key,
        previous_doctrine_key=previous,
        reason="player_choice",
        idempotency_key=idempotency_key,
    )
    db.add(selection)
    db.flush()
    now = datetime.now(UTC)
    if projection is None:
        projection = PlayerDoctrine(
            profile_id=profile.id,
            doctrine_key=doctrine_key,
            selection_id=selection.id,
            selected_at=now,
            changed_at=now,
        )
        db.add(projection)
    else:
        projection.doctrine_key = doctrine_key
        projection.selection_id = selection.id
        projection.version += 1
        projection.changed_at = now
    goals = db.scalars(
        select(GoalInstance)
        .join(GoalTemplate, GoalTemplate.id == GoalInstance.template_id)
        .where(
            GoalInstance.profile_id == profile.id,
            GoalInstance.status.in_(("offered", "active")),
        )
    ).all()
    for goal in goals:
        template = db.get(GoalTemplate, goal.template_id)
        goal.recommended_for_doctrine = bool(
            template is not None and doctrine_key in template.doctrine_keys_json
        )
    db.flush()
    return projection


def _mastery_level(points: int) -> int:
    thresholds = (0, 20, 50, 90, 140, 200, 275, 365, 470, 590, 725)
    return max(index for index, threshold in enumerate(thresholds) if points >= threshold)


def award_mastery(
    db: Session,
    *,
    profile_id: str,
    area_key: str,
    decision_key: str,
    source_type: str,
    source_id: str,
    base_points: int,
) -> MasteryEntry:
    existing = db.scalar(
        select(MasteryEntry).where(
            MasteryEntry.profile_id == profile_id,
            MasteryEntry.area_key == area_key,
            MasteryEntry.source_type == source_type,
            MasteryEntry.source_id == source_id,
        )
    )
    if existing is not None:
        return existing
    repeated = int(
        db.scalar(
            select(func.count())
            .select_from(MasteryEntry)
            .where(
                MasteryEntry.profile_id == profile_id,
                MasteryEntry.area_key == area_key,
                MasteryEntry.decision_key == decision_key,
            )
        )
        or 0
    )
    diversity_bps = (10_000, 5_000, 2_500)[min(repeated, 2)] if repeated < 3 else 1_000
    points = max(1, base_points * diversity_bps // 10_000)
    entry = MasteryEntry(
        profile_id=profile_id,
        area_key=area_key,
        decision_key=decision_key,
        source_type=source_type,
        source_id=source_id,
        base_points=base_points,
        diversity_bps=diversity_bps,
        points=points,
    )
    db.add(entry)
    progress = db.scalar(
        select(MasteryProgress)
        .where(
            MasteryProgress.profile_id == profile_id,
            MasteryProgress.area_key == area_key,
        )
        .with_for_update()
    )
    if progress is None:
        progress = MasteryProgress(
            profile_id=profile_id,
            area_key=area_key,
            points=0,
            level=0,
            distinct_decisions_json=[],
        )
        db.add(progress)
        db.flush()
    progress.points += points
    progress.level = _mastery_level(progress.points)
    progress.distinct_decisions_json = sorted(
        set([*progress.distinct_decisions_json, decision_key])
    )
    db.flush()
    return entry


def ensure_mastery_progress(db: Session, profile: PlayerProfile) -> list[MasteryProgress]:
    existing = {
        item.area_key: item
        for item in db.scalars(
            select(MasteryProgress).where(MasteryProgress.profile_id == profile.id)
        )
    }
    for area in MASTERY_AREAS:
        if area not in existing:
            progress = MasteryProgress(profile_id=profile.id, area_key=area)
            db.add(progress)
            existing[area] = progress
    db.flush()
    return [existing[area] for area in MASTERY_AREAS]


def _sync_success_chain(db: Session, profile_id: str) -> PersonalSuccessChain:
    chain = db.scalar(
        select(PersonalSuccessChain)
        .where(
            PersonalSuccessChain.profile_id == profile_id,
            PersonalSuccessChain.chain_key == "first_foundations",
        )
        .with_for_update()
    )
    if chain is None:
        chain = PersonalSuccessChain(profile_id=profile_id)
        db.add(chain)
        db.flush()
    completed = [
        event_type
        for event_type in SUCCESS_EVENTS
        if db.scalar(
            select(func.count())
            .select_from(EngagementEvent)
            .where(
                EngagementEvent.profile_id == profile_id,
                EngagementEvent.event_type == event_type,
            )
        )
    ]
    chain.completed_event_types_json = completed
    chain.completed_steps = len(completed)
    if len(completed) == len(SUCCESS_EVENTS) and chain.status != "completed":
        chain.status = "completed"
        chain.completed_at = datetime.now(UTC)
    db.flush()
    return chain


def project_engagement_learning(db: Session, event: EngagementEvent) -> None:
    learning = EVENT_LEARNING.get(event.event_type)
    if learning is not None:
        area, decision, points = learning
        award_mastery(
            db,
            profile_id=event.profile_id,
            area_key=area,
            decision_key=decision,
            source_type="engagement_event",
            source_id=event.id,
            base_points=points,
        )
        report_keys = OUTCOME_REPORT_KEYS[event.event_type]
        report = db.scalar(
            select(OutcomeReport).where(
                OutcomeReport.profile_id == event.profile_id,
                OutcomeReport.source_type == event.source_type,
                OutcomeReport.source_id == event.source_id,
            )
        )
        if report is None:
            db.add(
                OutcomeReport(
                    profile_id=event.profile_id,
                    source_type=event.source_type,
                    source_id=event.source_id,
                    title_key=report_keys[0],
                    controllable_factors_json=report_keys[1],
                    external_factors_json=report_keys[2],
                    worked_well_json=report_keys[3],
                    alternatives_json=report_keys[4],
                    knowledge_unlocked_json=[KNOWLEDGE_KEYS[area]],
                )
            )
    _sync_success_chain(db, event.profile_id)


def list_outcome_reports(db: Session, profile: PlayerProfile) -> list[OutcomeReport]:
    return list(
        db.scalars(
            select(OutcomeReport)
            .where(OutcomeReport.profile_id == profile.id)
            .order_by(OutcomeReport.created_at.desc())
            .limit(25)
        )
    )


def adaptive_help(db: Session, profile: PlayerProfile) -> list[AdaptiveHelpOffer]:
    setting = db.scalar(select(EngagementSetting).where(EngagementSetting.profile_id == profile.id))
    if setting is not None and not setting.adaptive_help_enabled:
        return []
    progress = ensure_mastery_progress(db, profile)
    contexts: list[tuple[str, str, str, str]] = []
    if profile.tutorial_step < 7:
        contexts.append(
            (
                "tutorial_foundations",
                "engagementHelpTutorialExplanation",
                "engagementHelpTutorialSuggestion",
                "/tutorial",
            )
        )
    if not any(item.points for item in progress):
        contexts.append(
            (
                "first_decision",
                "engagementHelpFirstDecisionExplanation",
                "engagementHelpFirstDecisionSuggestion",
                "/engagement",
            )
        )
    if sum(item.points for item in progress) >= 50 and not any(
        item.area_key == "market_analysis" and item.points for item in progress
    ):
        contexts.append(
            (
                "market_analysis_practice",
                "engagementHelpMarketExplanation",
                "engagementHelpMarketSuggestion",
                "/exchange",
            )
        )
    offers: list[AdaptiveHelpOffer] = []
    for context, explanation, suggestion, path in contexts[:3]:
        offer = db.scalar(
            select(AdaptiveHelpOffer).where(
                AdaptiveHelpOffer.profile_id == profile.id,
                AdaptiveHelpOffer.context_key == context,
            )
        )
        if offer is None:
            offer = AdaptiveHelpOffer(
                profile_id=profile.id,
                context_key=context,
                explanation_key=explanation,
                suggestion_key=suggestion,
                target_path=path,
            )
            db.add(offer)
            db.flush()
        if offer.status == "offered":
            offers.append(offer)
    return offers


def respond_to_help(
    db: Session,
    profile: PlayerProfile,
    offer_id: str,
    status: Literal["accepted", "dismissed", "completed"],
) -> AdaptiveHelpOffer:
    offer = db.scalar(
        select(AdaptiveHelpOffer)
        .where(
            AdaptiveHelpOffer.id == offer_id,
            AdaptiveHelpOffer.profile_id == profile.id,
        )
        .with_for_update()
    )
    if offer is None:
        raise DomainError(404, "engagement.help_not_found", "Help offer not found")
    offer.status = status
    offer.responded_at = datetime.now(UTC)
    db.flush()
    return offer


def success_chain(db: Session, profile: PlayerProfile) -> PersonalSuccessChain:
    return _sync_success_chain(db, profile.id)


def propose_mentorship(
    db: Session,
    mentor: PlayerProfile,
    *,
    mentee_profile_id: str,
    idempotency_key: str,
) -> Mentorship:
    existing = db.scalar(
        select(Mentorship).where(
            Mentorship.mentor_profile_id == mentor.id,
            Mentorship.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    mentee = db.get(PlayerProfile, mentee_profile_id)
    if mentee is None or mentee.world_id != mentor.world_id:
        raise DomainError(404, "mentoring.mentee_not_found", "Mentee not found in this world")
    if mentee.id == mentor.id:
        raise DomainError(422, "mentoring.self_forbidden", "Players cannot mentor themselves")
    mastery_points = int(
        db.scalar(
            select(func.coalesce(func.sum(MasteryProgress.points), 0)).where(
                MasteryProgress.profile_id == mentor.id
            )
        )
        or 0
    )
    if mastery_points < 20:
        raise DomainError(
            409,
            "mentoring.experience_required",
            "Mentors need verified mastery before offering guidance",
        )
    conflict = db.scalar(
        select(Mentorship).where(
            Mentorship.mentee_profile_id == mentee.id,
            Mentorship.status.in_(("proposed", "active", "paused")),
        )
    )
    if conflict is not None:
        raise DomainError(409, "mentoring.already_supported", "Mentee already has active support")
    mentorship = Mentorship(
        world_id=mentor.world_id,
        mentor_profile_id=mentor.id,
        mentee_profile_id=mentee.id,
        idempotency_key=idempotency_key,
    )
    db.add(mentorship)
    db.flush()
    return mentorship


def _mentorship_for_participant(
    db: Session, profile: PlayerProfile, mentorship_id: str, *, lock: bool = False
) -> Mentorship:
    query = select(Mentorship).where(
        Mentorship.id == mentorship_id,
        (Mentorship.mentor_profile_id == profile.id) | (Mentorship.mentee_profile_id == profile.id),
    )
    if lock:
        query = query.with_for_update()
    mentorship = db.scalar(query)
    if mentorship is None:
        raise DomainError(404, "mentoring.not_found", "Mentorship not found")
    return mentorship


def accept_mentorship(
    db: Session, mentee: PlayerProfile, mentorship_id: str, *, accept: bool
) -> Mentorship:
    mentorship = _mentorship_for_participant(db, mentee, mentorship_id, lock=True)
    if mentorship.mentee_profile_id != mentee.id or mentorship.status != "proposed":
        raise DomainError(409, "mentoring.invalid_transition", "Mentorship cannot be answered")
    if accept:
        mentorship.mentee_opted_in = True
        mentorship.status = "active"
        mentorship.accepted_at = datetime.now(UTC)
    else:
        mentorship.status = "declined"
    db.flush()
    return mentorship


def _add_milestone(
    db: Session,
    mentorship: Mentorship,
    milestone_key: str,
    *,
    event_id: str | None,
    evidence: dict[str, object],
) -> None:
    exists = db.scalar(
        select(MentoringMilestone).where(
            MentoringMilestone.mentorship_id == mentorship.id,
            MentoringMilestone.milestone_key == milestone_key,
        )
    )
    if exists is None:
        db.add(
            MentoringMilestone(
                mentorship_id=mentorship.id,
                milestone_key=milestone_key,
                verified_event_id=event_id,
                evidence_json=evidence,
            )
        )


def refresh_mentorship(
    db: Session,
    participant: PlayerProfile,
    mentorship_id: str,
    *,
    positive_feedback: bool | None = None,
) -> Mentorship:
    mentorship = _mentorship_for_participant(db, participant, mentorship_id, lock=True)
    if mentorship.status not in ("active", "paused", "completed"):
        raise DomainError(409, "mentoring.not_active", "Mentorship is not active")
    if positive_feedback is not None:
        if participant.id != mentorship.mentee_profile_id:
            raise DomainError(403, "mentoring.feedback_owner", "Only the mentee can give feedback")
        mentorship.feedback_positive = positive_feedback
    events = list(
        db.scalars(
            select(EngagementEvent)
            .where(EngagementEvent.profile_id == mentorship.mentee_profile_id)
            .order_by(EngagementEvent.occurred_at)
        )
    )
    distinct_types = list(dict.fromkeys(item.event_type for item in events))
    if len(distinct_types) >= 2:
        _add_milestone(
            db,
            mentorship,
            "system_understood",
            event_id=events[1].id,
            evidence={"distinct_systems": 2},
        )
    if len(distinct_types) >= 3:
        _add_milestone(
            db,
            mentorship,
            "independent_decision",
            event_id=events[2].id,
            evidence={"distinct_decisions": 3},
        )
    if mentorship.feedback_positive:
        _add_milestone(
            db,
            mentorship,
            "positive_feedback",
            event_id=None,
            evidence={"voluntary": True},
        )
    db.flush()
    milestone_count = int(
        db.scalar(
            select(func.count())
            .select_from(MentoringMilestone)
            .where(MentoringMilestone.mentorship_id == mentorship.id)
        )
        or 0
    )
    if milestone_count == 3 and mentorship.status != "completed":
        mentorship.status = "completed"
        mentorship.completed_at = datetime.now(UTC)
        award_mastery(
            db,
            profile_id=mentorship.mentor_profile_id,
            area_key="people_leadership",
            decision_key="verified_mentoring",
            source_type="mentorship",
            source_id=mentorship.id,
            base_points=30,
        )
        mentor = db.get(PlayerProfile, mentorship.mentor_profile_id)
        if mentor is not None:
            create_notification(
                db,
                mentor.user_id,
                "mentoring.completed",
                "Mentoring milestone complete",
                "The mentee demonstrated understanding, independent decisions and positive feedback.",
                {"mentorship_id": mentorship.id},
                category="social",
            )
    db.flush()
    return mentorship


def list_mentorships(db: Session, profile: PlayerProfile) -> list[Mentorship]:
    return list(
        db.scalars(
            select(Mentorship)
            .where(
                (Mentorship.mentor_profile_id == profile.id)
                | (Mentorship.mentee_profile_id == profile.id)
            )
            .order_by(Mentorship.created_at.desc())
        )
    )


def _active_membership(
    db: Session, profile_id: str, organization_id: str, *, lock: bool = False
) -> OrganizationMembership:
    query = select(OrganizationMembership).where(
        OrganizationMembership.profile_id == profile_id,
        OrganizationMembership.organization_id == organization_id,
        OrganizationMembership.status == "active",
    )
    if lock:
        query = query.with_for_update()
    membership = db.scalar(query)
    if membership is None:
        raise DomainError(403, "cartel.membership_required", "Active cartel membership required")
    return membership


def record_cartel_chronicle(
    db: Session,
    *,
    organization_id: str,
    actor_profile_id: str | None,
    entry_type: str,
    source_type: str,
    source_id: str,
    title_key: str,
    body_key: str,
    metadata: dict[str, object] | None = None,
) -> CartelChronicleEntry:
    existing = db.scalar(
        select(CartelChronicleEntry).where(
            CartelChronicleEntry.organization_id == organization_id,
            CartelChronicleEntry.source_type == source_type,
            CartelChronicleEntry.source_id == source_id,
            CartelChronicleEntry.entry_type == entry_type,
        )
    )
    if existing is not None:
        return existing
    entry = CartelChronicleEntry(
        organization_id=organization_id,
        actor_profile_id=actor_profile_id,
        entry_type=entry_type,
        source_type=source_type,
        source_id=source_id,
        title_key=title_key,
        body_key=body_key,
        metadata_json=metadata or {},
    )
    db.add(entry)
    db.flush()
    return entry


def create_delegation(
    db: Session,
    profile: PlayerProfile,
    *,
    organization_id: str,
    delegate_profile_id: str,
    role_key: str,
    duration_days: int,
    idempotency_key: str,
) -> CartelDelegation:
    if role_key not in DELEGATABLE_ROLES:
        raise DomainError(422, "cartel.invalid_delegation_role", "Unsupported delegation role")
    grantor = _active_membership(db, profile.id, organization_id, lock=True)
    existing = db.scalar(
        select(CartelDelegation).where(
            CartelDelegation.grantor_membership_id == grantor.id,
            CartelDelegation.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    delegate = _active_membership(db, delegate_profile_id, organization_id, lock=True)
    if delegate.id == grantor.id:
        raise DomainError(422, "cartel.self_delegation", "Delegation requires another member")
    grantor_permissions = ROLE_PERMISSIONS.get(grantor.role, set())
    if "*" not in grantor_permissions and not set(DELEGATABLE_ROLES[role_key]).issubset(
        grantor_permissions
    ):
        raise DomainError(403, "cartel.permission_denied", "Role cannot delegate these tools")
    now = datetime.now(UTC)
    delegation = CartelDelegation(
        organization_id=organization_id,
        grantor_membership_id=grantor.id,
        delegate_membership_id=delegate.id,
        role_key=role_key,
        permissions_json=DELEGATABLE_ROLES[role_key],
        idempotency_key=idempotency_key,
        starts_at=now,
        expires_at=now + timedelta(days=duration_days),
    )
    db.add(delegation)
    db.flush()
    record_cartel_chronicle(
        db,
        organization_id=organization_id,
        actor_profile_id=profile.id,
        entry_type="delegation_created",
        source_type="cartel_delegation",
        source_id=delegation.id,
        title_key="engagementChronicleDelegationTitle",
        body_key="engagementChronicleDelegationBody",
        metadata={"role_key": role_key},
    )
    return delegation


def list_delegations(
    db: Session, profile: PlayerProfile, organization_id: str
) -> list[CartelDelegation]:
    _active_membership(db, profile.id, organization_id)
    expire_delegations(db)
    return list(
        db.scalars(
            select(CartelDelegation)
            .where(CartelDelegation.organization_id == organization_id)
            .order_by(CartelDelegation.starts_at.desc())
        )
    )


def pause_membership(
    db: Session,
    profile: PlayerProfile,
    *,
    organization_id: str,
    duration_days: int,
    private_reason: str | None,
    idempotency_key: str,
) -> CartelMembershipPause:
    membership = _active_membership(db, profile.id, organization_id, lock=True)
    existing = db.scalar(
        select(CartelMembershipPause).where(
            CartelMembershipPause.membership_id == membership.id,
            CartelMembershipPause.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    active = db.scalar(
        select(CartelMembershipPause).where(
            CartelMembershipPause.membership_id == membership.id,
            CartelMembershipPause.status == "active",
        )
    )
    if active is not None:
        raise DomainError(409, "cartel.pause_active", "Membership is already paused")
    now = datetime.now(UTC)
    pause = CartelMembershipPause(
        membership_id=membership.id,
        private_reason=private_reason,
        idempotency_key=idempotency_key,
        starts_at=now,
        planned_until=now + timedelta(days=duration_days),
    )
    db.add(pause)
    db.flush()
    return pause


def current_membership_pause(
    db: Session, profile: PlayerProfile, organization_id: str
) -> CartelMembershipPause | None:
    membership = _active_membership(db, profile.id, organization_id)
    expire_pauses(db)
    return db.scalar(
        select(CartelMembershipPause).where(
            CartelMembershipPause.membership_id == membership.id,
            CartelMembershipPause.status == "active",
        )
    )


def resume_membership(
    db: Session, profile: PlayerProfile, *, organization_id: str
) -> CartelMembershipPause:
    membership = _active_membership(db, profile.id, organization_id, lock=True)
    pause = db.scalar(
        select(CartelMembershipPause)
        .where(
            CartelMembershipPause.membership_id == membership.id,
            CartelMembershipPause.status == "active",
        )
        .with_for_update()
    )
    if pause is None:
        raise DomainError(404, "cartel.pause_not_found", "No active membership pause")
    pause.status = "completed"
    pause.resumed_at = datetime.now(UTC)
    db.flush()
    return pause


def list_cartel_chronicle(
    db: Session, profile: PlayerProfile, organization_id: str
) -> list[CartelChronicleEntry]:
    _active_membership(db, profile.id, organization_id)
    return list(
        db.scalars(
            select(CartelChronicleEntry)
            .where(CartelChronicleEntry.organization_id == organization_id)
            .order_by(CartelChronicleEntry.created_at.desc())
            .limit(100)
        )
    )


def current_doctrine(db: Session, profile: PlayerProfile) -> PlayerDoctrine | None:
    return db.scalar(select(PlayerDoctrine).where(PlayerDoctrine.profile_id == profile.id))


def mastery_total(db: Session, profile_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(MasteryProgress.points), 0)).where(
                MasteryProgress.profile_id == profile_id
            )
        )
        or 0
    )


def expire_delegations(db: Session, *, now: datetime | None = None) -> int:
    timestamp = as_utc(now or datetime.now(UTC))
    delegations = db.scalars(
        select(CartelDelegation)
        .where(
            CartelDelegation.status == "active",
            CartelDelegation.expires_at <= timestamp,
        )
        .with_for_update()
    ).all()
    for delegation in delegations:
        delegation.status = "expired"
    db.flush()
    return len(delegations)


def expire_pauses(db: Session, *, now: datetime | None = None) -> int:
    timestamp = as_utc(now or datetime.now(UTC))
    pauses = db.scalars(
        select(CartelMembershipPause)
        .where(
            CartelMembershipPause.status == "active",
            CartelMembershipPause.planned_until <= timestamp,
        )
        .with_for_update()
    ).all()
    for pause in pauses:
        pause.status = "completed"
        pause.resumed_at = timestamp
    db.flush()
    return len(pauses)
