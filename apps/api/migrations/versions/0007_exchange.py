"""Add Phase 5 exchange listings, reservations, orders, trades and dividends."""

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0007_exchange"
down_revision = "0006_city_foreign_keys"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "exchange_listings",
    "share_classes",
    "share_holdings",
    "exchange_orders",
    "exchange_trades",
    "share_ledger_entries",
    "price_snapshots",
    "dividend_declarations",
    "dividend_entitlements",
)


def upgrade() -> None:
    bind = op.get_bind()
    account_columns = {str(item["name"]) for item in sa.inspect(bind).get_columns("accounts")}
    if "reserved_cents" not in account_columns:
        op.add_column(
            "accounts",
            sa.Column(
                "reserved_cents",
                sa.BigInteger(),
                nullable=False,
                server_default="0",
            ),
        )

    account_checks = {
        str(item["name"])
        for item in sa.inspect(bind).get_check_constraints("accounts")
        if item["name"] is not None
    }
    if "ck_account_reservation" not in account_checks:
        condition = (
            "reserved_cents >= 0 AND "
            "((owner_type = 'system' AND reserved_cents = 0) OR "
            "reserved_cents <= balance_cents)"
        )
        if bind.dialect.name == "sqlite":
            with op.get_context().autocommit_block():
                op.execute("PRAGMA foreign_keys = OFF")
            with op.batch_alter_table("accounts", recreate="always") as batch:
                batch.create_check_constraint("ck_account_reservation", condition)
            with op.get_context().autocommit_block():
                op.execute("PRAGMA foreign_keys = ON")
        else:
            op.create_check_constraint(
                "ck_account_reservation",
                "accounts",
                condition,
            )

    existing_tables = set(sa.inspect(bind).get_table_names())
    tables = [Base.metadata.tables[name] for name in NEW_TABLES if name not in existing_tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    tables = [Base.metadata.tables[name] for name in NEW_TABLES]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)

    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = OFF")
        with op.batch_alter_table("accounts", recreate="always") as batch:
            batch.drop_constraint("ck_account_reservation", type_="check")
            batch.drop_column("reserved_cents")
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = ON")
    else:
        op.drop_constraint("ck_account_reservation", "accounts", type_="check")
        op.drop_column("accounts", "reserved_cents")
