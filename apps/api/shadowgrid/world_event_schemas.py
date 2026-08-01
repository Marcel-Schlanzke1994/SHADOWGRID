from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WorldEventDefinitionView(ORMModel):
    id: str
    event_key: str
    version: int
    title: str
    description: str
    default_scope_type: str
    default_duration_minutes: int
    effect_config_json: dict[str, int]
    enabled: bool
    created_at: datetime


class WorldEventPlanRequest(BaseModel):
    world_id: str
    event_key: str = Field(min_length=2, max_length=60)
    version: int | None = Field(default=None, ge=1)
    scope_type: str | None = Field(
        default=None,
        pattern=r"^(world|city|district|industry|company)$",
    )
    scope_id: str | None = Field(default=None, max_length=60)
    starts_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_minutes: int | None = Field(default=None, ge=1, le=43_200)
    effect_overrides: dict[str, int] = Field(default_factory=dict)


class WorldEventPreviewView(BaseModel):
    definition_id: str
    event_key: str
    template_version: int
    title: str
    description: str
    scope_type: str
    scope_id: str
    starts_at: datetime
    ends_at: datetime
    effect_config: dict[str, int]
    affected_companies: int


class WorldEventInstanceView(ORMModel):
    id: str
    world_id: str
    definition_id: str
    event_key: str
    template_version: int
    title: str
    description: str
    status: str
    scope_type: str
    scope_id: str
    effect_config_json: dict[str, int]
    starts_at: datetime
    ends_at: datetime
    activated_at: datetime | None
    ended_at: datetime | None
    end_reason: str | None
    created_at: datetime


class EndWorldEventRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=240)


class WorldEventResponseRequest(BaseModel):
    response_key: str = Field(
        min_length=2,
        max_length=60,
        pattern=r"^[a-z][a-z0-9_]*$",
    )


class WorldEventResponseView(BaseModel):
    id: str
    world_event_id: str
    response_key: str
    occurred_at: datetime
