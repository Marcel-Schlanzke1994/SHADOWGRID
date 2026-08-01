"""Add shared transactional rate-limit buckets for release hardening."""

import sqlalchemy as sa
from alembic import op

revision = "0017_release_hardening"
down_revision = "0016_realtime_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    if "rate_limit_buckets" not in tables:
        op.create_table(
            "rate_limit_buckets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("scope", sa.String(length=40), nullable=False),
            sa.Column("key_hash", sa.String(length=64), nullable=False),
            sa.Column(
                "window_started_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column("attempts", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.CheckConstraint(
                "attempts BETWEEN 1 AND 1000000",
                name="ck_rate_limit_attempts",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "scope",
                "key_hash",
                "window_started_at",
                name="uq_rate_limit_scope_key_window",
            ),
        )
        op.create_index(
            "ix_rate_limit_expires",
            "rate_limit_buckets",
            ["expires_at"],
            unique=False,
        )
    if "seed_runs" not in tables:
        op.create_table(
            "seed_runs",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("seed_key", sa.String(length=32), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("random_seed", sa.Integer(), nullable=False),
            sa.Column(
                "applied_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.CheckConstraint(
                "random_seed >= 0",
                name="ck_seed_random_nonnegative",
            ),
            sa.CheckConstraint(
                "version > 0",
                name="ck_seed_version_positive",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "seed_key",
                "version",
                name="uq_seed_key_version",
            ),
        )


def downgrade() -> None:
    op.drop_table("seed_runs")
    op.drop_index("ix_rate_limit_expires", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
