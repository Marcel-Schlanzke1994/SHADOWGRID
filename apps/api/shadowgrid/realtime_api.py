from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from shadowgrid.dependencies import CurrentProfile, Db
from shadowgrid.models import RealtimeEvent
from shadowgrid.realtime import (
    EVENT_VERSION,
    channel_names,
    event_channel,
    list_realtime_events,
)
from shadowgrid.realtime_schemas import (
    RealtimeChannelsView,
    RealtimeEventView,
)

router = APIRouter()


def event_view(event: RealtimeEvent) -> RealtimeEventView:
    return RealtimeEventView.model_validate(
        {
            **{
                field: getattr(event, field)
                for field in RealtimeEventView.model_fields
                if field != "channel"
            },
            "channel": event_channel(event),
        }
    )


@router.get(
    "/realtime/channels",
    response_model=RealtimeChannelsView,
    tags=["realtime"],
)
def realtime_channels(
    db: Db,
    profile: CurrentProfile,
) -> RealtimeChannelsView:
    return RealtimeChannelsView(
        protocol_version=EVENT_VERSION,
        channels=channel_names(db, profile),
    )


@router.get(
    "/realtime/events",
    response_model=list[RealtimeEventView],
    tags=["realtime"],
)
def realtime_event_feed(
    db: Db,
    profile: CurrentProfile,
    after_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[RealtimeEventView]:
    return [
        event_view(event)
        for event in list_realtime_events(
            db,
            profile,
            after_id=after_id,
            limit=limit,
        )
    ]
