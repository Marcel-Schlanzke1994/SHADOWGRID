from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import select

from shadowgrid.dependencies import (
    CurrentProfile,
    Db,
    IdempotencyKey,
    request_id,
    require_admin,
)
from shadowgrid.domain import safe_commit
from shadowgrid.models import User, WorldEventDefinition, WorldEventInstance
from shadowgrid.world_event_schemas import (
    EndWorldEventRequest,
    WorldEventDefinitionView,
    WorldEventInstanceView,
    WorldEventPlanRequest,
    WorldEventPreviewView,
    WorldEventResponseRequest,
    WorldEventResponseView,
)
from shadowgrid.world_events import (
    activate_event,
    end_event,
    event_feed,
    preview_event,
    respond_to_event,
)

router = APIRouter()
AdminUser = Annotated[User, Depends(require_admin)]


@router.get(
    "/admin/world-events/definitions",
    response_model=list[WorldEventDefinitionView],
    tags=["admin", "world-events"],
)
def world_event_definitions(db: Db, _: AdminUser) -> list[WorldEventDefinition]:
    return list(
        db.scalars(
            select(WorldEventDefinition).order_by(
                WorldEventDefinition.event_key,
                WorldEventDefinition.version.desc(),
            )
        )
    )


@router.post(
    "/admin/world-events/preview",
    response_model=WorldEventPreviewView,
    tags=["admin", "world-events"],
)
def world_event_preview(
    payload: WorldEventPlanRequest,
    db: Db,
    _: AdminUser,
) -> WorldEventPreviewView:
    preview = preview_event(
        db,
        world_id=payload.world_id,
        event_key=payload.event_key,
        version=payload.version,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        effect_overrides=payload.effect_overrides,
    )
    return WorldEventPreviewView(
        definition_id=preview.definition_id,
        event_key=preview.event_key,
        template_version=preview.template_version,
        title=preview.title,
        description=preview.description,
        scope_type=preview.scope_type,
        scope_id=preview.scope_id,
        starts_at=preview.starts_at,
        ends_at=preview.ends_at,
        effect_config=preview.effect_config,
        affected_companies=preview.affected_companies,
    )


@router.post(
    "/admin/world-events/activate",
    response_model=WorldEventInstanceView,
    status_code=status.HTTP_201_CREATED,
    tags=["admin", "world-events"],
)
def world_event_activate(
    payload: WorldEventPlanRequest,
    request: Request,
    db: Db,
    admin: AdminUser,
    key: IdempotencyKey,
) -> WorldEventInstance:
    instance = activate_event(
        db,
        admin=admin,
        world_id=payload.world_id,
        event_key=payload.event_key,
        version=payload.version,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
        starts_at=payload.starts_at,
        duration_minutes=payload.duration_minutes,
        effect_overrides=payload.effect_overrides,
        idempotency_key=key,
        request_id=request_id(request),
    )
    safe_commit(db)
    return instance


@router.post(
    "/admin/world-events/{instance_id}/end",
    response_model=WorldEventInstanceView,
    tags=["admin", "world-events"],
)
def world_event_end(
    instance_id: str,
    payload: EndWorldEventRequest,
    request: Request,
    db: Db,
    admin: AdminUser,
    _: IdempotencyKey,
) -> WorldEventInstance:
    instance = end_event(
        db,
        admin=admin,
        instance_id=instance_id,
        reason=payload.reason,
        request_id=request_id(request),
    )
    safe_commit(db)
    return instance


@router.get(
    "/world-events/current",
    response_model=list[WorldEventInstanceView],
    tags=["world-events"],
)
def world_event_current(db: Db, profile: CurrentProfile) -> list[WorldEventInstance]:
    return event_feed(db, profile.world_id)


@router.post(
    "/world-events/{instance_id}/responses",
    response_model=WorldEventResponseView,
    tags=["world-events", "engagement"],
)
def world_event_response(
    instance_id: str,
    payload: WorldEventResponseRequest,
    db: Db,
    profile: CurrentProfile,
    key: IdempotencyKey,
) -> WorldEventResponseView:
    response = respond_to_event(
        db,
        profile,
        instance_id=instance_id,
        response_key=payload.response_key,
        idempotency_key=key,
    )
    safe_commit(db)
    return WorldEventResponseView.model_validate(response)
