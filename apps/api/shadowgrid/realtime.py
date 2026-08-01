from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from shadowgrid.errors import DomainError
from shadowgrid.models import (
    OrganizationMembership,
    PlayerProfile,
    RealtimeEvent,
    as_utc,
    uuid_str,
)

EVENT_VERSION = 1
MAX_EVENT_PAYLOAD_BYTES = 16_384
_EVENT_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")
_AUDIENCE_TYPES = {"world", "player", "cartel", "city"}
_CANONICAL_REQUIRED_FIELDS: dict[str, frozenset[str]] = {
    "player.resources.updated": frozenset({"profile_id", "resource_type"}),
    "company.metrics.updated": frozenset({"company_id", "version"}),
    "market.snapshot.created": frozenset({"tick_id"}),
    "exchange.order.updated": frozenset({"order_id", "status"}),
    "exchange.trade.executed": frozenset({"trade_id", "listing_id"}),
    "cartel.invitation.created": frozenset({"invitation_id", "cartel_id"}),
    "cartel.project.updated": frozenset({"project_id", "status"}),
    "world.event.started": frozenset({"event_id", "status"}),
    "world.event.ended": frozenset({"event_id", "status"}),
    "notification.created": frozenset({"notification_id"}),
    "season.phase.changed": frozenset({"season_id", "phase"}),
}


def validate_event_payload(event_type: str, payload: dict[str, Any]) -> None:
    if not _EVENT_TYPE_PATTERN.fullmatch(event_type):
        raise ValueError("Realtime event type must use dotted lowercase naming")
    if not isinstance(payload, dict):
        raise ValueError("Realtime event payload must be an object")
    missing = _CANONICAL_REQUIRED_FIELDS.get(event_type, frozenset()) - payload.keys()
    if missing:
        raise ValueError(f"Realtime event payload is missing fields: {', '.join(sorted(missing))}")
    try:
        encoded = json.dumps(
            payload,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("Realtime event payload is not JSON serializable") from exc
    if len(encoded) > MAX_EVENT_PAYLOAD_BYTES:
        raise ValueError("Realtime event payload exceeds 16 KiB")


def emit_realtime_event(
    db: Session,
    *,
    world_id: str,
    event_type: str,
    payload: dict[str, Any],
    audience_type: str = "world",
    audience_id: str | None = None,
    dedupe_key: str | None = None,
    at: datetime | None = None,
    ttl: timedelta = timedelta(days=7),
) -> RealtimeEvent:
    validate_event_payload(event_type, payload)
    if audience_type not in _AUDIENCE_TYPES:
        raise ValueError("Unsupported realtime audience")
    if audience_type == "world" and audience_id is not None:
        raise ValueError("World realtime audience cannot define audience_id")
    if audience_type != "world" and audience_id is None:
        raise ValueError("Scoped realtime audience requires audience_id")
    if dedupe_key is not None:
        for pending in db.new:
            if (
                isinstance(pending, RealtimeEvent)
                and pending.world_id == world_id
                and pending.dedupe_key == dedupe_key
            ):
                return pending
        with db.no_autoflush:
            existing = db.scalar(
                select(RealtimeEvent).where(
                    RealtimeEvent.world_id == world_id,
                    RealtimeEvent.dedupe_key == dedupe_key,
                )
            )
        if existing is not None:
            return existing
    now = as_utc(at or datetime.now(UTC))
    event = RealtimeEvent(
        id=uuid_str(),
        world_id=world_id,
        profile_id=audience_id if audience_type == "player" else None,
        event_type=event_type,
        event_version=EVENT_VERSION,
        audience_type=audience_type,
        audience_id=audience_id,
        dedupe_key=dedupe_key,
        payload_json=payload,
        created_at=now,
        expires_at=now + ttl,
    )
    db.add(event)
    return event


def profile_cartel_id(db: Session, profile_id: str) -> str | None:
    return db.scalar(
        select(OrganizationMembership.organization_id).where(
            OrganizationMembership.profile_id == profile_id,
            OrganizationMembership.status == "active",
        )
    )


def channel_names(db: Session, profile: PlayerProfile) -> list[str]:
    channels = [
        f"world:{profile.world_id}",
        f"city:{profile.city_id}",
        f"player:{profile.id}",
    ]
    cartel_id = profile_cartel_id(db, profile.id)
    if cartel_id is not None:
        channels.append(f"cartel:{cartel_id}")
    return channels


def accessible_event_filter(
    db: Session,
    profile: PlayerProfile,
) -> Any:
    cartel_id = profile_cartel_id(db, profile.id)
    audiences = [
        and_(
            RealtimeEvent.audience_type == "world",
            RealtimeEvent.audience_id.is_(None),
        ),
        and_(
            RealtimeEvent.audience_type == "player",
            RealtimeEvent.audience_id == profile.id,
        ),
        and_(
            RealtimeEvent.audience_type == "city",
            RealtimeEvent.audience_id == profile.city_id,
        ),
    ]
    if cartel_id is not None:
        audiences.append(
            and_(
                RealtimeEvent.audience_type == "cartel",
                RealtimeEvent.audience_id == cartel_id,
            )
        )
    return or_(*audiences)


def list_realtime_events(
    db: Session,
    profile: PlayerProfile,
    *,
    after_id: str | None = None,
    limit: int = 100,
    at: datetime | None = None,
) -> list[RealtimeEvent]:
    now = as_utc(at or datetime.now(UTC))
    statement = select(RealtimeEvent).where(
        RealtimeEvent.world_id == profile.world_id,
        RealtimeEvent.expires_at > now,
        accessible_event_filter(db, profile),
    )
    if after_id is not None:
        anchor = db.scalar(
            select(RealtimeEvent).where(
                RealtimeEvent.id == after_id,
                RealtimeEvent.world_id == profile.world_id,
                accessible_event_filter(db, profile),
            )
        )
        if anchor is None:
            raise DomainError(
                404,
                "realtime.cursor_not_found",
                "Realtime cursor is unavailable",
            )
        statement = statement.where(
            or_(
                RealtimeEvent.created_at > anchor.created_at,
                and_(
                    RealtimeEvent.created_at == anchor.created_at,
                    RealtimeEvent.id > anchor.id,
                ),
            )
        )
    return list(
        db.scalars(
            statement.order_by(RealtimeEvent.created_at, RealtimeEvent.id).limit(
                min(max(limit, 1), 100)
            )
        )
    )


def list_realtime_events_after(
    db: Session,
    profile: PlayerProfile,
    *,
    created_at: datetime,
    event_id: str,
    limit: int = 100,
    at: datetime | None = None,
) -> list[RealtimeEvent]:
    now = as_utc(at or datetime.now(UTC))
    return list(
        db.scalars(
            select(RealtimeEvent)
            .where(
                RealtimeEvent.world_id == profile.world_id,
                RealtimeEvent.expires_at > now,
                accessible_event_filter(db, profile),
                or_(
                    RealtimeEvent.created_at > created_at,
                    and_(
                        RealtimeEvent.created_at == created_at,
                        RealtimeEvent.id > event_id,
                    ),
                ),
            )
            .order_by(RealtimeEvent.created_at, RealtimeEvent.id)
            .limit(min(max(limit, 1), 100))
        )
    )


def realtime_cursor(
    db: Session,
    profile: PlayerProfile,
    event_id: str,
) -> tuple[datetime, str]:
    event = db.scalar(
        select(RealtimeEvent).where(
            RealtimeEvent.id == event_id,
            RealtimeEvent.world_id == profile.world_id,
            accessible_event_filter(db, profile),
        )
    )
    if event is None:
        raise DomainError(
            404,
            "realtime.cursor_not_found",
            "Realtime cursor is unavailable",
        )
    return as_utc(event.created_at), event.id


def event_channel(event: RealtimeEvent) -> str:
    if event.audience_type == "world":
        return f"world:{event.world_id}"
    if event.audience_id is None:
        raise RuntimeError("Scoped realtime event is missing audience_id")
    return f"{event.audience_type}:{event.audience_id}"
