from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import jwt
import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlalchemy import select
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.models import RefreshSession, User, as_utc

password_hasher = PasswordHasher(
    time_cost=3, memory_cost=65_536, parallelism=4, hash_len=32, salt_len=16
)


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    try:
        return password_hasher.verify(encoded, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def hash_token(token: str, pepper: str) -> str:
    return hmac.new(pepper.encode(), token.encode(), hashlib.sha256).hexdigest()


def create_access_token(user: User, session_id: str, settings: Settings) -> tuple[str, int]:
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    payload: dict[str, Any] = {
        "sub": user.id,
        "sid": session_id,
        "type": "access",
        "iat": now,
        "nbf": now,
        "exp": now + lifetime,
        "jti": str(uuid4()),
    }
    encoded = jwt.encode(payload, settings.secret_key.get_secret_value(), algorithm="HS256")
    return encoded, int(lifetime.total_seconds())


def decode_access_token(token: str, settings: Settings) -> dict[str, Any]:
    payload = jwt.decode(token, settings.secret_key.get_secret_value(), algorithms=["HS256"])
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("unexpected token type")
    return payload


def create_refresh_session(
    db: Session,
    user: User,
    settings: Settings,
    user_agent: str,
    family_id: str | None = None,
) -> tuple[RefreshSession, str]:
    raw = secrets.token_urlsafe(48)
    session = RefreshSession(
        user_id=user.id,
        family_id=family_id or str(uuid4()),
        token_hash=hash_token(raw, settings.refresh_pepper.get_secret_value()),
        user_agent=user_agent[:180] or "unknown",
        expires_at=datetime.now(UTC) + timedelta(days=settings.refresh_token_days),
    )
    db.add(session)
    db.flush()
    return session, raw


def rotate_refresh_session(
    db: Session, raw: str, settings: Settings, user_agent: str
) -> tuple[User, RefreshSession, str] | None:
    token_hash = hash_token(raw, settings.refresh_pepper.get_secret_value())
    current = db.scalar(
        select(RefreshSession).where(RefreshSession.token_hash == token_hash).with_for_update()
    )
    now = datetime.now(UTC)
    if current is None:
        return None
    if current.rotated_at or current.revoked_at or as_utc(current.expires_at) <= now:
        db.query(RefreshSession).filter(RefreshSession.family_id == current.family_id).update(
            {RefreshSession.revoked_at: now}
        )
        db.commit()
        return None
    current.rotated_at = now
    user = db.get(User, current.user_id)
    if user is None or user.disabled_at is not None:
        return None
    new_session, new_raw = create_refresh_session(db, user, settings, user_agent, current.family_id)
    db.commit()
    return user, new_session, new_raw


def verify_totp(user: User, code: str | None) -> bool:
    if not user.totp_secret:
        return True
    return bool(code and pyotp.TOTP(user.totp_secret).verify(code, valid_window=1))
