"""Add narrative, collection, season-goal and return-contract engagement systems."""

import sqlalchemy as sa
from alembic import op

revision = "0020_engagement_narrative_legacy"
down_revision = "0019_engagement_competence_social"
branch_labels = None
depends_on = None

TABLES = {
    "narrative_actors",
    "player_actor_relationships",
    "narrative_chronicle_entries",
    "event_dossiers",
    "dossier_clues",
    "player_dossier_progress",
    "collection_items",
    "player_collections",
    "player_identities",
    "legacy_records",
    "player_season_goals",
    "return_contracts",
}


def upgrade() -> None:
    existing = TABLES & set(sa.inspect(op.get_bind()).get_table_names())
    if existing and existing != TABLES:
        raise RuntimeError("Engagement narrative/legacy schema is only partially present")
    if existing == TABLES:
        return
    op.create_table(
        "narrative_actors",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(36), nullable=False),
        sa.Column("actor_key", sa.String(80), nullable=False),
        sa.Column("actor_type", sa.String(32), nullable=False),
        sa.Column("name_key", sa.String(120), nullable=False),
        sa.Column("description_key", sa.String(120), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "actor_type IN ('entrepreneur', 'journalist', 'analyst', 'decision_maker')",
            name="ck_narrative_actor_type",
        ),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("world_id", "actor_key", name="uq_narrative_actor_world_key"),
    )
    op.create_index("ix_narrative_actors_world_id", "narrative_actors", ["world_id"])
    op.create_index("ix_narrative_actors_actor_key", "narrative_actors", ["actor_key"])

    op.create_table(
        "player_actor_relationships",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("trust", sa.Integer(), nullable=False),
        sa.Column("rivalry", sa.Integer(), nullable=False),
        sa.Column("reputation", sa.Integer(), nullable=False),
        sa.Column("interaction_count", sa.Integer(), nullable=False),
        sa.Column("history_keys_json", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("trust BETWEEN -100 AND 100", name="ck_actor_relationship_trust"),
        sa.CheckConstraint("rivalry BETWEEN 0 AND 100", name="ck_actor_relationship_rivalry"),
        sa.CheckConstraint(
            "reputation BETWEEN -100 AND 100", name="ck_actor_relationship_reputation"
        ),
        sa.CheckConstraint("interaction_count >= 0", name="ck_actor_relationship_interactions"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actor_id"], ["narrative_actors.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "actor_id", name="uq_player_actor_relationship"),
    )
    op.create_index(
        "ix_player_actor_relationships_profile_id", "player_actor_relationships", ["profile_id"]
    )
    op.create_index(
        "ix_player_actor_relationships_actor_id", "player_actor_relationships", ["actor_id"]
    )

    op.create_table(
        "narrative_chronicle_entries",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("scope_type", sa.String(20), nullable=False),
        sa.Column("scope_id", sa.String(80), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("entry_type", sa.String(40), nullable=False),
        sa.Column("title_key", sa.String(120), nullable=False),
        sa.Column("body_key", sa.String(120), nullable=False),
        sa.Column("cause_keys_json", sa.JSON(), nullable=False),
        sa.Column("actor_keys_json", sa.JSON(), nullable=False),
        sa.Column("impact_keys_json", sa.JSON(), nullable=False),
        sa.Column("open_question_keys_json", sa.JSON(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "scope_type IN ('company', 'world', 'profile')", name="ck_narrative_chronicle_scope"
        ),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["event_id"], ["engagement_events.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scope_type",
            "scope_id",
            "source_type",
            "source_id",
            "entry_type",
            name="uq_narrative_chronicle_source",
        ),
    )
    op.create_index(
        "ix_narrative_chronicle_entries_world_id",
        "narrative_chronicle_entries",
        ["world_id"],
    )
    op.create_index(
        "ix_narrative_chronicle_entries_profile_id",
        "narrative_chronicle_entries",
        ["profile_id"],
    )
    op.create_index(
        "ix_narrative_chronicle_entries_event_id",
        "narrative_chronicle_entries",
        ["event_id"],
    )
    op.create_index(
        "ix_narrative_chronicle_scope_created",
        "narrative_chronicle_entries",
        ["scope_type", "scope_id", "created_at"],
    )

    op.create_table(
        "event_dossiers",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("world_id", sa.String(36), nullable=False),
        sa.Column("world_event_instance_id", sa.String(36), nullable=False),
        sa.Column("title_key", sa.String(120), nullable=False),
        sa.Column("cause_key", sa.String(120), nullable=False),
        sa.Column("local_impact_key", sa.String(120), nullable=False),
        sa.Column("open_question_key", sa.String(120), nullable=False),
        sa.Column("total_clues", sa.Integer(), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("total_clues BETWEEN 1 AND 12", name="ck_event_dossier_clues"),
        sa.ForeignKeyConstraint(["world_id"], ["worlds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["world_event_instance_id"], ["world_event_instances.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("world_event_instance_id", name="uq_event_dossier_instance"),
    )
    op.create_index("ix_event_dossiers_world_id", "event_dossiers", ["world_id"])
    op.create_table(
        "dossier_clues",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("clue_key", sa.String(120), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("rare", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("order_index BETWEEN 1 AND 12", name="ck_dossier_clue_order"),
        sa.ForeignKeyConstraint(["dossier_id"], ["event_dossiers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dossier_id", "clue_key", name="uq_dossier_clue_key"),
        sa.UniqueConstraint("dossier_id", "order_index", name="uq_dossier_clue_order"),
    )
    op.create_index("ix_dossier_clues_dossier_id", "dossier_clues", ["dossier_id"])
    op.create_table(
        "player_dossier_progress",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("dossier_id", sa.String(36), nullable=False),
        sa.Column("investigation_count", sa.Integer(), nullable=False),
        sa.Column("discovered_clue_ids_json", sa.JSON(), nullable=False),
        sa.Column("collection_points", sa.Integer(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("investigation_count >= 0", name="ck_dossier_investigations"),
        sa.CheckConstraint("collection_points >= 0", name="ck_dossier_collection_points"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["dossier_id"], ["event_dossiers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "dossier_id", name="uq_player_dossier_progress"),
    )
    op.create_index(
        "ix_player_dossier_progress_profile_id", "player_dossier_progress", ["profile_id"]
    )
    op.create_index(
        "ix_player_dossier_progress_dossier_id", "player_dossier_progress", ["dossier_id"]
    )

    op.create_table(
        "collection_items",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("item_key", sa.String(80), nullable=False),
        sa.Column("item_type", sa.String(24), nullable=False),
        sa.Column("title_key", sa.String(120), nullable=False),
        sa.Column("description_key", sa.String(120), nullable=False),
        sa.Column("rarity", sa.String(20), nullable=False),
        sa.Column("guarantee_after", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "item_type IN ('title', 'emblem', 'hq_cosmetic', 'chronicle', 'discovery')",
            name="ck_collection_item_type",
        ),
        sa.CheckConstraint("guarantee_after >= 0", name="ck_collection_item_guarantee"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_key", name="uq_collection_item_key"),
    )
    op.create_index("ix_collection_items_item_key", "collection_items", ["item_key"])
    op.create_index("ix_collection_items_item_type", "collection_items", ["item_type"])
    op.create_table(
        "player_collections",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("duplicate_points", sa.Integer(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("duplicate_points >= 0", name="ck_player_collection_duplicates"),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["item_id"], ["collection_items.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "item_id", name="uq_player_collection_item"),
    )
    op.create_index("ix_player_collections_profile_id", "player_collections", ["profile_id"])
    op.create_index("ix_player_collections_item_id", "player_collections", ["item_id"])
    op.create_table(
        "player_identities",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("active_title_item_id", sa.String(36), nullable=True),
        sa.Column("active_emblem_item_id", sa.String(36), nullable=True),
        sa.Column("active_hq_cosmetic_item_id", sa.String(36), nullable=True),
        sa.Column("profile_card_public", sa.Boolean(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["active_title_item_id"], ["collection_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["active_emblem_item_id"], ["collection_items.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["active_hq_cosmetic_item_id"], ["collection_items.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", name="uq_player_identity_profile"),
    )
    op.create_index("ix_player_identities_profile_id", "player_identities", ["profile_id"])

    op.create_table(
        "legacy_records",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("record_key", sa.String(80), nullable=False),
        sa.Column("source_type", sa.String(40), nullable=False),
        sa.Column("source_id", sa.String(80), nullable=False),
        sa.Column("title_key", sa.String(120), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "record_key", "source_id", name="uq_legacy_record_source"
        ),
    )
    op.create_index("ix_legacy_records_profile_id", "legacy_records", ["profile_id"])
    op.create_index(
        "ix_legacy_record_profile_created", "legacy_records", ["profile_id", "created_at"]
    )

    op.create_table(
        "player_season_goals",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("season_id", sa.String(36), nullable=False),
        sa.Column("goal_key", sa.String(40), nullable=False),
        sa.Column("title_key", sa.String(120), nullable=False),
        sa.Column("description_key", sa.String(120), nullable=False),
        sa.Column("event_types_json", sa.JSON(), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("progress_value", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "goal_key IN ('economic_resilience', 'social_impact', 'world_exploration', "
            "'intelligence_depth', 'strategic_variety')",
            name="ck_player_season_goal_key",
        ),
        sa.CheckConstraint(
            "status IN ('offered', 'active', 'completed', 'archived')",
            name="ck_player_season_goal_status",
        ),
        sa.CheckConstraint(
            "target_value > 0 AND progress_value BETWEEN 0 AND target_value",
            name="ck_player_season_goal_progress",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["season_id"], ["seasons.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("profile_id", "season_id", "goal_key", name="uq_player_season_goal"),
    )
    op.create_index("ix_player_season_goals_profile_id", "player_season_goals", ["profile_id"])
    op.create_index("ix_player_season_goals_season_id", "player_season_goals", ["season_id"])

    op.create_table(
        "return_contracts",
        sa.Column("id", sa.String(36), nullable=False),
        sa.Column("profile_id", sa.String(36), nullable=False),
        sa.Column("contract_key", sa.String(40), nullable=False),
        sa.Column("title_key", sa.String(120), nullable=False),
        sa.Column("description_key", sa.String(120), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("target_value", sa.Integer(), nullable=False),
        sa.Column("progress_value", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("absence_days", sa.Integer(), nullable=False),
        sa.Column("offered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("selected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "contract_key IN ('stabilize_company', 'review_world', 'reconnect_social')",
            name="ck_return_contract_key",
        ),
        sa.CheckConstraint(
            "status IN ('offered', 'active', 'completed', 'declined')",
            name="ck_return_contract_status",
        ),
        sa.CheckConstraint(
            "target_value > 0 AND progress_value BETWEEN 0 AND target_value",
            name="ck_return_contract_progress",
        ),
        sa.ForeignKeyConstraint(["profile_id"], ["player_profiles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "profile_id", "contract_key", "offered_at", name="uq_return_contract_offer"
        ),
    )
    op.create_index("ix_return_contracts_profile_id", "return_contracts", ["profile_id"])
    op.create_index(
        "ix_return_contract_profile_status",
        "return_contracts",
        ["profile_id", "status", "offered_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_return_contract_profile_status", table_name="return_contracts")
    op.drop_index("ix_return_contracts_profile_id", table_name="return_contracts")
    op.drop_table("return_contracts")
    op.drop_index("ix_player_season_goals_season_id", table_name="player_season_goals")
    op.drop_index("ix_player_season_goals_profile_id", table_name="player_season_goals")
    op.drop_table("player_season_goals")
    op.drop_index("ix_legacy_record_profile_created", table_name="legacy_records")
    op.drop_index("ix_legacy_records_profile_id", table_name="legacy_records")
    op.drop_table("legacy_records")
    op.drop_index("ix_player_identities_profile_id", table_name="player_identities")
    op.drop_table("player_identities")
    op.drop_index("ix_player_collections_item_id", table_name="player_collections")
    op.drop_index("ix_player_collections_profile_id", table_name="player_collections")
    op.drop_table("player_collections")
    op.drop_index("ix_collection_items_item_type", table_name="collection_items")
    op.drop_index("ix_collection_items_item_key", table_name="collection_items")
    op.drop_table("collection_items")
    op.drop_index("ix_player_dossier_progress_dossier_id", table_name="player_dossier_progress")
    op.drop_index("ix_player_dossier_progress_profile_id", table_name="player_dossier_progress")
    op.drop_table("player_dossier_progress")
    op.drop_index("ix_dossier_clues_dossier_id", table_name="dossier_clues")
    op.drop_table("dossier_clues")
    op.drop_index("ix_event_dossiers_world_id", table_name="event_dossiers")
    op.drop_table("event_dossiers")
    op.drop_index("ix_narrative_chronicle_scope_created", table_name="narrative_chronicle_entries")
    op.drop_index(
        "ix_narrative_chronicle_entries_event_id", table_name="narrative_chronicle_entries"
    )
    op.drop_index(
        "ix_narrative_chronicle_entries_profile_id", table_name="narrative_chronicle_entries"
    )
    op.drop_index(
        "ix_narrative_chronicle_entries_world_id", table_name="narrative_chronicle_entries"
    )
    op.drop_table("narrative_chronicle_entries")
    op.drop_index("ix_player_actor_relationships_actor_id", table_name="player_actor_relationships")
    op.drop_index(
        "ix_player_actor_relationships_profile_id", table_name="player_actor_relationships"
    )
    op.drop_table("player_actor_relationships")
    op.drop_index("ix_narrative_actors_actor_key", table_name="narrative_actors")
    op.drop_index("ix_narrative_actors_world_id", table_name="narrative_actors")
    op.drop_table("narrative_actors")
