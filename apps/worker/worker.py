from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast

from arq import cron
from arq.connections import RedisSettings
from arq.typing import WorkerCoroutine

API_ROOT = Path(__file__).resolve().parents[1] / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from shadowgrid.ai import run_due_ai_ticks  # noqa: E402
from shadowgrid.config import get_settings  # noqa: E402
from shadowgrid.database import SessionLocal  # noqa: E402
from shadowgrid.domain import resolve_due, settle_businesses  # noqa: E402
from shadowgrid.economy import run_due_economy_ticks  # noqa: E402
from shadowgrid.exchange import expire_due_orders  # noqa: E402
from shadowgrid.mailer import deliver_pending_email  # noqa: E402
from shadowgrid.progression import expire_delegations, expire_pauses  # noqa: E402
from shadowgrid.specialists import (  # noqa: E402
    run_due_specialist_market_refresh,
    run_due_specialist_payrolls,
)


async def due_every_minute(_: dict[Any, Any], *args: Any, **kwargs: Any) -> dict[str, int]:
    db = SessionLocal()
    try:
        return resolve_due(db, get_settings())
    finally:
        db.close()


async def settle_hourly(_: dict[Any, Any], *args: Any, **kwargs: Any) -> int:
    db = SessionLocal()
    try:
        return settle_businesses(db)
    finally:
        db.close()


async def economy_hourly(_: dict[Any, Any], *args: Any, **kwargs: Any) -> int:
    db = SessionLocal()
    try:
        return run_due_economy_ticks(db)
    finally:
        db.close()


async def specialist_market_daily(_: dict[Any, Any], *args: Any, **kwargs: Any) -> int:
    db = SessionLocal()
    try:
        return run_due_specialist_market_refresh(db)
    finally:
        db.close()


async def specialist_payroll_hourly(_: dict[Any, Any], *args: Any, **kwargs: Any) -> int:
    db = SessionLocal()
    try:
        return run_due_specialist_payrolls(db)
    finally:
        db.close()


async def ai_hourly(_: dict[Any, Any], *args: Any, **kwargs: Any) -> int:
    db = SessionLocal()
    try:
        return run_due_ai_ticks(db, settings=get_settings())
    finally:
        db.close()


async def mail_every_minute(_: dict[Any, Any], *args: Any, **kwargs: Any) -> int:
    db = SessionLocal()
    try:
        return deliver_pending_email(db, get_settings())
    finally:
        db.close()


async def expire_exchange_orders(_: dict[Any, Any], *args: Any, **kwargs: Any) -> int:
    db = SessionLocal()
    try:
        return expire_due_orders(db)
    finally:
        db.close()


async def expire_collaboration_windows(
    _: dict[Any, Any], *args: Any, **kwargs: Any
) -> dict[str, int]:
    db = SessionLocal()
    try:
        result = {
            "delegations": expire_delegations(db),
            "membership_pauses": expire_pauses(db),
        }
        db.commit()
        return result
    finally:
        db.close()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [
        due_every_minute,
        settle_hourly,
        economy_hourly,
        specialist_market_daily,
        specialist_payroll_hourly,
        ai_hourly,
        mail_every_minute,
        expire_exchange_orders,
        expire_collaboration_windows,
    ]
    cron_jobs = [
        cron(cast(WorkerCoroutine, due_every_minute), minute=None, second=0, unique=True),
        cron(cast(WorkerCoroutine, mail_every_minute), minute=None, second=10, unique=True),
        cron(cast(WorkerCoroutine, expire_exchange_orders), minute=None, second=15, unique=True),
        cron(
            cast(WorkerCoroutine, expire_collaboration_windows),
            minute=None,
            second=25,
            unique=True,
        ),
        cron(cast(WorkerCoroutine, settle_hourly), minute=0, second=20, unique=True),
        cron(cast(WorkerCoroutine, economy_hourly), minute=0, second=30, unique=True),
        cron(
            cast(WorkerCoroutine, specialist_market_daily),
            hour=0,
            minute=0,
            second=5,
            unique=True,
        ),
        cron(
            cast(WorkerCoroutine, specialist_payroll_hourly),
            minute=0,
            second=40,
            unique=True,
        ),
        cron(cast(WorkerCoroutine, ai_hourly), minute=0, second=50, unique=True),
    ]
    max_jobs = 8
    job_timeout = 300
    health_check_interval = 30
