from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

from shadowgrid.database import SessionLocal
from shadowgrid.models import RateLimitBucket
from shadowgrid.rate_limits import clear_rate_limit, consume_rate_limit
from sqlalchemy import func, select


def test_rate_limit_bucket_is_atomic_shared_and_windowed() -> None:
    at = datetime(2026, 7, 28, 12, 0, 30, tzinfo=UTC)

    def consume(_: int) -> int:
        attempts, _ = consume_rate_limit(
            scope="test.concurrent",
            raw_key="player-1",
            limit=20,
            window_seconds=60,
            at=at,
        )
        return attempts

    with ThreadPoolExecutor(max_workers=8) as pool:
        attempts = list(pool.map(consume, range(12)))

    assert sorted(attempts) == list(range(1, 13))
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RateLimitBucket)) == 1

    next_attempt, _ = consume_rate_limit(
        scope="test.concurrent",
        raw_key="player-1",
        limit=20,
        window_seconds=60,
        at=at + timedelta(seconds=60),
    )
    assert next_attempt == 1


def test_rate_limit_clear_removes_only_the_selected_identity() -> None:
    at = datetime(2026, 7, 28, 12, 0, 30, tzinfo=UTC)
    for key in ("first", "second"):
        consume_rate_limit(
            scope="auth.login",
            raw_key=key,
            limit=8,
            window_seconds=600,
            at=at,
        )

    clear_rate_limit(scope="auth.login", raw_key="first")

    with SessionLocal() as db:
        remaining = list(db.scalars(select(RateLimitBucket)))
    assert len(remaining) == 1
