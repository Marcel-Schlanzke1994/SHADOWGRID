from __future__ import annotations

from datetime import UTC, datetime


def period_start_for(at: datetime) -> datetime:
    if at.tzinfo is None:
        raise ValueError("tick timestamps must include a timezone")
    return at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)


def period_key_for(at: datetime) -> str:
    return period_start_for(at).strftime("%Y-%m-%dT%H:00:00Z")
