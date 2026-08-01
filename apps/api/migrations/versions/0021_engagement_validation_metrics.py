"""Add privacy-safe engagement metrics and complete rollout evidence."""

import sqlalchemy as sa
from alembic import op

revision = "0021_engagement_validation_metrics"
down_revision = "0020_engagement_narrative_legacy"
branch_labels = None
depends_on = None

STATUS_COLUMNS = {
    "technical_status",
    "accessibility_status",
    "voluntary_return_status",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    guardrail_columns = {
        str(item["name"]) for item in inspector.get_columns("engagement_guardrail_evaluations")
    }
    metric_exists = "engagement_metrics_daily" in tables
    status_exists = STATUS_COLUMNS & guardrail_columns
    if metric_exists and status_exists == STATUS_COLUMNS:
        return
    if metric_exists or status_exists:
        raise RuntimeError("Engagement validation schema is only partially present")

    with op.batch_alter_table("engagement_guardrail_evaluations") as batch:
        for column_name in sorted(STATUS_COLUMNS):
            batch.add_column(
                sa.Column(
                    column_name,
                    sa.String(24),
                    nullable=False,
                    server_default="insufficient_data",
                )
            )

    op.create_table(
        "engagement_metrics_daily",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(36), nullable=True),
        sa.Column("scope_key", sa.String(40), nullable=False),
        sa.Column("metric_date", sa.Date(), nullable=False),
        sa.Column("cohort_key", sa.String(40), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("profile_count", sa.Integer(), nullable=False),
        sa.Column("active_profile_count", sa.Integer(), nullable=False),
        sa.Column("d1_return_bps", sa.Integer(), nullable=False),
        sa.Column("d7_return_bps", sa.Integer(), nullable=False),
        sa.Column("d30_return_bps", sa.Integer(), nullable=False),
        sa.Column("weekly_return_bps", sa.Integer(), nullable=False),
        sa.Column("goal_completion_bps", sa.Integer(), nullable=False),
        sa.Column("meaningful_decision_count", sa.Integer(), nullable=False),
        sa.Column("strategy_diversity_bps", sa.Integer(), nullable=False),
        sa.Column("season_participation_bps", sa.Integer(), nullable=False),
        sa.Column("socially_engaged_bps", sa.Integer(), nullable=False),
        sa.Column("pause_return_7_bps", sa.Integer(), nullable=False),
        sa.Column("pause_return_14_bps", sa.Integer(), nullable=False),
        sa.Column("pause_return_30_bps", sa.Integer(), nullable=False),
        sa.Column("satisfaction_bps", sa.Integer(), nullable=True),
        sa.Column("fairness_bps", sa.Integer(), nullable=True),
        sa.Column("survey_response_count", sa.Integer(), nullable=False),
        sa.Column("natural_break_bps", sa.Integer(), nullable=False),
        sa.Column("story_progress_count", sa.Integer(), nullable=False),
        sa.Column("collection_completion_bps", sa.Integer(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("profile_count >= 0", name="ck_engagement_metric_profiles"),
        sa.CheckConstraint(
            "active_profile_count >= 0", name="ck_engagement_metric_active_profiles"
        ),
        sa.CheckConstraint("meaningful_decision_count >= 0", name="ck_engagement_metric_decisions"),
        sa.CheckConstraint("story_progress_count >= 0", name="ck_engagement_metric_story"),
        sa.CheckConstraint(
            "d1_return_bps BETWEEN 0 AND 10000 AND d7_return_bps BETWEEN 0 AND 10000 "
            "AND d30_return_bps BETWEEN 0 AND 10000 "
            "AND weekly_return_bps BETWEEN 0 AND 10000",
            name="ck_engagement_metric_return_bps",
        ),
        sa.CheckConstraint(
            "goal_completion_bps BETWEEN 0 AND 10000 "
            "AND strategy_diversity_bps BETWEEN 0 AND 10000 "
            "AND season_participation_bps BETWEEN 0 AND 10000 "
            "AND socially_engaged_bps BETWEEN 0 AND 10000",
            name="ck_engagement_metric_engagement_bps",
        ),
        sa.CheckConstraint(
            "pause_return_7_bps BETWEEN 0 AND 10000 "
            "AND pause_return_14_bps BETWEEN 0 AND 10000 "
            "AND pause_return_30_bps BETWEEN 0 AND 10000",
            name="ck_engagement_metric_pause_return_bps",
        ),
        sa.CheckConstraint(
            "natural_break_bps BETWEEN 0 AND 10000 "
            "AND collection_completion_bps BETWEEN 0 AND 10000",
            name="ck_engagement_metric_quality_bps",
        ),
        sa.CheckConstraint(
            "satisfaction_bps IS NULL OR satisfaction_bps BETWEEN 0 AND 10000",
            name="ck_engagement_metric_satisfaction",
        ),
        sa.CheckConstraint(
            "fairness_bps IS NULL OR fairness_bps BETWEEN 0 AND 10000",
            name="ck_engagement_metric_fairness",
        ),
        sa.CheckConstraint("survey_response_count >= 0", name="ck_engagement_metric_surveys"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_key", "metric_date", "cohort_key", name="uq_engagement_metric_day"
        ),
        sa.UniqueConstraint("idempotency_key", name="uq_engagement_metric_key"),
    )
    op.create_index(
        "ix_engagement_metrics_daily_world_id",
        "engagement_metrics_daily",
        ["world_id"],
    )
    op.create_index(
        "ix_engagement_metrics_daily_scope_key",
        "engagement_metrics_daily",
        ["scope_key"],
    )
    op.create_index(
        "ix_engagement_metrics_daily_metric_date",
        "engagement_metrics_daily",
        ["metric_date"],
    )


def downgrade() -> None:
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "engagement_metrics_daily" in tables:
        op.drop_index(
            "ix_engagement_metrics_daily_metric_date",
            table_name="engagement_metrics_daily",
        )
        op.drop_index(
            "ix_engagement_metrics_daily_scope_key",
            table_name="engagement_metrics_daily",
        )
        op.drop_index(
            "ix_engagement_metrics_daily_world_id",
            table_name="engagement_metrics_daily",
        )
        op.drop_table("engagement_metrics_daily")
    guardrail_columns = {
        str(item["name"])
        for item in sa.inspect(op.get_bind()).get_columns("engagement_guardrail_evaluations")
    }
    existing = STATUS_COLUMNS & guardrail_columns
    if existing:
        with op.batch_alter_table("engagement_guardrail_evaluations") as batch:
            for column_name in sorted(existing):
                batch.drop_column(column_name)
