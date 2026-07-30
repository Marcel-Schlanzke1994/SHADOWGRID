"""Add deterministic city-sector economy ticks and immutable reports."""

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0004_economy_ticks"
down_revision = "0003_company_finance"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "city_sector_markets",
    "economy_ticks",
    "market_economy_reports",
    "company_economy_reports",
)


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    tables = [Base.metadata.tables[name] for name in NEW_TABLES if name not in existing_tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in NEW_TABLES]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
