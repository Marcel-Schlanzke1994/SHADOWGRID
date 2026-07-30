from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from shadowgrid.database import SessionLocal
from shadowgrid.models import RateLimitBucket, uuid_str


def _key_hash(raw_key: str) -> str:
    return hashlib.sha256(raw_key.strip().lower().encode("utf-8")).hexdigest()


def consume_rate_limit(
    *,
    scope: str,
    raw_key: str,
    limit: int,
    window_seconds: int,
    at: datetime | None = None,
) -> tuple[int, int]:
    """Atomically consume a shared fixed-window limit in its own transaction."""
    if not scope or len(scope) > 40:
        raise ValueError("Rate-limit scope must contain at most 40 characters")
    if limit < 1 or window_seconds < 1:
        raise ValueError("Rate-limit bounds must be positive")
    now = (at or datetime.now(UTC)).astimezone(UTC)
    epoch = int(now.timestamp())
    window_started_at = datetime.fromtimestamp(
        epoch - (epoch % window_seconds),
        tz=UTC,
    )
    expires_at = window_started_at + timedelta(seconds=window_seconds)
    with SessionLocal() as db:
        db.execute(delete(RateLimitBucket).where(RateLimitBucket.expires_at <= now))
        attempts = _increment_bucket(
            db,
            scope=scope,
            key_hash=_key_hash(raw_key),
            window_started_at=window_started_at,
            expires_at=expires_at,
        )
        db.commit()
    retry_after = max(1, int((expires_at - now).total_seconds()))
    return attempts, retry_after


def clear_rate_limit(*, scope: str, raw_key: str) -> None:
    """Clear current and historical buckets after a successful authentication."""
    with SessionLocal() as db:
        db.execute(
            delete(RateLimitBucket).where(
                RateLimitBucket.scope == scope,
                RateLimitBucket.key_hash == _key_hash(raw_key),
            )
        )
        db.commit()


def _increment_bucket(
    db: Session,
    *,
    scope: str,
    key_hash: str,
    window_started_at: datetime,
    expires_at: datetime,
) -> int:
    values = {
        "id": uuid_str(),
        "scope": scope,
        "key_hash": key_hash,
        "window_started_at": window_started_at,
        "attempts": 1,
        "expires_at": expires_at,
    }
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        postgresql_statement = (
            postgresql_insert(RateLimitBucket)
            .values(**values)
            .on_conflict_do_update(
                constraint="uq_rate_limit_scope_key_window",
                set_={
                    "attempts": RateLimitBucket.attempts + 1,
                    "expires_at": expires_at,
                },
            )
            .returning(RateLimitBucket.attempts)
        )
        attempts = db.scalar(postgresql_statement)
        if attempts is None:
            raise RuntimeError("PostgreSQL rate-limit increment returned no value")
        return int(attempts)
    if db.bind is not None and db.bind.dialect.name == "sqlite":
        sqlite_statement = (
            sqlite_insert(RateLimitBucket)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["scope", "key_hash", "window_started_at"],
                set_={
                    "attempts": RateLimitBucket.attempts + 1,
                    "expires_at": expires_at,
                },
            )
            .returning(RateLimitBucket.attempts)
        )
        attempts = db.scalar(sqlite_statement)
        if attempts is None:
            raise RuntimeError("SQLite rate-limit increment returned no value")
        return int(attempts)

    bucket = db.scalar(
        select(RateLimitBucket)
        .where(
            RateLimitBucket.scope == scope,
            RateLimitBucket.key_hash == key_hash,
            RateLimitBucket.window_started_at == window_started_at,
        )
        .with_for_update()
    )
    if bucket is None:
        bucket = RateLimitBucket(**values)
        db.add(bucket)
        db.flush()
        return 1
    bucket.attempts += 1
    db.flush()
    return bucket.attempts
