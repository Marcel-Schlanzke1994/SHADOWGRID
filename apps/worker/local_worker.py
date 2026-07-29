from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from time import monotonic

from .worker import (
    ai_hourly,
    due_every_minute,
    economy_hourly,
    expire_exchange_orders,
    mail_every_minute,
    settle_hourly,
    specialist_market_daily,
    specialist_payroll_hourly,
)


async def run_cycle() -> dict[str, object]:
    """Run every idempotent due-job adapter once for the zero-dependency local mode."""

    context: dict[object, object] = {}
    return {
        "due": await due_every_minute(context),
        "legacy_settlement": await settle_hourly(context),
        "economy": await economy_hourly(context),
        "specialist_market": await specialist_market_daily(context),
        "specialist_payroll": await specialist_payroll_hourly(context),
        "ai": await ai_hourly(context),
        "mail": await mail_every_minute(context),
        "expired_orders": await expire_exchange_orders(context),
    }


async def run_forever(interval_seconds: int = 60) -> None:
    if interval_seconds < 1:
        raise ValueError("interval_seconds must be positive")
    while True:
        started = monotonic()
        result = await run_cycle()
        print(
            json.dumps(
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "jobs": result,
                },
                sort_keys=True,
            ),
            flush=True,
        )
        elapsed = monotonic() - started
        await asyncio.sleep(max(1.0, interval_seconds - elapsed))


def main() -> None:
    try:
        asyncio.run(run_forever())
    except KeyboardInterrupt:
        print("Local worker stopped.", flush=True)


if __name__ == "__main__":
    main()
