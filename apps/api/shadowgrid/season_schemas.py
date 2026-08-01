from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

SeasonPhase = Literal["setup", "early", "mid", "late", "scoring", "archived"]


class SeasonTemplateView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    template_key: str
    version: int
    name: str
    duration_minutes: int
    phase_weights_json: dict[str, int]
    goals_json: list[dict[str, Any]]
    scoring_categories_json: list[str]
    starting_cash_cents: int
    enabled: bool
    created_at: datetime


class SeasonView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    template_id: str
    season_number: int
    name: str
    phase: SeasonPhase
    status: Literal["active", "scoring", "archived"]
    goals_json: list[dict[str, Any]]
    scoring_categories_json: list[str]
    phase_schedule_json: list[dict[str, Any]]
    starting_cash_cents: int
    starts_at: datetime
    ends_at: datetime
    phase_changed_at: datetime
    scoring_started_at: datetime | None
    closed_at: datetime | None
    archived_at: datetime | None
    created_at: datetime
    phase_ends_at: datetime
    remaining_seconds: int


class SeasonScoreView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    category: str
    entity_type: str
    entity_id: str
    entity_name: str
    score_value: int
    rank: int
    tied: bool
    metrics_json: dict[str, Any]
    captured_at: datetime | None


class HallOfFameView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    season_id: str
    season_number: int
    category: str
    entity_type: str
    entity_id: str
    entity_name: str
    score_value: int
    rank: int
    tied: bool
    metrics_json: dict[str, Any]
    awarded_at: datetime


class AccountRewardView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    season_id: str
    reward_type: Literal["achievement", "title", "cosmetic"]
    reward_key: str
    label: str
    metadata_json: dict[str, Any]
    awarded_at: datetime


class SeasonCloseView(BaseModel):
    season: SeasonView
    score_count: int
    hall_of_fame_count: int
    reward_count: int
    archive_count: int


class ShortenSeasonRequest(BaseModel):
    duration_minutes: int = Field(ge=5, le=201_600)


class SimulateSeasonRequest(BaseModel):
    at: datetime


class CreateSeasonRequest(BaseModel):
    world_id: str = Field(min_length=36, max_length=36)
    template_key: str = Field(default="cologne_standard", min_length=1, max_length=60)
    template_version: int = Field(default=1, ge=1)
    starts_at: datetime | None = None


class HallOfFameQuery(BaseModel):
    season_number: int | None = Field(default=None, ge=0)
    category: str | None = Field(default=None, min_length=1, max_length=48)

    @model_validator(mode="after")
    def validate_category(self) -> HallOfFameQuery:
        if self.category is not None and not self.category.strip():
            raise ValueError("category cannot be blank")
        return self
