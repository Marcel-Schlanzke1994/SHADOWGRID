"""Run the database migration and idempotent production bootstrap in one process."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from shadowgrid.bootstrap import bootstrap

API_ROOT = Path(__file__).resolve().parents[1]


def run_predeploy() -> None:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "migrations"))
    command.upgrade(config, "head")
    bootstrap()


if __name__ == "__main__":
    run_predeploy()
