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

from shadowgrid.config import get_settings  # noqa: E402
from shadowgrid.database import SessionLocal  # noqa: E402
from shadowgrid.domain import resolve_due, settle_businesses  # noqa: E402
from shadowgrid.mailer import deliver_pending_email  # noqa: E402


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


async def mail_every_minute(_: dict[Any, Any], *args: Any, **kwargs: Any) -> int:
    db = SessionLocal()
    try:
        return deliver_pending_email(db, get_settings())
    finally:
        db.close()


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
    functions = [due_every_minute, settle_hourly, mail_every_minute]
    cron_jobs = [
        cron(cast(WorkerCoroutine, due_every_minute), minute=None, second=0, unique=True),
        cron(cast(WorkerCoroutine, mail_every_minute), minute=None, second=10, unique=True),
        cron(cast(WorkerCoroutine, settle_hourly), minute=0, second=20, unique=True),
    ]
    max_jobs = 8
    job_timeout = 300
    health_check_interval = 30
