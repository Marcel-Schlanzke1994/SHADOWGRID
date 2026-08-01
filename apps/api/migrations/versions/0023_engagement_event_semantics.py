"""Enforce one engagement event per profile and semantic source."""

import sqlalchemy as sa
from alembic import op

revision = "0023_engagement_event_semantics"
down_revision = "0022_engagement_ranking_history"
branch_labels = None
depends_on = None

CONSTRAINT_NAME = "uq_engagement_event_source"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraints = {
        str(item["name"])
        for item in inspector.get_unique_constraints("engagement_events")
        if item.get("name")
    }
    if CONSTRAINT_NAME in constraints:
        return
    duplicate = bind.execute(
        sa.text(
            "SELECT profile_id, event_type, source_type, source_id, COUNT(*) AS item_count "
            "FROM engagement_events "
            "GROUP BY profile_id, event_type, source_type, source_id "
            "HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate is not None:
        raise RuntimeError(
            "Duplicate semantic engagement events must be reviewed before migration 0023"
        )
    with op.batch_alter_table("engagement_events") as batch:
        batch.create_unique_constraint(
            CONSTRAINT_NAME,
            ["profile_id", "event_type", "source_type", "source_id"],
        )


def downgrade() -> None:
    constraints = {
        str(item["name"])
        for item in sa.inspect(op.get_bind()).get_unique_constraints("engagement_events")
        if item.get("name")
    }
    if CONSTRAINT_NAME in constraints:
        with op.batch_alter_table("engagement_events") as batch:
            batch.drop_constraint(CONSTRAINT_NAME, type_="unique")
