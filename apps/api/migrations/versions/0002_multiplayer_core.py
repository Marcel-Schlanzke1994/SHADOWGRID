"""Add the persistent multiplayer, PvP, territory, war, alliance and chat core."""

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0002_multiplayer_core"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "cities",
    "city_markets",
    "pvp_operations",
    "pvp_operation_participants",
    "pvp_defense_actions",
    "pvp_reports",
    "pvp_cooldowns",
    "pvp_protection_states",
    "pvp_reputation",
    "cartel_wars",
    "cartel_war_participants",
    "cartel_war_objectives",
    "cartel_war_operations",
    "cartel_war_scores",
    "cartel_war_events",
    "cartel_war_treaties",
    "territory_claims",
    "territory_control_points",
    "territory_contributions",
    "territory_history",
    "alliances",
    "alliance_memberships",
    "alliance_roles",
    "alliance_treaties",
    "player_messages",
    "chat_channels",
    "chat_memberships",
    "chat_messages",
    "user_blocks",
    "moderation_reports",
    "market_offers",
    "market_trades",
    "realtime_events",
    "anti_cheat_risk_events",
)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    tables = [Base.metadata.tables[name] for name in NEW_TABLES if name not in existing_tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)

    def columns(table_name: str) -> set[str]:
        return {str(item["name"]) for item in sa.inspect(bind).get_columns(table_name)}

    def indexes(table_name: str) -> set[str]:
        return {
            str(item["name"])
            for item in sa.inspect(bind).get_indexes(table_name)
            if item["name"] is not None
        }

    if "city_id" not in columns("player_profiles"):
        op.add_column("player_profiles", sa.Column("city_id", sa.String(length=36), nullable=True))
    if "recovery_until" not in columns("player_profiles"):
        op.add_column(
            "player_profiles",
            sa.Column("recovery_until", sa.DateTime(timezone=True), nullable=True),
        )
    if "ix_player_profiles_city_id" not in indexes("player_profiles"):
        op.create_index("ix_player_profiles_city_id", "player_profiles", ["city_id"])

    if "city_id" not in columns("districts"):
        op.add_column("districts", sa.Column("city_id", sa.String(length=36), nullable=True))
    if "ix_districts_city_id" not in indexes("districts"):
        op.create_index("ix_districts_city_id", "districts", ["city_id"])

    organization_columns = columns("organizations")
    if "city_id" not in organization_columns:
        op.add_column("organizations", sa.Column("city_id", sa.String(length=36), nullable=True))
    if "governance_model" not in organization_columns:
        op.add_column(
            "organizations",
            sa.Column(
                "governance_model",
                sa.String(length=32),
                nullable=False,
                server_default="autocratic",
            ),
        )
    if "reputation" not in organization_columns:
        op.add_column(
            "organizations",
            sa.Column("reputation", sa.Integer(), nullable=False, server_default="50"),
        )
    if "investigation_pressure" not in organization_columns:
        op.add_column(
            "organizations",
            sa.Column("investigation_pressure", sa.Integer(), nullable=False, server_default="0"),
        )
    if "version" not in organization_columns:
        op.add_column(
            "organizations", sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )
    if "ix_organizations_city_id" not in indexes("organizations"):
        op.create_index("ix_organizations_city_id", "organizations", ["city_id"])

    # SQLite cannot add a foreign key to an existing table without rebuilding it.
    # The ORM and PostgreSQL production schema still enforce these relationships;
    # local SQLite keeps indexes and application-level validation.
    if bind.dialect.name != "sqlite":
        foreign_keys = {
            table_name: {
                tuple(str(column) for column in item["constrained_columns"])
                for item in sa.inspect(bind).get_foreign_keys(table_name)
            }
            for table_name in ("player_profiles", "districts", "organizations")
        }
        if ("city_id",) not in foreign_keys["player_profiles"]:
            op.create_foreign_key(
                "fk_profile_city", "player_profiles", "cities", ["city_id"], ["id"]
            )
        if ("city_id",) not in foreign_keys["districts"]:
            op.create_foreign_key("fk_district_city", "districts", "cities", ["city_id"], ["id"])
        if ("city_id",) not in foreign_keys["organizations"]:
            op.create_foreign_key(
                "fk_organization_city", "organizations", "cities", ["city_id"], ["id"]
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("organizations", recreate="always") as batch:
            batch.drop_index("ix_organizations_city_id")
            batch.drop_column("version")
            batch.drop_column("investigation_pressure")
            batch.drop_column("reputation")
            batch.drop_column("governance_model")
            batch.drop_column("city_id")
        with op.batch_alter_table("districts", recreate="always") as batch:
            batch.drop_index("ix_districts_city_id")
            batch.drop_column("city_id")
        with op.batch_alter_table("player_profiles", recreate="always") as batch:
            batch.drop_index("ix_player_profiles_city_id")
            batch.drop_column("recovery_until")
            batch.drop_column("city_id")
    else:
        op.drop_constraint("fk_organization_city", "organizations", type_="foreignkey")
        op.drop_constraint("fk_district_city", "districts", type_="foreignkey")
        op.drop_constraint("fk_profile_city", "player_profiles", type_="foreignkey")
        op.drop_index("ix_organizations_city_id", table_name="organizations")
        op.drop_column("organizations", "version")
        op.drop_column("organizations", "investigation_pressure")
        op.drop_column("organizations", "reputation")
        op.drop_column("organizations", "governance_model")
        op.drop_column("organizations", "city_id")
        op.drop_index("ix_districts_city_id", table_name="districts")
        op.drop_column("districts", "city_id")
        op.drop_index("ix_player_profiles_city_id", table_name="player_profiles")
        op.drop_column("player_profiles", "recovery_until")
        op.drop_column("player_profiles", "city_id")

    tables = [Base.metadata.tables[name] for name in NEW_TABLES]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)
