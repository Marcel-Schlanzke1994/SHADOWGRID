from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select

from shadowgrid.dependencies import (
    CurrentProfile,
    CurrentUser,
    Db,
    IdempotencyKey,
    require_admin,
)
from shadowgrid.errors import DomainError
from shadowgrid.models import (
    AccountReward,
    HallOfFameEntry,
    Season,
    SeasonTemplate,
    User,
    World,
    as_utc,
)
from shadowgrid.season_schemas import (
    AccountRewardView,
    CreateSeasonRequest,
    HallOfFameView,
    SeasonCloseView,
    SeasonScoreView,
    SeasonTemplateView,
    SeasonView,
    ShortenSeasonRequest,
    SimulateSeasonRequest,
)
from shadowgrid.seasons import (
    SeasonCloseResult,
    close_season,
    create_season_from_template,
    current_season,
    leaderboard,
    live_leaderboard,
    shorten_season,
    simulate_season,
)

router = APIRouter()
AdminUser = Annotated[User, Depends(require_admin)]


def _phase_end(season: Season) -> datetime:
    for item in season.phase_schedule_json:
        if item["phase"] == season.phase:
            return datetime.fromisoformat(str(item["ends_at"])).astimezone(UTC)
    return as_utc(season.ends_at)


def _season_view(season: Season, *, at: datetime | None = None) -> SeasonView:
    now = as_utc(at or datetime.now(UTC))
    phase_ends_at = _phase_end(season)
    data = SeasonView.model_validate(
        {
            **{
                key: getattr(season, key)
                for key in SeasonView.model_fields
                if key not in {"phase_ends_at", "remaining_seconds"}
            },
            "phase_ends_at": phase_ends_at,
            "remaining_seconds": max(0, int((phase_ends_at - now).total_seconds())),
        }
    )
    return data


def _close_view(result: SeasonCloseResult, *, at: datetime) -> SeasonCloseView:
    return SeasonCloseView(
        season=_season_view(result.season, at=at),
        score_count=result.score_count,
        hall_of_fame_count=result.hall_of_fame_count,
        reward_count=result.reward_count,
        archive_count=result.archive_count,
    )


@router.get(
    "/seasons/current",
    response_model=SeasonView,
    tags=["seasons"],
)
def get_current_season(db: Db, profile: CurrentProfile) -> SeasonView:
    return _season_view(current_season(db, profile.world_id))


@router.get(
    "/seasons/current/leaderboards/{category}",
    response_model=list[SeasonScoreView],
    tags=["seasons", "leaderboards"],
)
def get_current_leaderboard(
    category: str,
    db: Db,
    profile: CurrentProfile,
) -> list[SeasonScoreView]:
    season = current_season(db, profile.world_id)
    if season.status == "archived":
        rows: list[Any] = leaderboard(db, season_id=season.id, category=category)
    else:
        rows = live_leaderboard(db, season=season, category=category)
    return [SeasonScoreView.model_validate(row) for row in rows]


@router.get(
    "/seasons/{season_id}/leaderboards/{category}",
    response_model=list[SeasonScoreView],
    tags=["seasons", "leaderboards"],
)
def get_season_leaderboard(
    season_id: str,
    category: str,
    db: Db,
    profile: CurrentProfile,
) -> list[SeasonScoreView]:
    season = db.get(Season, season_id)
    if season is None or season.world_id != profile.world_id:
        raise DomainError(404, "season.not_found", "Season not found")
    rows = (
        leaderboard(db, season_id=season.id, category=category)
        if season.status == "archived"
        else live_leaderboard(db, season=season, category=category)
    )
    return [SeasonScoreView.model_validate(row) for row in rows]


@router.get(
    "/hall-of-fame",
    response_model=list[HallOfFameView],
    tags=["seasons", "leaderboards"],
)
def hall_of_fame(
    db: Db,
    profile: CurrentProfile,
    season_number: int | None = Query(default=None, ge=0),
    category: str | None = Query(default=None, min_length=1, max_length=48),
) -> list[HallOfFameEntry]:
    statement = (
        select(HallOfFameEntry)
        .join(Season, Season.id == HallOfFameEntry.season_id)
        .where(Season.world_id == profile.world_id)
    )
    if season_number is not None:
        statement = statement.where(HallOfFameEntry.season_number == season_number)
    if category is not None:
        statement = statement.where(HallOfFameEntry.category == category)
    return list(
        db.scalars(
            statement.order_by(
                HallOfFameEntry.season_number.desc(),
                HallOfFameEntry.category,
                HallOfFameEntry.rank,
                HallOfFameEntry.entity_name,
            )
        )
    )


@router.get(
    "/account/rewards/me",
    response_model=list[AccountRewardView],
    tags=["seasons", "account"],
)
def my_account_rewards(db: Db, user: CurrentUser) -> list[AccountReward]:
    return list(
        db.scalars(
            select(AccountReward)
            .where(AccountReward.user_id == user.id)
            .order_by(AccountReward.awarded_at.desc(), AccountReward.id)
        )
    )


@router.get(
    "/admin/seasons/templates",
    response_model=list[SeasonTemplateView],
    tags=["admin", "seasons"],
)
def season_templates(db: Db, _: AdminUser) -> list[SeasonTemplate]:
    return list(
        db.scalars(
            select(SeasonTemplate).order_by(
                SeasonTemplate.template_key,
                SeasonTemplate.version.desc(),
            )
        )
    )


@router.get(
    "/admin/seasons",
    response_model=list[SeasonView],
    tags=["admin", "seasons"],
)
def admin_seasons(
    world_id: str,
    db: Db,
    _: AdminUser,
) -> list[SeasonView]:
    return [
        _season_view(season)
        for season in db.scalars(
            select(Season).where(Season.world_id == world_id).order_by(Season.season_number.desc())
        )
    ]


@router.post(
    "/admin/seasons/{season_id}/shorten",
    response_model=SeasonView,
    tags=["admin", "seasons"],
)
def admin_shorten_season(
    season_id: str,
    payload: ShortenSeasonRequest,
    request: Request,
    db: Db,
    admin: AdminUser,
) -> SeasonView:
    now = datetime.now(UTC)
    season = shorten_season(
        db,
        season_id=season_id,
        duration_minutes=payload.duration_minutes,
        admin=admin,
        request_id=request.state.request_id,
        at=now,
    )
    return _season_view(season, at=now)


@router.post(
    "/admin/seasons/{season_id}/simulate",
    response_model=SeasonView | SeasonCloseView,
    tags=["admin", "seasons"],
)
def admin_simulate_season(
    season_id: str,
    payload: SimulateSeasonRequest,
    request: Request,
    db: Db,
    admin: AdminUser,
) -> SeasonView | SeasonCloseView:
    result = simulate_season(
        db,
        season_id=season_id,
        at=payload.at,
        admin=admin,
        request_id=request.state.request_id,
    )
    if isinstance(result, SeasonCloseResult):
        return _close_view(result, at=payload.at)
    return _season_view(result, at=payload.at)


@router.post(
    "/admin/seasons/{season_id}/close",
    response_model=SeasonCloseView,
    tags=["admin", "seasons"],
)
def admin_close_season(
    season_id: str,
    request: Request,
    db: Db,
    admin: AdminUser,
    _: IdempotencyKey,
) -> SeasonCloseView:
    now = datetime.now(UTC)
    result = close_season(
        db,
        season_id=season_id,
        at=now,
        admin=admin,
        request_id=request.state.request_id,
    )
    return _close_view(result, at=now)


@router.post(
    "/admin/seasons",
    response_model=SeasonView,
    status_code=status.HTTP_201_CREATED,
    tags=["admin", "seasons"],
)
def admin_create_season(
    payload: CreateSeasonRequest,
    request: Request,
    db: Db,
    admin: AdminUser,
    idempotency_key: IdempotencyKey,
) -> SeasonView:
    world = db.get(World, payload.world_id)
    if world is None:
        raise DomainError(404, "world.not_found", "World not found")
    template = db.scalar(
        select(SeasonTemplate).where(
            SeasonTemplate.template_key == payload.template_key,
            SeasonTemplate.version == payload.template_version,
        )
    )
    if template is None:
        raise DomainError(404, "season.template_not_found", "Season template not found")
    starts_at = payload.starts_at or datetime.now(UTC)
    season = create_season_from_template(
        db,
        world=world,
        template=template,
        starts_at=starts_at,
        idempotency_key=idempotency_key,
        admin=admin,
        request_id=request.state.request_id,
    )
    return _season_view(season, at=starts_at)
