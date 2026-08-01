from __future__ import annotations

from datetime import UTC, datetime
from threading import RLock
from typing import Any, Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.domain import get_idempotent, remember_idempotent
from shadowgrid.errors import DomainError
from shadowgrid.models import (
    CollectionItem,
    Company,
    CompanyEconomyReport,
    DossierClue,
    EngagementEvent,
    EngagementSetting,
    EventDossier,
    LegacyRecord,
    MasteryProgress,
    Mentorship,
    NarrativeActor,
    NarrativeChronicleEntry,
    OrganizationMembership,
    PlayerActorRelationship,
    PlayerCollection,
    PlayerDoctrine,
    PlayerDossierProgress,
    PlayerIdentity,
    PlayerProfile,
    PlayerRankingBest,
    PlayerSeasonGoal,
    PlayerSession,
    ResourceBalance,
    ReturnContract,
    Season,
    User,
    WorldEventInstance,
    as_utc,
)

ACTORS = (
    (
        "mara_voss",
        "entrepreneur",
        "engagementActorMaraVoss",
        "engagementActorMaraVossDescription",
    ),
    (
        "elias_kern",
        "journalist",
        "engagementActorEliasKern",
        "engagementActorEliasKernDescription",
    ),
    (
        "nia_calder",
        "analyst",
        "engagementActorNiaCalder",
        "engagementActorNiaCalderDescription",
    ),
    (
        "jun_arendt",
        "decision_maker",
        "engagementActorJunArendt",
        "engagementActorJunArendtDescription",
    ),
)

ACTOR_BY_EVENT = {
    "company.founded": "mara_voss",
    "company.first_profit": "mara_voss",
    "specialist.assigned": "mara_voss",
    "exchange.ipo_completed": "nia_calder",
    "cartel.project_contributed": "jun_arendt",
    "intelligence.report_acquired": "nia_calder",
    "world_event.responded": "elias_kern",
    "season.closed": "jun_arendt",
}

CHRONICLE_KEYS = {
    "company.founded": (
        "company",
        "foundation",
        "engagementChronicleCompanyFoundedTitle",
        "engagementChronicleCompanyFoundedBody",
    ),
    "company.first_profit": (
        "company",
        "first_profit",
        "engagementChronicleFirstProfitTitle",
        "engagementChronicleFirstProfitBody",
    ),
    "specialist.assigned": (
        "company",
        "specialist_joined",
        "engagementChronicleSpecialistTitle",
        "engagementChronicleSpecialistBody",
    ),
    "exchange.ipo_completed": (
        "company",
        "ipo",
        "engagementChronicleIpoTitle",
        "engagementChronicleIpoBody",
    ),
    "world_event.responded": (
        "world",
        "world_response",
        "engagementChronicleWorldResponseTitle",
        "engagementChronicleWorldResponseBody",
    ),
    "season.closed": (
        "world",
        "season_finale",
        "engagementChronicleSeasonFinaleTitle",
        "engagementChronicleSeasonFinaleBody",
    ),
}

COLLECTION_CATALOG = (
    (
        "company_founder_title",
        "title",
        "engagementCollectionFounderTitle",
        "engagementCollectionFounderDescription",
        "common",
        0,
    ),
    (
        "team_builder_emblem",
        "emblem",
        "engagementCollectionTeamBuilderTitle",
        "engagementCollectionTeamBuilderDescription",
        "common",
        0,
    ),
    (
        "ipo_pioneer_emblem",
        "emblem",
        "engagementCollectionIpoTitle",
        "engagementCollectionIpoDescription",
        "rare",
        0,
    ),
    (
        "world_investigator_chronicle",
        "chronicle",
        "engagementCollectionInvestigatorTitle",
        "engagementCollectionInvestigatorDescription",
        "uncommon",
        0,
    ),
    (
        "season_archivist_title",
        "title",
        "engagementCollectionSeasonTitle",
        "engagementCollectionSeasonDescription",
        "rare",
        0,
    ),
    (
        "season_memorial_hq",
        "hq_cosmetic",
        "engagementCollectionSeasonHqTitle",
        "engagementCollectionSeasonHqDescription",
        "rare",
        0,
    ),
    (
        "rare_city_signal",
        "discovery",
        "engagementCollectionCitySignalTitle",
        "engagementCollectionCitySignalDescription",
        "rare",
        5,
    ),
)

COLLECTION_BY_EVENT = {
    "company.founded": ("company_founder_title",),
    "specialist.assigned": ("team_builder_emblem",),
    "exchange.ipo_completed": ("ipo_pioneer_emblem",),
    "world_event.responded": ("world_investigator_chronicle",),
    "season.closed": ("season_archivist_title", "season_memorial_hq"),
}

SEASON_GOALS = (
    (
        "economic_resilience",
        "engagementSeasonGoalEconomicTitle",
        "engagementSeasonGoalEconomicDescription",
        ("company.first_profit",),
        3,
    ),
    (
        "social_impact",
        "engagementSeasonGoalSocialTitle",
        "engagementSeasonGoalSocialDescription",
        ("cartel.project_contributed",),
        3,
    ),
    (
        "world_exploration",
        "engagementSeasonGoalWorldTitle",
        "engagementSeasonGoalWorldDescription",
        ("world_event.responded",),
        3,
    ),
    (
        "intelligence_depth",
        "engagementSeasonGoalIntelligenceTitle",
        "engagementSeasonGoalIntelligenceDescription",
        ("intelligence.report_acquired",),
        4,
    ),
    (
        "strategic_variety",
        "engagementSeasonGoalVarietyTitle",
        "engagementSeasonGoalVarietyDescription",
        tuple(ACTOR_BY_EVENT),
        5,
    ),
)

RETURN_CONTRACTS = (
    (
        "stabilize_company",
        "engagementReturnContractCompanyTitle",
        "engagementReturnContractCompanyDescription",
        "company.first_profit",
    ),
    (
        "review_world",
        "engagementReturnContractWorldTitle",
        "engagementReturnContractWorldDescription",
        "world_event.responded",
    ),
    (
        "reconnect_social",
        "engagementReturnContractSocialTitle",
        "engagementReturnContractSocialDescription",
        "cartel.project_contributed",
    ),
)

RANKING_CATEGORIES = (
    "company_value",
    "sustainable_profit",
    "innovation",
    "contract_reliability",
    "portfolio_return",
    "district_development",
    "cartel_influence",
    "intelligence_success",
    "diplomatic_stability",
    "comeback_performance",
    "mentoring",
    "season_goals",
)
_RANKING_LOCK = RLock()


def ensure_actor_catalog(db: Session, world_id: str) -> list[NarrativeActor]:
    existing = {
        item.actor_key: item
        for item in db.scalars(select(NarrativeActor).where(NarrativeActor.world_id == world_id))
    }
    for actor_key, actor_type, name_key, description_key in ACTORS:
        if actor_key not in existing:
            actor = NarrativeActor(
                world_id=world_id,
                actor_key=actor_key,
                actor_type=actor_type,
                name_key=name_key,
                description_key=description_key,
            )
            db.add(actor)
            existing[actor_key] = actor
    db.flush()
    return [existing[item[0]] for item in ACTORS]


def ensure_collection_catalog(db: Session) -> list[CollectionItem]:
    existing = {item.item_key: item for item in db.scalars(select(CollectionItem))}
    for (
        item_key,
        item_type,
        title_key,
        description_key,
        rarity,
        guarantee_after,
    ) in COLLECTION_CATALOG:
        if item_key not in existing:
            item = CollectionItem(
                item_key=item_key,
                item_type=item_type,
                title_key=title_key,
                description_key=description_key,
                rarity=rarity,
                guarantee_after=guarantee_after,
            )
            db.add(item)
            existing[item_key] = item
    db.flush()
    return [existing[item[0]] for item in COLLECTION_CATALOG]


def unlock_collection_item(
    db: Session,
    *,
    profile_id: str,
    item_key: str,
    source_type: str,
    source_id: str,
) -> PlayerCollection:
    items = {item.item_key: item for item in ensure_collection_catalog(db)}
    item = items[item_key]
    collection = db.scalar(
        select(PlayerCollection)
        .where(
            PlayerCollection.profile_id == profile_id,
            PlayerCollection.item_id == item.id,
        )
        .with_for_update()
    )
    if collection is None:
        collection = PlayerCollection(
            profile_id=profile_id,
            item_id=item.id,
            source_type=source_type,
            source_id=source_id,
        )
        db.add(collection)
    elif collection.source_id != source_id:
        collection.duplicate_points += 10
    db.flush()
    identity = db.scalar(select(PlayerIdentity).where(PlayerIdentity.profile_id == profile_id))
    if identity is None:
        identity = PlayerIdentity(profile_id=profile_id)
        db.add(identity)
        db.flush()
    if item.item_type == "title" and identity.active_title_item_id is None:
        identity.active_title_item_id = item.id
    elif item.item_type == "emblem" and identity.active_emblem_item_id is None:
        identity.active_emblem_item_id = item.id
    elif item.item_type == "hq_cosmetic" and identity.active_hq_cosmetic_item_id is None:
        identity.active_hq_cosmetic_item_id = item.id
    return collection


def _company_scope_id(event: EngagementEvent) -> str | None:
    company_id = event.payload_json.get("company_id")
    if isinstance(company_id, str):
        return company_id
    if event.event_type in ("company.founded", "company.first_profit"):
        return event.source_id
    return None


def _project_actor_relationship(db: Session, event: EngagementEvent) -> None:
    actor_key = ACTOR_BY_EVENT.get(event.event_type)
    if actor_key is None:
        return
    actors = {item.actor_key: item for item in ensure_actor_catalog(db, event.world_id)}
    actor = actors[actor_key]
    relationship = db.scalar(
        select(PlayerActorRelationship)
        .where(
            PlayerActorRelationship.profile_id == event.profile_id,
            PlayerActorRelationship.actor_id == actor.id,
        )
        .with_for_update()
    )
    if relationship is None:
        relationship = PlayerActorRelationship(profile_id=event.profile_id, actor_id=actor.id)
        db.add(relationship)
        db.flush()
    relationship.trust = min(100, relationship.trust + 2)
    relationship.reputation = min(100, relationship.reputation + 1)
    relationship.information_access = min(
        100,
        relationship.information_access
        + (
            2
            if event.event_type in ("intelligence.report_acquired", "world_event.responded")
            else 1
        ),
    )
    relationship.interaction_count += 1
    relationship.history_keys_json = [
        *relationship.history_keys_json[-19:],
        f"engagementActorHistory{event.event_type.replace('.', '_')}",
    ]


def _project_chronicle(db: Session, event: EngagementEvent) -> None:
    definition = CHRONICLE_KEYS.get(event.event_type)
    if definition is None:
        return
    scope_type, entry_type, title_key, body_key = definition
    scope_id = event.world_id if scope_type == "world" else _company_scope_id(event)
    if scope_id is None:
        return
    source_type = event.source_type
    source_id = event.source_id or event.id
    exists = db.scalar(
        select(NarrativeChronicleEntry).where(
            NarrativeChronicleEntry.scope_type == scope_type,
            NarrativeChronicleEntry.scope_id == scope_id,
            NarrativeChronicleEntry.source_type == source_type,
            NarrativeChronicleEntry.source_id == source_id,
            NarrativeChronicleEntry.entry_type == entry_type,
        )
    )
    if exists is None:
        actor_key = ACTOR_BY_EVENT.get(event.event_type)
        db.add(
            NarrativeChronicleEntry(
                world_id=event.world_id,
                profile_id=event.profile_id,
                event_id=event.id,
                scope_type=scope_type,
                scope_id=scope_id,
                source_type=source_type,
                source_id=source_id,
                entry_type=entry_type,
                title_key=title_key,
                body_key=body_key,
                cause_keys_json=["engagementChronicleCauseDecision"],
                actor_keys_json=[actor_key] if actor_key else [],
                impact_keys_json=["engagementChronicleImpactPersistent"],
                open_question_keys_json=["engagementChronicleOpenQuestion"],
                metadata_json=event.payload_json,
                created_at=event.occurred_at,
            )
        )


def ensure_season_goals(db: Session, profile: PlayerProfile) -> list[PlayerSeasonGoal]:
    season = db.scalar(
        select(Season)
        .where(Season.world_id == profile.world_id, Season.status.in_(("active", "scoring")))
        .order_by(Season.season_number.desc())
        .limit(1)
    )
    if season is None:
        return []
    existing = {
        item.goal_key: item
        for item in db.scalars(
            select(PlayerSeasonGoal).where(
                PlayerSeasonGoal.profile_id == profile.id,
                PlayerSeasonGoal.season_id == season.id,
            )
        )
    }
    for goal_key, title_key, description_key, event_types, target in SEASON_GOALS:
        if goal_key not in existing:
            goal = PlayerSeasonGoal(
                profile_id=profile.id,
                season_id=season.id,
                goal_key=goal_key,
                title_key=title_key,
                description_key=description_key,
                event_types_json=list(event_types),
                target_value=target,
            )
            db.add(goal)
            existing[goal_key] = goal
    db.flush()
    return [existing[item[0]] for item in SEASON_GOALS]


def select_season_goal(db: Session, profile: PlayerProfile, goal_id: str) -> PlayerSeasonGoal:
    goal = db.scalar(
        select(PlayerSeasonGoal)
        .where(PlayerSeasonGoal.id == goal_id, PlayerSeasonGoal.profile_id == profile.id)
        .with_for_update()
    )
    if goal is None:
        raise DomainError(404, "engagement.season_goal_not_found", "Season goal not found")
    if goal.status != "offered":
        return goal
    selected_count = int(
        db.scalar(
            select(func.count())
            .select_from(PlayerSeasonGoal)
            .where(
                PlayerSeasonGoal.profile_id == profile.id,
                PlayerSeasonGoal.season_id == goal.season_id,
                PlayerSeasonGoal.status.in_(("active", "completed")),
            )
        )
        or 0
    )
    if selected_count >= 3:
        raise DomainError(409, "engagement.season_goal_limit", "Choose at most three season goals")
    goal.status = "active"
    goal.selected_at = datetime.now(UTC)
    db.flush()
    return goal


def _project_season_goals(db: Session, event: EngagementEvent) -> None:
    goals = db.scalars(
        select(PlayerSeasonGoal)
        .where(
            PlayerSeasonGoal.profile_id == event.profile_id,
            PlayerSeasonGoal.status == "active",
        )
        .with_for_update()
    ).all()
    for goal in goals:
        if event.event_type not in goal.event_types_json:
            continue
        if goal.goal_key == "strategic_variety":
            event_count = int(
                db.scalar(
                    select(func.count(func.distinct(EngagementEvent.event_type))).where(
                        EngagementEvent.profile_id == event.profile_id,
                        EngagementEvent.occurred_at >= goal.created_at,
                    )
                )
                or 0
            )
            goal.progress_value = min(goal.target_value, event_count)
        else:
            goal.progress_value = min(goal.target_value, goal.progress_value + 1)
        if goal.progress_value == goal.target_value:
            goal.status = "completed"
            goal.completed_at = event.occurred_at


def _project_return_contracts(db: Session, event: EngagementEvent) -> None:
    contracts = db.scalars(
        select(ReturnContract)
        .where(
            ReturnContract.profile_id == event.profile_id,
            ReturnContract.status == "active",
            ReturnContract.event_type == event.event_type,
        )
        .with_for_update()
    ).all()
    for contract in contracts:
        contract.progress_value = contract.target_value
        contract.status = "completed"
        contract.completed_at = event.occurred_at


def project_legacy_event(db: Session, event: EngagementEvent) -> None:
    _project_actor_relationship(db, event)
    _project_chronicle(db, event)
    for item_key in COLLECTION_BY_EVENT.get(event.event_type, ()):
        unlock_collection_item(
            db,
            profile_id=event.profile_id,
            item_key=item_key,
            source_type=event.source_type,
            source_id=event.source_id,
        )
    if event.event_type == "season.closed":
        exists = db.scalar(
            select(LegacyRecord).where(
                LegacyRecord.profile_id == event.profile_id,
                LegacyRecord.record_key == "season_completed",
                LegacyRecord.source_id == event.source_id,
            )
        )
        if exists is None:
            db.add(
                LegacyRecord(
                    profile_id=event.profile_id,
                    record_key="season_completed",
                    source_type=event.source_type,
                    source_id=event.source_id,
                    title_key="engagementLegacySeasonCompleted",
                    metadata_json=event.payload_json,
                )
            )
    _project_season_goals(db, event)
    _project_return_contracts(db, event)
    db.flush()


def list_chronicle(
    db: Session,
    profile: PlayerProfile,
    *,
    scope_type: Literal["company", "world", "profile"],
    scope_id: str,
) -> list[NarrativeChronicleEntry]:
    if scope_type == "company":
        company = db.get(Company, scope_id)
        if company is None or company.founder_profile_id != profile.id:
            raise DomainError(404, "company.not_found", "Owned company not found")
    elif scope_type == "world" and scope_id != profile.world_id:
        raise DomainError(404, "world.not_found", "World not found")
    elif scope_type == "profile" and scope_id != profile.id:
        raise DomainError(403, "engagement.chronicle_private", "Profile chronicle is private")
    return list(
        db.scalars(
            select(NarrativeChronicleEntry)
            .where(
                NarrativeChronicleEntry.scope_type == scope_type,
                NarrativeChronicleEntry.scope_id == scope_id,
            )
            .order_by(NarrativeChronicleEntry.created_at.desc())
        )
    )


def list_actor_relationships(
    db: Session, profile: PlayerProfile
) -> list[tuple[NarrativeActor, PlayerActorRelationship | None]]:
    actors = ensure_actor_catalog(db, profile.world_id)
    relationships = {
        item.actor_id: item
        for item in db.scalars(
            select(PlayerActorRelationship).where(PlayerActorRelationship.profile_id == profile.id)
        )
    }
    return [(actor, relationships.get(actor.id)) for actor in actors]


def ensure_dossiers(db: Session, profile: PlayerProfile) -> list[EventDossier]:
    instances = db.scalars(
        select(WorldEventInstance)
        .where(WorldEventInstance.world_id == profile.world_id)
        .order_by(WorldEventInstance.starts_at.desc())
    ).all()
    dossiers: list[EventDossier] = []
    for instance in instances:
        dossier = db.scalar(
            select(EventDossier).where(EventDossier.world_event_instance_id == instance.id)
        )
        if dossier is None:
            dossier = EventDossier(
                world_id=profile.world_id,
                world_event_instance_id=instance.id,
                title_key="engagementDossierTitle",
                cause_key="engagementDossierCause",
                local_impact_key="engagementDossierLocalImpact",
                open_question_key="engagementDossierOpenQuestion",
                archived=instance.status in ("ended", "cancelled"),
            )
            db.add(dossier)
            db.flush()
            for index, (clue_key, rare) in enumerate(
                (
                    ("engagementDossierClueCause", False),
                    ("engagementDossierClueActor", False),
                    ("engagementDossierClueRare", True),
                ),
                start=1,
            ):
                db.add(
                    DossierClue(
                        dossier_id=dossier.id,
                        clue_key=clue_key,
                        order_index=index,
                        rare=rare,
                    )
                )
        dossiers.append(dossier)
    db.flush()
    return dossiers


def dossier_progress(
    db: Session, profile: PlayerProfile, dossier: EventDossier
) -> PlayerDossierProgress:
    progress = db.scalar(
        select(PlayerDossierProgress).where(
            PlayerDossierProgress.profile_id == profile.id,
            PlayerDossierProgress.dossier_id == dossier.id,
        )
    )
    if progress is None:
        progress = PlayerDossierProgress(profile_id=profile.id, dossier_id=dossier.id)
        db.add(progress)
        db.flush()
    return progress


def investigate_dossier(
    db: Session,
    user: User,
    profile: PlayerProfile,
    dossier_id: str,
    *,
    idempotency_key: str,
) -> PlayerDossierProgress:
    previous = get_idempotent(db, user.id, idempotency_key, "engagement.dossier.investigate")
    if previous is not None:
        progress = db.get(PlayerDossierProgress, previous.resource_id)
        if progress is not None and progress.profile_id == profile.id:
            return progress
    dossier = db.get(EventDossier, dossier_id)
    if dossier is None or dossier.world_id != profile.world_id:
        raise DomainError(404, "engagement.dossier_not_found", "Event dossier not found")
    progress = db.scalar(
        select(PlayerDossierProgress)
        .where(
            PlayerDossierProgress.profile_id == profile.id,
            PlayerDossierProgress.dossier_id == dossier.id,
        )
        .with_for_update()
    )
    if progress is None:
        progress = PlayerDossierProgress(profile_id=profile.id, dossier_id=dossier.id)
        db.add(progress)
        db.flush()
    if progress.completed_at is not None:
        remember_idempotent(
            db,
            user.id,
            idempotency_key,
            "engagement.dossier.investigate",
            progress.id,
            {"progress_id": progress.id},
        )
        return progress
    progress.investigation_count += 1
    clues = db.scalars(
        select(DossierClue)
        .where(DossierClue.dossier_id == dossier.id)
        .order_by(DossierClue.order_index)
    ).all()
    discovered = set(progress.discovered_clue_ids_json)
    candidate = next((item for item in clues if not item.rare and item.id not in discovered), None)
    if candidate is None and progress.investigation_count >= 5:
        candidate = next((item for item in clues if item.rare and item.id not in discovered), None)
    if candidate is not None:
        discovered.add(candidate.id)
        progress.discovered_clue_ids_json = sorted(discovered)
    if len(discovered) == dossier.total_clues:
        progress.completed_at = progress.completed_at or datetime.now(UTC)
        unlock_collection_item(
            db,
            profile_id=profile.id,
            item_key="rare_city_signal",
            source_type="event_dossier",
            source_id=dossier.id,
        )
    remember_idempotent(
        db,
        user.id,
        idempotency_key,
        "engagement.dossier.investigate",
        progress.id,
        {"progress_id": progress.id},
    )
    db.flush()
    return progress


def list_collection(
    db: Session, profile: PlayerProfile
) -> list[tuple[PlayerCollection, CollectionItem]]:
    ensure_collection_catalog(db)
    rows = db.execute(
        select(PlayerCollection, CollectionItem)
        .join(CollectionItem, CollectionItem.id == PlayerCollection.item_id)
        .where(PlayerCollection.profile_id == profile.id)
        .order_by(PlayerCollection.unlocked_at.desc())
    ).all()
    return [(owned, item) for owned, item in rows]


def update_identity(
    db: Session,
    profile: PlayerProfile,
    *,
    title_item_id: str | None,
    emblem_item_id: str | None,
    hq_cosmetic_item_id: str | None,
    profile_card_public: bool,
) -> PlayerIdentity:
    identity = db.scalar(
        select(PlayerIdentity).where(PlayerIdentity.profile_id == profile.id).with_for_update()
    )
    if identity is None:
        identity = PlayerIdentity(profile_id=profile.id)
        db.add(identity)
        db.flush()
    requested = {
        "title": title_item_id,
        "emblem": emblem_item_id,
        "hq_cosmetic": hq_cosmetic_item_id,
    }
    for item_type, item_id in requested.items():
        if item_id is None:
            continue
        owned = db.scalar(
            select(PlayerCollection)
            .join(CollectionItem, CollectionItem.id == PlayerCollection.item_id)
            .where(
                PlayerCollection.profile_id == profile.id,
                CollectionItem.id == item_id,
                CollectionItem.item_type == item_type,
            )
        )
        if owned is None:
            raise DomainError(403, "engagement.collection_not_owned", "Collection item not owned")
    identity.active_title_item_id = title_item_id
    identity.active_emblem_item_id = emblem_item_id
    identity.active_hq_cosmetic_item_id = hq_cosmetic_item_id
    identity.profile_card_public = profile_card_public
    db.flush()
    return identity


def profile_card(db: Session, profile: PlayerProfile) -> dict[str, Any]:
    identity = db.scalar(select(PlayerIdentity).where(PlayerIdentity.profile_id == profile.id))
    doctrine = db.scalar(select(PlayerDoctrine).where(PlayerDoctrine.profile_id == profile.id))
    mastery = list(
        db.scalars(
            select(MasteryProgress)
            .where(MasteryProgress.profile_id == profile.id)
            .order_by(MasteryProgress.points.desc())
            .limit(3)
        )
    )
    return {
        "profile_id": profile.id,
        "codename": profile.codename,
        "doctrine_key": doctrine.doctrine_key if doctrine else None,
        "active_title_item_id": identity.active_title_item_id if identity else None,
        "active_emblem_item_id": identity.active_emblem_item_id if identity else None,
        "active_hq_cosmetic_item_id": (identity.active_hq_cosmetic_item_id if identity else None),
        "profile_card_public": identity.profile_card_public if identity else True,
        "mastery_highlights": [
            {"area_key": item.area_key, "level": item.level, "points": item.points}
            for item in mastery
        ],
    }


def offer_return_contracts(
    db: Session, profile: PlayerProfile, *, now: datetime | None = None
) -> list[ReturnContract]:
    timestamp = as_utc(now or datetime.now(UTC))
    last_event = db.scalar(
        select(func.max(EngagementEvent.occurred_at)).where(
            EngagementEvent.profile_id == profile.id
        )
    )
    last_session = db.scalar(
        select(func.max(PlayerSession.ended_at)).where(PlayerSession.profile_id == profile.id)
    )
    candidates = [as_utc(profile.created_at)]
    if last_event is not None:
        candidates.append(as_utc(last_event))
    if last_session is not None:
        candidates.append(as_utc(last_session))
    absence_days = (timestamp - max(candidates)).days
    existing = list(
        db.scalars(
            select(ReturnContract)
            .where(
                ReturnContract.profile_id == profile.id,
                ReturnContract.status.in_(("offered", "active")),
            )
            .order_by(ReturnContract.offered_at.desc())
        )
    )
    if existing or absence_days < 7:
        return existing
    offered_at = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    for contract_key, title_key, description_key, event_type in RETURN_CONTRACTS:
        db.add(
            ReturnContract(
                profile_id=profile.id,
                contract_key=contract_key,
                title_key=title_key,
                description_key=description_key,
                event_type=event_type,
                absence_days=absence_days,
                offered_at=offered_at,
            )
        )
    db.flush()
    return list(
        db.scalars(
            select(ReturnContract).where(
                ReturnContract.profile_id == profile.id,
                ReturnContract.offered_at == offered_at,
            )
        )
    )


def select_return_contract(db: Session, profile: PlayerProfile, contract_id: str) -> ReturnContract:
    contract = db.scalar(
        select(ReturnContract)
        .where(ReturnContract.id == contract_id, ReturnContract.profile_id == profile.id)
        .with_for_update()
    )
    if contract is None:
        raise DomainError(404, "engagement.return_contract_not_found", "Return contract not found")
    if contract.status != "offered":
        return contract
    active = db.scalar(
        select(ReturnContract).where(
            ReturnContract.profile_id == profile.id,
            ReturnContract.status == "active",
        )
    )
    if active is not None:
        raise DomainError(409, "engagement.return_contract_active", "A return contract is active")
    contract.status = "active"
    contract.selected_at = datetime.now(UTC)
    db.flush()
    return contract


def rankings(db: Session, profile: PlayerProfile) -> dict[str, object]:
    with _RANKING_LOCK:
        return _rankings_locked(db, profile)


def _rankings_locked(db: Session, profile: PlayerProfile) -> dict[str, object]:
    visible_profiles = list(
        db.scalars(
            select(PlayerProfile)
            .outerjoin(EngagementSetting, EngagementSetting.profile_id == PlayerProfile.id)
            .where(
                PlayerProfile.world_id == profile.world_id,
                (EngagementSetting.ranking_visible.is_(True)) | (EngagementSetting.id.is_(None)),
            )
            .with_for_update()
        )
    )
    values: dict[str, dict[str, int]] = {}
    for item in visible_profiles:
        resources = db.get(ResourceBalance, item.id)
        company_count = int(
            db.scalar(
                select(func.count())
                .select_from(Company)
                .where(Company.founder_profile_id == item.id)
            )
            or 0
        )
        profit = int(
            db.scalar(
                select(func.coalesce(func.sum(CompanyEconomyReport.profit_cents), 0))
                .join(Company, Company.id == CompanyEconomyReport.company_id)
                .where(Company.founder_profile_id == item.id)
            )
            or 0
        )
        mastery = {
            row.area_key: row.points
            for row in db.scalars(
                select(MasteryProgress).where(MasteryProgress.profile_id == item.id)
            )
        }
        event_counts = {
            event_type: int(count)
            for event_type, count in db.execute(
                select(EngagementEvent.event_type, func.count())
                .where(EngagementEvent.profile_id == item.id)
                .group_by(EngagementEvent.event_type)
            )
        }
        membership = db.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.profile_id == item.id,
                OrganizationMembership.status == "active",
            )
        )
        values[item.id] = {
            "company_value": company_count * 10_000 + max(0, profit // 100),
            "sustainable_profit": max(0, profit),
            "innovation": mastery.get("people_leadership", 0)
            + mastery.get("company_management", 0),
            "contract_reliability": mastery.get("contract_management", 0),
            "portfolio_return": mastery.get("capital_markets", 0),
            "district_development": item.stability * 100,
            "cartel_influence": event_counts.get("cartel.project_contributed", 0) * 100
            + (100 if membership else 0),
            "intelligence_success": event_counts.get("intelligence.report_acquired", 0) * 100,
            "diplomatic_stability": item.legitimacy * 100 + mastery.get("diplomacy", 0),
            "comeback_performance": int(
                db.scalar(
                    select(func.count())
                    .select_from(ReturnContract)
                    .where(
                        ReturnContract.profile_id == item.id, ReturnContract.status == "completed"
                    )
                )
                or 0
            )
            * 100,
            "mentoring": int(
                db.scalar(
                    select(func.count())
                    .select_from(Mentorship)
                    .where(
                        Mentorship.mentor_profile_id == item.id, Mentorship.status == "completed"
                    )
                )
                or 0
            )
            * 100,
            "season_goals": int(
                db.scalar(
                    select(func.count())
                    .select_from(PlayerSeasonGoal)
                    .where(
                        PlayerSeasonGoal.profile_id == item.id,
                        PlayerSeasonGoal.status == "completed",
                    )
                )
                or 0
            )
            * 100,
        }
        if resources is not None:
            values[item.id]["company_value"] += max(0, int(resources.capital))
    bests = {
        (item.profile_id, item.category): item
        for item in db.scalars(
            select(PlayerRankingBest).where(
                PlayerRankingBest.profile_id.in_([item.id for item in visible_profiles])
            )
        )
    }
    categories: list[dict[str, object]] = []
    for category in RANKING_CATEGORIES:
        ordered = sorted(
            visible_profiles,
            key=lambda item: (-values[item.id][category], item.created_at, item.id),
        )
        entries: list[dict[str, object]] = []
        for index, item in enumerate(ordered[:100], start=1):
            score = values[item.id][category]
            best = bests.get((item.id, category))
            if best is None:
                best = PlayerRankingBest(
                    profile_id=item.id,
                    category=category,
                    best_score=score,
                    achieved_at=datetime.now(UTC),
                )
                db.add(best)
                bests[(item.id, category)] = best
            elif score > best.best_score:
                best.best_score = score
                best.achieved_at = datetime.now(UTC)
            entries.append(
                {
                    "rank": index,
                    "profile_id": item.id,
                    "codename": item.codename,
                    "score": score,
                    "historical_best_score": best.best_score,
                    "bracket": "newcomer"
                    if (datetime.now(UTC) - as_utc(item.created_at)).days < 30
                    else "veteran",
                    "is_self": item.id == profile.id,
                }
            )
        categories.append(
            {
                "category": category,
                "entries": entries,
            }
        )
    db.flush()
    return {"categories": categories, "economic_rewards": False}
