from __future__ import annotations

from typing import Literal

from fastapi import APIRouter
from sqlalchemy import select

from shadowgrid.dependencies import CurrentProfile, CurrentUser, Db, IdempotencyKey
from shadowgrid.domain import safe_commit
from shadowgrid.legacy import (
    dossier_progress,
    ensure_dossiers,
    ensure_season_goals,
    investigate_dossier,
    list_actor_relationships,
    list_chronicle,
    list_collection,
    offer_return_contracts,
    profile_card,
    rankings,
    select_return_contract,
    select_season_goal,
    update_identity,
)
from shadowgrid.legacy_schemas import (
    ActorRelationshipView,
    ChronicleEntryView,
    CollectionEntryView,
    DossierClueView,
    DossierView,
    IdentityUpdateRequest,
    IdentityView,
    LegacyRecordView,
    ParallelRankingsView,
    ProfileCardView,
    ReturnContractView,
    SeasonGoalView,
)
from shadowgrid.models import (
    DossierClue,
    EventDossier,
    LegacyRecord,
    PlayerIdentity,
)

router = APIRouter(prefix="/engagement/legacy", tags=["engagement-legacy"])


def _dossier_view(db: Db, profile: CurrentProfile, dossier: EventDossier) -> DossierView:
    progress = dossier_progress(db, profile, dossier)
    discovered = set(progress.discovered_clue_ids_json)
    clues = list(
        db.scalars(
            select(DossierClue)
            .where(DossierClue.dossier_id == dossier.id)
            .order_by(DossierClue.order_index)
        )
    )
    return DossierView(
        id=dossier.id,
        world_event_instance_id=dossier.world_event_instance_id,
        title_key=dossier.title_key,
        cause_key=dossier.cause_key,
        local_impact_key=dossier.local_impact_key,
        open_question_key=dossier.open_question_key,
        archived=dossier.archived,
        investigation_count=progress.investigation_count,
        completed_at=progress.completed_at,
        clues=[
            DossierClueView(
                id=item.id,
                clue_key=item.clue_key,
                order_index=item.order_index,
                rare=item.rare,
                discovered=item.id in discovered,
            )
            for item in clues
        ],
    )


@router.get("/actors", response_model=list[ActorRelationshipView])
def actors(db: Db, profile: CurrentProfile) -> list[ActorRelationshipView]:
    result = [
        ActorRelationshipView(
            actor_id=actor.id,
            actor_key=actor.actor_key,
            actor_type=actor.actor_type,
            name_key=actor.name_key,
            description_key=actor.description_key,
            trust=relationship.trust if relationship else 0,
            rivalry=relationship.rivalry if relationship else 0,
            reputation=relationship.reputation if relationship else 0,
            information_access=relationship.information_access if relationship else 0,
            interaction_count=relationship.interaction_count if relationship else 0,
            history_keys=relationship.history_keys_json if relationship else [],
        )
        for actor, relationship in list_actor_relationships(db, profile)
    ]
    safe_commit(db)
    return result


@router.get(
    "/chronicles/{scope_type}/{scope_id}",
    response_model=list[ChronicleEntryView],
)
def chronicle(
    scope_type: Literal["company", "world", "profile"],
    scope_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[ChronicleEntryView]:
    return [
        ChronicleEntryView.model_validate(item)
        for item in list_chronicle(
            db,
            profile,
            scope_type=scope_type,
            scope_id=scope_id,
        )
    ]


@router.get("/dossiers", response_model=list[DossierView])
def dossiers(db: Db, profile: CurrentProfile) -> list[DossierView]:
    result = [_dossier_view(db, profile, item) for item in ensure_dossiers(db, profile)]
    safe_commit(db)
    return result


@router.post("/dossiers/{dossier_id}/investigate", response_model=DossierView)
def dossier_investigate(
    dossier_id: str,
    db: Db,
    user: CurrentUser,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> DossierView:
    progress = investigate_dossier(
        db,
        user,
        profile,
        dossier_id,
        idempotency_key=idempotency_key,
    )
    dossier = db.get(EventDossier, progress.dossier_id)
    if dossier is None:
        raise RuntimeError("Dossier progress references a missing dossier")
    safe_commit(db)
    return _dossier_view(db, profile, dossier)


@router.get("/collection", response_model=list[CollectionEntryView])
def collection(db: Db, profile: CurrentProfile) -> list[CollectionEntryView]:
    rows = list_collection(db, profile)
    safe_commit(db)
    return [
        CollectionEntryView(
            id=owned.id,
            item_id=item.id,
            item_key=item.item_key,
            item_type=item.item_type,
            title_key=item.title_key,
            description_key=item.description_key,
            rarity=item.rarity,
            duplicate_points=owned.duplicate_points,
            unlocked_at=owned.unlocked_at,
        )
        for owned, item in rows
    ]


@router.get("/identity", response_model=IdentityView)
def identity(db: Db, profile: CurrentProfile) -> IdentityView:
    value = db.scalar(select(PlayerIdentity).where(PlayerIdentity.profile_id == profile.id))
    if value is None:
        value = PlayerIdentity(profile_id=profile.id)
        db.add(value)
        safe_commit(db)
    return IdentityView.model_validate(value)


@router.put("/identity", response_model=IdentityView)
def identity_update(
    payload: IdentityUpdateRequest,
    db: Db,
    profile: CurrentProfile,
) -> IdentityView:
    value = update_identity(
        db,
        profile,
        title_item_id=payload.title_item_id,
        emblem_item_id=payload.emblem_item_id,
        hq_cosmetic_item_id=payload.hq_cosmetic_item_id,
        profile_card_public=payload.profile_card_public,
    )
    safe_commit(db)
    return IdentityView.model_validate(value)


@router.get("/profile-card", response_model=ProfileCardView)
def player_profile_card(db: Db, profile: CurrentProfile) -> ProfileCardView:
    return ProfileCardView.model_validate(profile_card(db, profile))


@router.get("/legacy-records", response_model=list[LegacyRecordView])
def legacy_records(db: Db, profile: CurrentProfile) -> list[LegacyRecordView]:
    return [
        LegacyRecordView.model_validate(item)
        for item in db.scalars(
            select(LegacyRecord)
            .where(LegacyRecord.profile_id == profile.id)
            .order_by(LegacyRecord.created_at.desc())
        )
    ]


@router.get("/season-goals", response_model=list[SeasonGoalView])
def season_goals(db: Db, profile: CurrentProfile) -> list[SeasonGoalView]:
    goals = ensure_season_goals(db, profile)
    safe_commit(db)
    return [SeasonGoalView.model_validate(item) for item in goals]


@router.post("/season-goals/{goal_id}/select", response_model=SeasonGoalView)
def season_goal_select(
    goal_id: str,
    db: Db,
    profile: CurrentProfile,
) -> SeasonGoalView:
    goal = select_season_goal(db, profile, goal_id)
    safe_commit(db)
    return SeasonGoalView.model_validate(goal)


@router.post("/return-contracts", response_model=list[ReturnContractView])
def return_contracts(db: Db, profile: CurrentProfile) -> list[ReturnContractView]:
    contracts = offer_return_contracts(db, profile)
    safe_commit(db)
    return [ReturnContractView.model_validate(item) for item in contracts]


@router.post("/return-contracts/{contract_id}/select", response_model=ReturnContractView)
def return_contract_select(
    contract_id: str,
    db: Db,
    profile: CurrentProfile,
) -> ReturnContractView:
    contract = select_return_contract(db, profile, contract_id)
    safe_commit(db)
    return ReturnContractView.model_validate(contract)


@router.get("/rankings", response_model=ParallelRankingsView)
def parallel_rankings(db: Db, profile: CurrentProfile) -> ParallelRankingsView:
    result = ParallelRankingsView.model_validate(rankings(db, profile))
    safe_commit(db)
    return result
