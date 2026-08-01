"""Add Phase 10C bond issuance, holdings and settlements."""

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0014_bonds"
down_revision = "0013_loans"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "bond_issues",
    "bond_subscriptions",
    "bond_holdings",
    "bond_ledger_entries",
    "bond_settlements",
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
