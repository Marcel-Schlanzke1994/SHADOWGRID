"""Add Phase 10D district real estate, leases and improvements."""

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0015_real_estate"
down_revision = "0014_bonds"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "real_estate_district_indices",
    "real_estate_index_snapshots",
    "real_estate_properties",
    "property_transfers",
    "property_leases",
    "property_lease_payments",
    "property_improvements",
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
