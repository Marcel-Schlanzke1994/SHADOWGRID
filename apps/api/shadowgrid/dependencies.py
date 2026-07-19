from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from shadowgrid.config import Settings, get_settings
from shadowgrid.database import get_db
from shadowgrid.models import PlayerProfile, RefreshSession, User, as_utc
from shadowgrid.security import decode_access_token

bearer = HTTPBearer(auto_error=False)
Db = Annotated[Session, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def current_user(
    db: Db,
    settings: AppSettings,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.required", "message": "Authentication required"},
        )
    try:
        payload = decode_access_token(credentials.credentials, settings)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.invalid_token", "message": "Invalid or expired access token"},
        ) from exc
    session = db.get(RefreshSession, payload.get("sid"))
    user = db.get(User, payload.get("sub"))
    now = datetime.now(UTC)
    if (
        user is None
        or user.disabled_at is not None
        or session is None
        or session.revoked_at is not None
        or as_utc(session.expires_at) <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "auth.session_revoked", "message": "Session is no longer active"},
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def current_profile(
    db: Db, user: CurrentUser, x_world_id: Annotated[str | None, Header()] = None
) -> PlayerProfile:
    query = db.query(PlayerProfile).filter(PlayerProfile.user_id == user.id)
    if x_world_id:
        query = query.filter(PlayerProfile.world_id == x_world_id)
    profile = query.order_by(PlayerProfile.created_at.desc()).first()
    if profile is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "world.not_joined",
                "message": "Join a world before using this endpoint",
            },
        )
    return profile


CurrentProfile = Annotated[PlayerProfile, Depends(current_profile)]


def require_admin(user: CurrentUser) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail={"code": "auth.forbidden", "message": "Administrator permission required"},
        )
    return user


def request_id(request: Request) -> str:
    return str(request.state.request_id)


def require_idempotency(
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> str:
    if not idempotency_key or not 8 <= len(idempotency_key) <= 80:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "request.idempotency_required",
                "message": "A valid Idempotency-Key header is required",
            },
        )
    return idempotency_key


IdempotencyKey = Annotated[str, Depends(require_idempotency)]
