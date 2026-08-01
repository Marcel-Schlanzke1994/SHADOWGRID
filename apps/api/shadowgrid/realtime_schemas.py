from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class RealtimeConnectMessage(BaseModel):
    access_token: str = Field(min_length=16, max_length=4_096)
    world_id: str | None = Field(default=None, min_length=36, max_length=36)
    last_event_id: str | None = Field(default=None, min_length=36, max_length=36)
    protocol_version: Literal[1] = 1


class RealtimeEventView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    event_type: str
    event_version: int
    audience_type: Literal["world", "player", "cartel", "city"]
    channel: str
    payload_json: dict[str, Any]
    created_at: datetime
    expires_at: datetime


class RealtimeChannelsView(BaseModel):
    protocol_version: int
    channels: list[str]
