"""Add Phase 4 specialist employment, payroll and local AI state."""

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0005_specialists_ai"
down_revision = "0004_economy_ticks"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "specialist_market_candidates",
    "specialist_payroll_ticks",
    "specialist_payroll_reports",
    "ai_decision_ticks",
    "ai_decisions",
)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = OFF")

    player_profile_columns = (
        sa.Column("is_local_ai", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ai_strategy", sa.String(length=24), nullable=True),
        sa.Column("ai_paused", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ai_seed", sa.Integer(), nullable=True),
    )
    specialist_columns = (
        sa.Column("level", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("energy", sa.Integer(), nullable=False, server_default="100"),
        sa.Column(
            "experience_points",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "skills_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "salary_cents",
            sa.BigInteger(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("employer_company_id", sa.String(length=36), nullable=True),
        sa.Column("cooldown_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("hired_at", sa.DateTime(timezone=True), nullable=True),
    )
    for table_name, columns_to_add in (
        ("player_profiles", player_profile_columns),
        ("specialists", specialist_columns),
    ):
        existing_columns = {str(item["name"]) for item in sa.inspect(bind).get_columns(table_name)}
        for column in columns_to_add:
            if column.name not in existing_columns:
                op.add_column(table_name, column)

    op.execute(
        sa.text(
            "UPDATE specialists SET salary_cents = CAST(salary * 100 AS BIGINT) "
            "WHERE salary_cents = 0"
        )
    )

    profile_checks = (
        (
            "ck_profile_ai_strategy",
            "ai_strategy IS NULL OR ai_strategy IN "
            "('growth', 'efficiency', 'innovation', 'market_share', 'stability')",
        ),
        ("ck_profile_ai_seed", "ai_seed IS NULL OR ai_seed >= 0"),
    )
    specialist_checks = (
        ("ck_specialist_level", "level BETWEEN 1 AND 10"),
        ("ck_specialist_energy", "energy BETWEEN 0 AND 100"),
        (
            "ck_specialist_experience",
            "experience_points BETWEEN 0 AND 100000",
        ),
        ("ck_specialist_salary_cents", "salary_cents >= 0"),
        (
            "ck_specialist_status",
            "status IN ('available', 'hired', 'assigned', 'released')",
        ),
    )
    profile_check_names = {
        str(item["name"])
        for item in sa.inspect(bind).get_check_constraints("player_profiles")
        if item["name"] is not None
    }
    specialist_check_names = {
        str(item["name"])
        for item in sa.inspect(bind).get_check_constraints("specialists")
        if item["name"] is not None
    }
    missing_profile_checks = [item for item in profile_checks if item[0] not in profile_check_names]
    missing_specialist_checks = [
        item for item in specialist_checks if item[0] not in specialist_check_names
    ]
    has_employer_foreign_key = any(
        tuple(str(column) for column in item["constrained_columns"]) == ("employer_company_id",)
        for item in sa.inspect(bind).get_foreign_keys("specialists")
    )
    if bind.dialect.name == "sqlite":
        if missing_profile_checks:
            with op.batch_alter_table("player_profiles", recreate="always") as batch:
                for name, condition in missing_profile_checks:
                    batch.create_check_constraint(name, condition)
        if missing_specialist_checks or not has_employer_foreign_key:
            with op.batch_alter_table("specialists", recreate="always") as batch:
                for name, condition in missing_specialist_checks:
                    batch.create_check_constraint(name, condition)
                if not has_employer_foreign_key:
                    batch.create_foreign_key(
                        "fk_specialists_employer_company_id_companies",
                        "companies",
                        ["employer_company_id"],
                        ["id"],
                    )
    else:
        for name, condition in missing_profile_checks:
            op.create_check_constraint(name, "player_profiles", condition)
        for name, condition in missing_specialist_checks:
            op.create_check_constraint(name, "specialists", condition)
        if not has_employer_foreign_key:
            op.create_foreign_key(
                "fk_specialists_employer_company_id_companies",
                "specialists",
                "companies",
                ["employer_company_id"],
                ["id"],
            )
    specialist_indexes = {
        str(item["name"])
        for item in sa.inspect(bind).get_indexes("specialists")
        if item["name"] is not None
    }
    if "ix_specialists_employer_company_id" not in specialist_indexes:
        op.create_index(
            "ix_specialists_employer_company_id",
            "specialists",
            ["employer_company_id"],
        )

    existing_tables = set(sa.inspect(bind).get_table_names())
    tables = [Base.metadata.tables[name] for name in NEW_TABLES if name not in existing_tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = ON")


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = OFF")
    tables = [Base.metadata.tables[name] for name in NEW_TABLES]
    Base.metadata.drop_all(bind=bind, tables=tables, checkfirst=True)

    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("specialists", recreate="always") as batch:
            batch.drop_index("ix_specialists_employer_company_id")
            batch.drop_constraint("ck_specialist_status", type_="check")
            batch.drop_constraint("ck_specialist_salary_cents", type_="check")
            batch.drop_constraint("ck_specialist_experience", type_="check")
            batch.drop_constraint("ck_specialist_energy", type_="check")
            batch.drop_constraint("ck_specialist_level", type_="check")
            batch.drop_column("hired_at")
            batch.drop_column("cooldown_until")
            batch.drop_column("employer_company_id")
            batch.drop_column("salary_cents")
            batch.drop_column("skills_json")
            batch.drop_column("experience_points")
            batch.drop_column("energy")
            batch.drop_column("level")
        with op.batch_alter_table("player_profiles", recreate="always") as batch:
            batch.drop_constraint("ck_profile_ai_seed", type_="check")
            batch.drop_constraint("ck_profile_ai_strategy", type_="check")
            batch.drop_column("ai_seed")
            batch.drop_column("ai_paused")
            batch.drop_column("ai_strategy")
            batch.drop_column("is_local_ai")
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = ON")
    else:
        op.drop_index("ix_specialists_employer_company_id", table_name="specialists")
        op.drop_constraint("ck_specialist_status", "specialists", type_="check")
        op.drop_constraint("ck_specialist_salary_cents", "specialists", type_="check")
        op.drop_constraint("ck_specialist_experience", "specialists", type_="check")
        op.drop_constraint("ck_specialist_energy", "specialists", type_="check")
        op.drop_constraint("ck_specialist_level", "specialists", type_="check")
        op.drop_column("specialists", "hired_at")
        op.drop_column("specialists", "cooldown_until")
        op.drop_column("specialists", "employer_company_id")
        op.drop_column("specialists", "salary_cents")
        op.drop_column("specialists", "skills_json")
        op.drop_column("specialists", "experience_points")
        op.drop_column("specialists", "energy")
        op.drop_column("specialists", "level")
        op.drop_constraint("ck_profile_ai_seed", "player_profiles", type_="check")
        op.drop_constraint(
            "ck_profile_ai_strategy",
            "player_profiles",
            type_="check",
        )
        op.drop_column("player_profiles", "ai_seed")
        op.drop_column("player_profiles", "ai_paused")
        op.drop_column("player_profiles", "ai_strategy")
        op.drop_column("player_profiles", "is_local_ai")
