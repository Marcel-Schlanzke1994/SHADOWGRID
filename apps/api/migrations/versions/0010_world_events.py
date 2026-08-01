"""Add Phase 8 versioned world-event definitions and concrete instances."""

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0010_world_events"
down_revision = "0009_intelligence_pvp"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "world_event_definitions",
    "world_event_instances",
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
