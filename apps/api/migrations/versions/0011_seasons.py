"""Add Phase 9 seasons, immutable scoring, rewards and archival snapshots."""

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0011_seasons"
down_revision = "0010_world_events"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "season_templates",
    "seasons",
    "season_score_snapshots",
    "hall_of_fame_entries",
    "account_rewards",
    "season_archive_snapshots",
)


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    tables = [Base.metadata.tables[name] for name in NEW_TABLES if name not in existing_tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(
        bind=bind,
        tables=[Base.metadata.tables[name] for name in reversed(NEW_TABLES)],
        checkfirst=True,
    )
