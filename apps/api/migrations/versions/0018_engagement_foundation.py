"""Add the voluntary engagement foundation and notification categories."""

import sqlalchemy as sa
from alembic import op

revision = "0018_engagement_foundation"
down_revision = "0017_release_hardening"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    engagement_tables = {
        "engagement_events",
        "goal_templates",
        "goal_choice_windows",
        "goal_instances",
        "goal_progress",
        "goal_rewards",
        "player_open_plans",
        "player_sessions",
        "session_summaries",
        "return_briefings",
        "notification_preferences",
        "engagement_settings",
        "engagement_guardrail_evaluations",
        "engagement_rollouts",
    }
    existing_engagement_tables = engagement_tables & tables
    if existing_engagement_tables and existing_engagement_tables != engagement_tables:
        raise RuntimeError("Engagement foundation schema is only partially present")
    if existing_engagement_tables == engagement_tables:
        notification_columns = {
            str(item["name"]) for item in sa.inspect(bind).get_columns("notifications")
        }
        if "category" not in notification_columns:
            with op.batch_alter_table("notifications") as batch:
                batch.add_column(
                    sa.Column(
                        "category",
                        sa.String(length=16),
                        nullable=False,
                        server_default="strategic",
                    )
                )
                batch.create_check_constraint(
                    "ck_notification_category",
                    "category IN ('critical', 'strategic', 'social', 'summary')",
                )
                batch.create_index("ix_notifications_category", ["category"], unique=False)
        return
    op.create_table(
        "engagement_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("world_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("source_type", sa.String(length=40), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "event_type IN ("
            "'company.founded', 'company.first_profit', 'specialist.assigned', "
            "'exchange.ipo_completed', 'cartel.project_contributed', "
            "'intelligence.report_acquired', 'world_event.responded', 'season.closed', "
            "'mentoring.system_understood', 'mentoring.independent_decision', "
            "'mentoring.positive_feedback')",
            name="ck_engagement_event_type",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("world_id", "idempotency_key", name="uq_engagement_event_key"),
    )
    op.create_index("ix_engagement_events_world_id", "engagement_events", ["world_id"])
    op.create_index("ix_engagement_events_profile_id", "engagement_events", ["profile_id"])
    op.create_index("ix_engagement_events_event_type", "engagement_events", ["event_type"])
    op.create_index(
        "ix_engagement_event_profile_occurred",
        "engagement_events",
        ["profile_id", "occurred_at"],
    )

    op.create_table(
        "goal_templates",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_key", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(length=24), nullable=False),
        sa.Column("title_key", sa.String(length=120), nullable=False),
        sa.Column("description_key", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("unit_key", sa.String(length=60), nullable=False),
        sa.Column("catch_up_weeks", sa.Integer(), nullable=False),
        sa.Column("doctrine_keys_json", sa.JSON(), nullable=False),
        sa.Column("reward_type", sa.String(length=24), nullable=False),
        sa.Column("reward_key", sa.String(length=80), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_goal_template_version"),
        sa.CheckConstraint(
            "category IN ('economic', 'social', 'exploration', 'risk', 'long_term', 'season')",
            name="ck_goal_template_category",
        ),
        sa.CheckConstraint("target_value > 0", name="ck_goal_template_target"),
        sa.CheckConstraint("catch_up_weeks BETWEEN 1 AND 8", name="ck_goal_template_catchup"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("template_key", "version", name="uq_goal_template_version"),
    )
    op.create_index("ix_goal_templates_template_key", "goal_templates", ["template_key"])
    op.create_index("ix_goal_templates_event_type", "goal_templates", ["event_type"])

    op.create_table(
        "goal_choice_windows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("catch_up_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("max_choices", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("ends_at > starts_at", name="ck_goal_window_duration"),
        sa.CheckConstraint("catch_up_until >= ends_at", name="ck_goal_window_catchup"),
        sa.CheckConstraint("max_choices BETWEEN 1 AND 3", name="ck_goal_window_choices"),
        sa.CheckConstraint(
            "status IN ('open', 'catch_up', 'closed')",
            name="ck_goal_window_status",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "starts_at", name="uq_goal_window_profile_start"),
    )
    op.create_index("ix_goal_choice_windows_profile_id", "goal_choice_windows", ["profile_id"])
    op.create_index(
        "ix_goal_window_profile_status",
        "goal_choice_windows",
        ["profile_id", "status", "starts_at"],
    )

    op.create_table(
        "goal_instances",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("template_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("choice_window_id", sa.String(length=36), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("progress_value", sa.Integer(), nullable=False),
        sa.Column("recommended_for_doctrine", sa.Boolean(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("swapped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('offered', 'active', 'completed', 'swapped', 'declined', 'expired')",
            name="ck_goal_instance_status",
        ),
        sa.CheckConstraint(
            "target_value > 0 AND progress_value >= 0 AND progress_value <= target_value",
            name="ck_goal_instance_progress",
        ),
        sa.ForeignKeyConstraint(
            ["choice_window_id"], ["goal_choice_windows.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["goal_templates.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "idempotency_key", name="uq_goal_instance_profile_key"),
        sa.UniqueConstraint("choice_window_id", "template_id", name="uq_goal_window_template"),
    )
    op.create_index("ix_goal_instances_template_id", "goal_instances", ["template_id"])
    op.create_index("ix_goal_instances_profile_id", "goal_instances", ["profile_id"])
    op.create_index("ix_goal_instances_choice_window_id", "goal_instances", ["choice_window_id"])
    op.create_index(
        "ix_goal_instance_profile_status",
        "goal_instances",
        ["profile_id", "status", "created_at"],
    )

    op.create_table(
        "goal_progress",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("goal_instance_id", sa.String(length=36), nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("delta_value", sa.Integer(), nullable=False),
        sa.Column("progress_after", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("delta_value > 0", name="ck_goal_progress_delta"),
        sa.CheckConstraint("progress_after > 0", name="ck_goal_progress_after"),
        sa.ForeignKeyConstraint(["event_id"], ["engagement_events.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["goal_instance_id"], ["goal_instances.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_instance_id", "event_id", name="uq_goal_progress_event"),
    )
    op.create_index("ix_goal_progress_goal_instance_id", "goal_progress", ["goal_instance_id"])
    op.create_index("ix_goal_progress_event_id", "goal_progress", ["event_id"])

    op.create_table(
        "goal_rewards",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("goal_instance_id", sa.String(length=36), nullable=False),
        sa.Column("reward_type", sa.String(length=24), nullable=False),
        sa.Column("reward_key", sa.String(length=80), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("awarded_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "reward_type IN ('knowledge', 'chronicle', 'mastery', 'cosmetic')",
            name="ck_goal_reward_type",
        ),
        sa.ForeignKeyConstraint(["goal_instance_id"], ["goal_instances.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("goal_instance_id", "reward_key", name="uq_goal_reward_key"),
    )
    op.create_index("ix_goal_rewards_goal_instance_id", "goal_rewards", ["goal_instance_id"])

    op.create_table(
        "player_open_plans",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("next_step", sa.String(length=280), nullable=False),
        sa.Column("target_path", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "category IN ('urgent', 'strategic', 'discoverable')",
            name="ck_open_plan_category",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'archived')",
            name="ck_open_plan_status",
        ),
        sa.CheckConstraint("priority BETWEEN 0 AND 100", name="ck_open_plan_priority"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "idempotency_key", name="uq_open_plan_profile_key"),
    )
    op.create_index("ix_player_open_plans_profile_id", "player_open_plans", ["profile_id"])
    op.create_index(
        "ix_open_plan_profile_status",
        "player_open_plans",
        ["profile_id", "status", "priority"],
    )

    op.create_table(
        "player_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("client_session_key", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("initial_snapshot_json", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'abandoned')",
            name="ck_player_session_status",
        ),
        sa.CheckConstraint(
            "ended_at IS NULL OR ended_at >= started_at",
            name="ck_player_session_duration",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "client_session_key", name="uq_player_session_key"),
    )
    op.create_index("ix_player_sessions_profile_id", "player_sessions", ["profile_id"])
    op.create_index(
        "ix_player_session_profile_started",
        "player_sessions",
        ["profile_id", "started_at"],
    )

    op.create_table(
        "session_summaries",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=False),
        sa.Column("decisions_json", sa.JSON(), nullable=False),
        sa.Column("changes_json", sa.JSON(), nullable=False),
        sa.Column("open_plans_json", sa.JSON(), nullable=False),
        sa.Column("next_entry_points_json", sa.JSON(), nullable=False),
        sa.Column("natural_break_reached", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("duration_seconds >= 0", name="ck_session_summary_duration"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["session_id"], ["player_sessions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", name="uq_session_summary_session"),
    )
    op.create_index("ix_session_summaries_session_id", "session_summaries", ["session_id"])
    op.create_index("ix_session_summaries_profile_id", "session_summaries", ["profile_id"])

    op.create_table(
        "return_briefings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("since_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("world_changes_json", sa.JSON(), nullable=False),
        sa.Column("company_changes_json", sa.JSON(), nullable=False),
        sa.Column("relevant_decisions_json", sa.JSON(), nullable=False),
        sa.Column("available_content_json", sa.JSON(), nullable=False),
        sa.Column("entry_points_json", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "since_at", name="uq_return_briefing_since"),
    )
    op.create_index("ix_return_briefings_profile_id", "return_briefings", ["profile_id"])
    op.create_index(
        "ix_return_briefing_profile_generated",
        "return_briefings",
        ["profile_id", "generated_at"],
    )

    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("live_enabled", sa.Boolean(), nullable=False),
        sa.Column("digest_frequency", sa.String(length=16), nullable=False),
        sa.Column("quiet_start_minute", sa.Integer(), nullable=False),
        sa.Column("quiet_end_minute", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "category IN ('critical', 'strategic', 'social', 'summary')",
            name="ck_notification_preference_category",
        ),
        sa.CheckConstraint(
            "digest_frequency IN ('immediate', 'daily', 'weekly', 'off')",
            name="ck_notification_preference_digest",
        ),
        sa.CheckConstraint(
            "quiet_start_minute BETWEEN 0 AND 1439 AND quiet_end_minute BETWEEN 0 AND 1439",
            name="ck_notification_preference_quiet_hours",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "category", name="uq_notification_preference_category"),
    )
    op.create_index(
        "ix_notification_preferences_profile_id", "notification_preferences", ["profile_id"]
    )

    op.create_table(
        "engagement_settings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("adaptive_help_enabled", sa.Boolean(), nullable=False),
        sa.Column("session_summary_enabled", sa.Boolean(), nullable=False),
        sa.Column("ranking_visible", sa.Boolean(), nullable=False),
        sa.Column("information_density", sa.String(length=16), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "information_density IN ('compact', 'standard', 'detailed')",
            name="ck_engagement_setting_density",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", name="uq_engagement_setting_profile"),
    )
    op.create_index("ix_engagement_settings_profile_id", "engagement_settings", ["profile_id"])

    op.create_table(
        "engagement_guardrail_evaluations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("world_id", sa.String(length=36), nullable=True),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("strategy_spread_bps", sa.Integer(), nullable=False),
        sa.Column("cartel_dominance_bps", sa.Integer(), nullable=False),
        sa.Column("newcomer_wealth_bps", sa.Integer(), nullable=False),
        sa.Column("ledger_imbalance_cents", sa.BigInteger(), nullable=False),
        sa.Column("negative_balance_count", sa.Integer(), nullable=False),
        sa.Column("wellbeing_status", sa.String(length=24), nullable=False),
        sa.Column("wellbeing_signals_json", sa.JSON(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("reasons_json", sa.JSON(), nullable=False),
        sa.Column("evaluated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("strategy_spread_bps >= 0", name="ck_guardrail_strategy_spread"),
        sa.CheckConstraint("cartel_dominance_bps >= 0", name="ck_guardrail_cartel_dominance"),
        sa.CheckConstraint("newcomer_wealth_bps >= 0", name="ck_guardrail_newcomer_wealth"),
        sa.CheckConstraint("negative_balance_count >= 0", name="ck_guardrail_negative_balances"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_engagement_guardrail_key"),
    )
    op.create_index(
        "ix_engagement_guardrail_evaluations_world_id",
        "engagement_guardrail_evaluations",
        ["world_id"],
    )

    op.create_table(
        "engagement_rollouts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("feature_key", sa.String(length=80), nullable=False),
        sa.Column("cohort_bps", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("last_evaluation_id", sa.String(length=36), nullable=True),
        sa.Column("updated_by_user_id", sa.String(length=36), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("cohort_bps BETWEEN 0 AND 10000", name="ck_rollout_cohort"),
        sa.CheckConstraint(
            "status IN ('disabled', 'internal', 'staged', 'active', 'paused')",
            name="ck_rollout_status",
        ),
        sa.ForeignKeyConstraint(
            ["last_evaluation_id"], ["engagement_guardrail_evaluations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["updated_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("feature_key", name="uq_engagement_rollout_feature"),
    )

    notification_columns = {
        str(item["name"]) for item in sa.inspect(bind).get_columns("notifications")
    }
    if "category" not in notification_columns:
        with op.batch_alter_table("notifications") as batch:
            batch.add_column(
                sa.Column(
                    "category",
                    sa.String(length=16),
                    nullable=False,
                    server_default="strategic",
                )
            )
            batch.create_check_constraint(
                "ck_notification_category",
                "category IN ('critical', 'strategic', 'social', 'summary')",
            )
            batch.create_index("ix_notifications_category", ["category"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_index("ix_notifications_category")
        batch.drop_constraint("ck_notification_category", type_="check")
        batch.drop_column("category")
    op.drop_table("engagement_rollouts")
    op.drop_index(
        "ix_engagement_guardrail_evaluations_world_id",
        table_name="engagement_guardrail_evaluations",
    )
    op.drop_table("engagement_guardrail_evaluations")
    op.drop_index("ix_engagement_settings_profile_id", table_name="engagement_settings")
    op.drop_table("engagement_settings")
    op.drop_index("ix_notification_preferences_profile_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")
    op.drop_index("ix_return_briefing_profile_generated", table_name="return_briefings")
    op.drop_index("ix_return_briefings_profile_id", table_name="return_briefings")
    op.drop_table("return_briefings")
    op.drop_index("ix_session_summaries_profile_id", table_name="session_summaries")
    op.drop_index("ix_session_summaries_session_id", table_name="session_summaries")
    op.drop_table("session_summaries")
    op.drop_index("ix_player_session_profile_started", table_name="player_sessions")
    op.drop_index("ix_player_sessions_profile_id", table_name="player_sessions")
    op.drop_table("player_sessions")
    op.drop_index("ix_open_plan_profile_status", table_name="player_open_plans")
    op.drop_index("ix_player_open_plans_profile_id", table_name="player_open_plans")
    op.drop_table("player_open_plans")
    op.drop_index("ix_goal_rewards_goal_instance_id", table_name="goal_rewards")
    op.drop_table("goal_rewards")
    op.drop_index("ix_goal_progress_event_id", table_name="goal_progress")
    op.drop_index("ix_goal_progress_goal_instance_id", table_name="goal_progress")
    op.drop_table("goal_progress")
    op.drop_index("ix_goal_instance_profile_status", table_name="goal_instances")
    op.drop_index("ix_goal_instances_choice_window_id", table_name="goal_instances")
    op.drop_index("ix_goal_instances_profile_id", table_name="goal_instances")
    op.drop_index("ix_goal_instances_template_id", table_name="goal_instances")
    op.drop_table("goal_instances")
    op.drop_index("ix_goal_window_profile_status", table_name="goal_choice_windows")
    op.drop_index("ix_goal_choice_windows_profile_id", table_name="goal_choice_windows")
    op.drop_table("goal_choice_windows")
    op.drop_index("ix_goal_templates_event_type", table_name="goal_templates")
    op.drop_index("ix_goal_templates_template_key", table_name="goal_templates")
    op.drop_table("goal_templates")
    op.drop_index("ix_engagement_event_profile_occurred", table_name="engagement_events")
    op.drop_index("ix_engagement_events_event_type", table_name="engagement_events")
    op.drop_index("ix_engagement_events_profile_id", table_name="engagement_events")
    op.drop_index("ix_engagement_events_world_id", table_name="engagement_events")
    op.drop_table("engagement_events")
