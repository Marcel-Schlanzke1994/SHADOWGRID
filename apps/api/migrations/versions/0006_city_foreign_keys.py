"""Align city foreign keys across PostgreSQL and SQLite."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine import Connection

revision = "0006_city_foreign_keys"
down_revision = "0005_specialists_ai"
branch_labels = None
depends_on = None

CITY_FOREIGN_KEYS = (
    ("player_profiles", "fk_0006_profile_city"),
    ("districts", "fk_0006_district_city"),
    ("organizations", "fk_0006_organization_city"),
)


def _foreign_key_names(bind: Connection, table_name: str) -> set[str]:
    return {
        str(item["name"])
        for item in sa.inspect(bind).get_foreign_keys(table_name)
        if item["name"] is not None
    }


def _has_city_foreign_key(bind: Connection, table_name: str) -> bool:
    return any(
        tuple(str(column) for column in item["constrained_columns"]) == ("city_id",)
        for item in sa.inspect(bind).get_foreign_keys(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = OFF")
    for table_name, constraint_name in CITY_FOREIGN_KEYS:
        if _has_city_foreign_key(bind, table_name):
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table_name, recreate="always") as batch:
                batch.create_foreign_key(
                    constraint_name,
                    "cities",
                    ["city_id"],
                    ["id"],
                )
        else:
            op.create_foreign_key(
                constraint_name,
                table_name,
                "cities",
                ["city_id"],
                ["id"],
            )
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = ON")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = OFF")
    for table_name, constraint_name in reversed(CITY_FOREIGN_KEYS):
        if constraint_name not in _foreign_key_names(bind, table_name):
            continue
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table(table_name, recreate="always") as batch:
                batch.drop_constraint(constraint_name, type_="foreignkey")
        else:
            op.drop_constraint(constraint_name, table_name, type_="foreignkey")
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = ON")
