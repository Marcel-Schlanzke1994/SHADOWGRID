"""Add narrative information access and persistent ranking bests."""

import sqlalchemy as sa
from alembic import op

revision = "0022_engagement_ranking_history"
down_revision = "0021_engagement_validation_metrics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    relationship_columns = {
        str(item["name"]) for item in inspector.get_columns("player_actor_relationships")
    }
    ranking_exists = "player_ranking_bests" in tables
    access_exists = "information_access" in relationship_columns
    if ranking_exists and access_exists:
        return
    if ranking_exists or access_exists:
        raise RuntimeError("Engagement ranking-history schema is only partially present")

    with op.batch_alter_table("player_actor_relationships") as batch:
        batch.add_column(
            sa.Column(
                "information_access",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch.create_check_constraint(
            "ck_actor_relationship_information_access",
            "information_access BETWEEN 0 AND 100",
        )

    op.create_table(
        "player_ranking_bests",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column("best_score", sa.BigInteger(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("best_score >= 0", name="ck_player_ranking_best_score"),
        sa.CheckConstraint(
            "category IN ('company_value', 'sustainable_profit', 'innovation', "
            "'contract_reliability', 'portfolio_return', 'district_development', "
            "'cartel_influence', 'intelligence_success', 'diplomatic_stability', "
            "'comeback_performance', 'mentoring', 'season_goals')",
            name="ck_player_ranking_best_category",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "category", name="uq_player_ranking_best"),
    )
    op.create_index(
        "ix_player_ranking_bests_profile_id",
        "player_ranking_bests",
        ["profile_id"],
    )
    op.create_index(
        "ix_player_ranking_bests_category",
        "player_ranking_bests",
        ["category"],
    )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "player_ranking_bests" in tables:
        op.drop_index(
            "ix_player_ranking_bests_category",
            table_name="player_ranking_bests",
        )
        op.drop_index(
            "ix_player_ranking_bests_profile_id",
            table_name="player_ranking_bests",
        )
        op.drop_table("player_ranking_bests")
    columns = {
        str(item["name"])
        for item in sa.inspect(op.get_bind()).get_columns("player_actor_relationships")
    }
    if "information_access" in columns:
        with op.batch_alter_table("player_actor_relationships") as batch:
            batch.drop_constraint(
                "ck_actor_relationship_information_access",
                type_="check",
            )
            batch.drop_column("information_access")
