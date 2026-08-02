"""Add engagement competence, mentoring and asynchronous cartel collaboration."""

import sqlalchemy as sa
from alembic import op

revision = "0019_engagement_competence_social"
down_revision = "0018_engagement_foundation"
branch_labels = None
depends_on = None

TABLES = {
    "doctrine_selections",
    "player_doctrines",
    "mastery_entries",
    "mastery_progress",
    "outcome_reports",
    "adaptive_help_offers",
    "personal_success_chains",
    "mentorships",
    "mentoring_milestones",
    "cartel_delegations",
    "cartel_membership_pauses",
    "cartel_chronicle_entries",
}


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Alembic creates version_num as VARCHAR(32), but engagement revision IDs
        # intentionally carry descriptive names longer than that. Widen the
        # bookkeeping column before Alembic records this revision.
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=32),
            type_=sa.String(length=128),
            existing_nullable=False,
        )

    tables = set(sa.inspect(bind).get_table_names())
    existing = TABLES & tables
    if existing and existing != TABLES:
        raise RuntimeError("Engagement competence/social schema is only partially present")
    if existing == TABLES:
        return

    doctrine_check = (
        "doctrine_key IN ('industrial_captain', 'financial_architect', 'innovator', "
        "'real_estate_strategist', 'networker', 'information_strategist', 'opportunist')"
    )
    mastery_check = (
        "area_key IN ('company_management', 'market_analysis', 'capital_markets', "
        "'contract_management', 'people_leadership', 'real_estate', 'cartel_leadership', "
        "'diplomacy', 'intelligence', 'risk_management', 'season_strategy')"
    )
    op.create_table(
        "doctrine_selections",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("doctrine_key", sa.String(40), nullable=False),
        sa.Column("previous_doctrine_key", sa.String(40), nullable=True),
        sa.Column("reason", sa.String(160), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(doctrine_check, name="ck_doctrine_selection_key"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "idempotency_key", name="uq_doctrine_selection_key"),
    )
    op.create_index("ix_doctrine_selections_profile_id", "doctrine_selections", ["profile_id"])
    op.create_index("ix_doctrine_selections_doctrine_key", "doctrine_selections", ["doctrine_key"])

    op.create_table(
        "player_doctrines",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("doctrine_key", sa.String(40), nullable=False),
        sa.Column("selection_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(doctrine_check, name="ck_player_doctrine_key"),
        sa.CheckConstraint("version > 0", name="ck_player_doctrine_version"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["selection_id"], ["doctrine_selections.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", name="uq_player_doctrine_profile"),
        sa.UniqueConstraint("selection_id"),
    )
    op.create_index("ix_player_doctrines_profile_id", "player_doctrines", ["profile_id"])

    op.create_table(
        "mastery_entries",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("area_key", sa.String(40), nullable=False),
        sa.Column("decision_key", sa.String(80), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("base_points", sa.Integer(), nullable=False),
        sa.Column("diversity_bps", sa.Integer(), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(mastery_check, name="ck_mastery_entry_area"),
        sa.CheckConstraint("points > 0 AND points <= 100", name="ck_mastery_entry_points"),
        sa.CheckConstraint(
            "diversity_bps BETWEEN 1000 AND 10000", name="ck_mastery_entry_diversity"
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "area_key", "source_type", "source_id", name="uq_mastery_source"
        ),
    )
    op.create_index("ix_mastery_entries_profile_id", "mastery_entries", ["profile_id"])
    op.create_index("ix_mastery_entries_area_key", "mastery_entries", ["area_key"])
    op.create_index(
        "ix_mastery_entry_profile_created", "mastery_entries", ["profile_id", "created_at"]
    )

    op.create_table(
        "mastery_progress",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("area_key", sa.String(40), nullable=False),
        sa.Column("points", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("distinct_decisions_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(mastery_check, name="ck_mastery_progress_area"),
        sa.CheckConstraint("points >= 0", name="ck_mastery_progress_points"),
        sa.CheckConstraint("level BETWEEN 0 AND 10", name="ck_mastery_progress_level"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "area_key", name="uq_mastery_progress_area"),
    )
    op.create_index("ix_mastery_progress_profile_id", "mastery_progress", ["profile_id"])

    op.create_table(
        "outcome_reports",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("title_key", sa.String(120), nullable=False),
        sa.Column("controllable_factors_json", sa.JSON(), nullable=False),
        sa.Column("external_factors_json", sa.JSON(), nullable=False),
        sa.Column("worked_well_json", sa.JSON(), nullable=False),
        sa.Column("alternatives_json", sa.JSON(), nullable=False),
        sa.Column("knowledge_unlocked_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "source_type", "source_id", name="uq_outcome_report_source"
        ),
    )
    op.create_index("ix_outcome_reports_profile_id", "outcome_reports", ["profile_id"])
    op.create_index(
        "ix_outcome_report_profile_created", "outcome_reports", ["profile_id", "created_at"]
    )

    op.create_table(
        "adaptive_help_offers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("context_key", sa.String(80), nullable=False),
        sa.Column("explanation_key", sa.String(120), nullable=False),
        sa.Column("suggestion_key", sa.String(120), nullable=False),
        sa.Column("target_path", sa.String(180), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('offered', 'accepted', 'dismissed', 'completed')",
            name="ck_adaptive_help_status",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "context_key", name="uq_adaptive_help_context"),
    )
    op.create_index("ix_adaptive_help_offers_profile_id", "adaptive_help_offers", ["profile_id"])

    op.create_table(
        "personal_success_chains",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("chain_key", sa.String(80), nullable=False),
        sa.Column("completed_steps", sa.Integer(), nullable=False),
        sa.Column("total_steps", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("completed_event_types_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "completed_steps BETWEEN 0 AND total_steps", name="ck_success_chain_steps"
        ),
        sa.CheckConstraint("total_steps BETWEEN 1 AND 12", name="ck_success_chain_total"),
        sa.CheckConstraint("status IN ('active', 'completed')", name="ck_success_chain_status"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "chain_key", name="uq_success_chain_profile"),
    )
    op.create_index(
        "ix_personal_success_chains_profile_id", "personal_success_chains", ["profile_id"]
    )

    op.create_table(
        "mentorships",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(36), nullable=False),
        sa.Column("mentor_profile_id", sa.String(36), nullable=False),
        sa.Column("mentee_profile_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("mentor_opted_in", sa.Boolean(), nullable=False),
        sa.Column("mentee_opted_in", sa.Boolean(), nullable=False),
        sa.Column("feedback_positive", sa.Boolean(), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("mentor_profile_id <> mentee_profile_id", name="ck_mentorship_distinct"),
        sa.CheckConstraint(
            "status IN ('proposed', 'active', 'paused', 'completed', 'declined', 'cancelled')",
            name="ck_mentorship_status",
        ),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mentor_profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["mentee_profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mentor_profile_id", "idempotency_key", name="uq_mentorship_key"),
    )
    op.create_index("ix_mentorships_world_id", "mentorships", ["world_id"])
    op.create_index("ix_mentorships_mentor_profile_id", "mentorships", ["mentor_profile_id"])
    op.create_index("ix_mentorships_mentee_profile_id", "mentorships", ["mentee_profile_id"])
    op.create_index("ix_mentorship_mentee_status", "mentorships", ["mentee_profile_id", "status"])

    op.create_table(
        "mentoring_milestones",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("mentorship_id", sa.String(36), nullable=False),
        sa.Column("verified_event_id", sa.String(36), nullable=True),
        sa.Column("milestone_key", sa.String(40), nullable=False),
        sa.Column("evidence_json", sa.JSON(), nullable=False),
        sa.Column("achieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "milestone_key IN ('system_understood', 'independent_decision', 'positive_feedback')",
            name="ck_mentoring_milestone_key",
        ),
        sa.ForeignKeyConstraint(["mentorship_id"], ["mentorships.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["verified_event_id"], ["engagement_events.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("mentorship_id", "milestone_key", name="uq_mentoring_milestone"),
    )
    op.create_index(
        "ix_mentoring_milestones_mentorship_id", "mentoring_milestones", ["mentorship_id"]
    )

    op.create_table(
        "cartel_delegations",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("grantor_membership_id", sa.String(36), nullable=False),
        sa.Column("delegate_membership_id", sa.String(36), nullable=False),
        sa.Column("role_key", sa.String(40), nullable=False),
        sa.Column("permissions_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("expires_at > starts_at", name="ck_delegation_duration"),
        sa.CheckConstraint(
            "status IN ('active', 'revoked', 'expired')", name="ck_delegation_status"
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["grantor_membership_id"], ["organization_memberships.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["delegate_membership_id"], ["organization_memberships.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("grantor_membership_id", "idempotency_key", name="uq_delegation_key"),
    )
    op.create_index(
        "ix_cartel_delegations_organization_id", "cartel_delegations", ["organization_id"]
    )
    op.create_index(
        "ix_cartel_delegations_grantor_membership_id",
        "cartel_delegations",
        ["grantor_membership_id"],
    )
    op.create_index(
        "ix_cartel_delegations_delegate_membership_id",
        "cartel_delegations",
        ["delegate_membership_id"],
    )
    op.create_index(
        "ix_delegation_org_status",
        "cartel_delegations",
        ["organization_id", "status", "expires_at"],
    )

    op.create_table(
        "cartel_membership_pauses",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("membership_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("private_reason", sa.String(240), nullable=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_until", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("planned_until > starts_at", name="ck_membership_pause_duration"),
        sa.CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')", name="ck_membership_pause_status"
        ),
        sa.ForeignKeyConstraint(
            ["membership_id"], ["organization_memberships.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("membership_id", "idempotency_key", name="uq_membership_pause_key"),
    )
    op.create_index(
        "ix_cartel_membership_pauses_membership_id", "cartel_membership_pauses", ["membership_id"]
    )
    op.create_index(
        "ix_membership_pause_status_until",
        "cartel_membership_pauses",
        ["status", "planned_until"],
    )

    op.create_table(
        "cartel_chronicle_entries",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("actor_profile_id", sa.String(36), nullable=True),
        sa.Column("entry_type", sa.String(40), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("title_key", sa.String(120), nullable=False),
        sa.Column("body_key", sa.String(120), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id",
            "source_type",
            "source_id",
            "entry_type",
            name="uq_cartel_chronicle_source",
        ),
    )
    op.create_index(
        "ix_cartel_chronicle_entries_organization_id",
        "cartel_chronicle_entries",
        ["organization_id"],
    )
    op.create_index(
        "ix_cartel_chronicle_entries_actor_profile_id",
        "cartel_chronicle_entries",
        ["actor_profile_id"],
    )
    op.create_index(
        "ix_cartel_chronicle_org_created",
        "cartel_chronicle_entries",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cartel_chronicle_org_created", table_name="cartel_chronicle_entries")
    op.drop_index(
        "ix_cartel_chronicle_entries_actor_profile_id", table_name="cartel_chronicle_entries"
    )
    op.drop_index(
        "ix_cartel_chronicle_entries_organization_id", table_name="cartel_chronicle_entries"
    )
    op.drop_table("cartel_chronicle_entries")
    op.drop_index("ix_membership_pause_status_until", table_name="cartel_membership_pauses")
    op.drop_index(
        "ix_cartel_membership_pauses_membership_id", table_name="cartel_membership_pauses"
    )
    op.drop_table("cartel_membership_pauses")
    op.drop_index("ix_delegation_org_status", table_name="cartel_delegations")
    op.drop_index("ix_cartel_delegations_delegate_membership_id", table_name="cartel_delegations")
    op.drop_index("ix_cartel_delegations_grantor_membership_id", table_name="cartel_delegations")
    op.drop_index("ix_cartel_delegations_organization_id", table_name="cartel_delegations")
    op.drop_table("cartel_delegations")
    op.drop_index("ix_mentoring_milestones_mentorship_id", table_name="mentoring_milestones")
    op.drop_table("mentoring_milestones")
    op.drop_index("ix_mentorship_mentee_status", table_name="mentorships")
    op.drop_index("ix_mentorships_mentee_profile_id", table_name="mentorships")
    op.drop_index("ix_mentorships_mentor_profile_id", table_name="mentorships")
    op.drop_index("ix_mentorships_world_id", table_name="mentorships")
    op.drop_table("mentorships")
    op.drop_index("ix_personal_success_chains_profile_id", table_name="personal_success_chains")
    op.drop_table("personal_success_chains")
    op.drop_index("ix_adaptive_help_offers_profile_id", table_name="adaptive_help_offers")
    op.drop_table("adaptive_help_offers")
    op.drop_index("ix_outcome_report_profile_created", table_name="outcome_reports")
    op.drop_index("ix_outcome_reports_profile_id", table_name="outcome_reports")
    op.drop_table("outcome_reports")
    op.drop_index("ix_mastery_progress_profile_id", table_name="mastery_progress")
    op.drop_table("mastery_progress")
    op.drop_index("ix_mastery_entry_profile_created", table_name="mastery_entries")
    op.drop_index("ix_mastery_entries_area_key", table_name="mastery_entries")
    op.drop_index("ix_mastery_entries_profile_id", table_name="mastery_entries")
    op.drop_table("mastery_entries")
    op.drop_index("ix_player_doctrines_profile_id", table_name="player_doctrines")
    op.drop_table("player_doctrines")
    op.drop_index("ix_doctrine_selections_doctrine_key", table_name="doctrine_selections")
    op.drop_index("ix_doctrine_selections_profile_id", table_name="doctrine_selections")
    op.drop_table("doctrine_selections")
