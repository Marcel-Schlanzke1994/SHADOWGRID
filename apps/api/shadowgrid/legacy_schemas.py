from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ChronicleEntryView(ORMModel):
    id: str
    scope_type: Literal["company", "world", "profile"]
    scope_id: str
    source_type: str
    source_id: str
    entry_type: str
    title_key: str
    body_key: str
    cause_keys_json: list[str]
    actor_keys_json: list[str]
    impact_keys_json: list[str]
    open_question_keys_json: list[str]
    metadata_json: dict[str, object]
    created_at: datetime


class ActorRelationshipView(BaseModel):
    actor_id: str
    actor_key: str
    actor_type: Literal["entrepreneur", "journalist", "analyst", "decision_maker"]
    name_key: str
    description_key: str
    trust: int
    rivalry: int
    reputation: int
    information_access: int
    interaction_count: int
    history_keys: list[str]


class DossierClueView(BaseModel):
    id: str
    clue_key: str
    order_index: int
    rare: bool
    discovered: bool


class DossierView(BaseModel):
    id: str
    world_event_instance_id: str
    title_key: str
    cause_key: str
    local_impact_key: str
    open_question_key: str
    archived: bool
    investigation_count: int
    completed_at: datetime | None
    clues: list[DossierClueView]


class CollectionEntryView(BaseModel):
    id: str
    item_id: str
    item_key: str
    item_type: Literal["title", "emblem", "hq_cosmetic", "chronicle", "discovery"]
    title_key: str
    description_key: str
    rarity: str
    duplicate_points: int
    unlocked_at: datetime


class IdentityUpdateRequest(BaseModel):
    title_item_id: str | None = Field(default=None, min_length=36, max_length=36)
    emblem_item_id: str | None = Field(default=None, min_length=36, max_length=36)
    hq_cosmetic_item_id: str | None = Field(default=None, min_length=36, max_length=36)
    profile_card_public: bool = True


class IdentityView(ORMModel):
    id: str
    active_title_item_id: str | None
    active_emblem_item_id: str | None
    active_hq_cosmetic_item_id: str | None
    profile_card_public: bool
    updated_at: datetime


class MasteryHighlight(BaseModel):
    area_key: str
    level: int
    points: int


class ProfileCardView(BaseModel):
    profile_id: str
    codename: str
    doctrine_key: str | None
    active_title_item_id: str | None
    active_emblem_item_id: str | None
    active_hq_cosmetic_item_id: str | None
    profile_card_public: bool
    mastery_highlights: list[MasteryHighlight]


class LegacyRecordView(ORMModel):
    id: str
    record_key: str
    source_type: str
    source_id: str
    title_key: str
    metadata_json: dict[str, object]
    created_at: datetime


class SeasonGoalView(ORMModel):
    id: str
    season_id: str
    goal_key: str
    title_key: str
    description_key: str
    target_value: int
    progress_value: int
    status: Literal["offered", "active", "completed", "archived"]
    selected_at: datetime | None
    completed_at: datetime | None


class ReturnContractView(ORMModel):
    id: str
    contract_key: str
    title_key: str
    description_key: str
    target_value: int
    progress_value: int
    status: Literal["offered", "active", "completed", "declined"]
    absence_days: int
    offered_at: datetime
    selected_at: datetime | None
    completed_at: datetime | None


class RankingEntryView(BaseModel):
    rank: int
    profile_id: str
    codename: str
    score: int
    historical_best_score: int
    bracket: Literal["newcomer", "veteran"]
    is_self: bool


class RankingCategoryView(BaseModel):
    category: str
    entries: list[RankingEntryView]


class ParallelRankingsView(BaseModel):
    categories: list[RankingCategoryView]
    economic_rewards: Literal[False]
