"""Add Phase 11 scoped realtime event contracts and notification index."""

import sqlalchemy as sa
from alembic import op

revision = "0016_realtime_notifications"
down_revision = "0015_real_estate"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    def columns() -> set[str]:
        return {str(item["name"]) for item in sa.inspect(bind).get_columns("realtime_events")}

    existing_columns = columns()
    missing_columns = {
        "event_version",
        "audience_type",
        "audience_id",
        "dedupe_key",
    } - existing_columns
    if missing_columns:
        with op.batch_alter_table("realtime_events") as batch:
            if "event_version" in missing_columns:
                batch.add_column(
                    sa.Column(
                        "event_version",
                        sa.Integer(),
                        nullable=False,
                        server_default="1",
                    )
                )
            if "audience_type" in missing_columns:
                batch.add_column(
                    sa.Column(
                        "audience_type",
                        sa.String(length=16),
                        nullable=False,
                        server_default="world",
                    )
                )
            if "audience_id" in missing_columns:
                batch.add_column(sa.Column("audience_id", sa.String(length=36), nullable=True))
            if "dedupe_key" in missing_columns:
                batch.add_column(sa.Column("dedupe_key", sa.String(length=120), nullable=True))
    op.execute(
        sa.text(
            "UPDATE realtime_events "
            "SET audience_type = 'player', audience_id = profile_id "
            "WHERE profile_id IS NOT NULL"
        )
    )
    inspector = sa.inspect(bind)
    existing_indexes = {
        str(item["name"])
        for item in inspector.get_indexes("realtime_events")
        if item["name"] is not None
    }
    existing_uniques = {
        str(item["name"])
        for item in inspector.get_unique_constraints("realtime_events")
        if item["name"] is not None
    }
    existing_checks = {
        str(item["name"])
        for item in inspector.get_check_constraints("realtime_events")
        if item["name"] is not None
    }
    missing_index = "ix_realtime_audience_created" not in existing_indexes
    missing_unique = "uq_realtime_world_dedupe" not in existing_uniques
    missing_checks = {
        "ck_realtime_event_version",
        "ck_realtime_audience_type",
        "ck_realtime_audience_id",
    } - existing_checks
    if missing_index or missing_unique or missing_checks:
        with op.batch_alter_table("realtime_events") as batch:
            if missing_index:
                batch.create_index(
                    "ix_realtime_audience_created",
                    ["world_id", "audience_type", "audience_id", "created_at"],
                    unique=False,
                )
            if missing_unique:
                batch.create_unique_constraint(
                    "uq_realtime_world_dedupe",
                    ["world_id", "dedupe_key"],
                )
            if "ck_realtime_event_version" in missing_checks:
                batch.create_check_constraint(
                    "ck_realtime_event_version",
                    "event_version BETWEEN 1 AND 100",
                )
            if "ck_realtime_audience_type" in missing_checks:
                batch.create_check_constraint(
                    "ck_realtime_audience_type",
                    "audience_type IN ('world', 'player', 'cartel', 'city')",
                )
            if "ck_realtime_audience_id" in missing_checks:
                batch.create_check_constraint(
                    "ck_realtime_audience_id",
                    "(audience_type = 'world' AND audience_id IS NULL) OR "
                    "(audience_type != 'world' AND audience_id IS NOT NULL)",
                )
    notification_indexes = {
        str(item["name"])
        for item in sa.inspect(bind).get_indexes("notifications")
        if item["name"] is not None
    }
    if "ix_notification_user_read_created" not in notification_indexes:
        op.create_index(
            "ix_notification_user_read_created",
            "notifications",
            ["user_id", "read_at", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(
        "ix_notification_user_read_created",
        table_name="notifications",
    )
    with op.batch_alter_table("realtime_events") as batch:
        batch.drop_constraint(
            "ck_realtime_audience_id",
            type_="check",
        )
        batch.drop_constraint(
            "ck_realtime_audience_type",
            type_="check",
        )
        batch.drop_constraint(
            "ck_realtime_event_version",
            type_="check",
        )
        batch.drop_constraint(
            "uq_realtime_world_dedupe",
            type_="unique",
        )
        batch.drop_index("ix_realtime_audience_created")
        batch.drop_column("dedupe_key")
        batch.drop_column("audience_id")
        batch.drop_column("audience_type")
        batch.drop_column("event_version")
