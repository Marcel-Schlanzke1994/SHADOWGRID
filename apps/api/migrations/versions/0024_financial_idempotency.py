"""Widen server-derived financial idempotency keys."""

import sqlalchemy as sa
from alembic import op

revision = "0024_financial_idempotency"
down_revision = "0023_engagement_event_semantics"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ledger_transactions") as batch:
        batch.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=120),
            type_=sa.String(length=160),
            existing_nullable=False,
        )
    with op.batch_alter_table("ledger_entries") as batch:
        batch.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=80),
            type_=sa.String(length=160),
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("ledger_entries") as batch:
        batch.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=160),
            type_=sa.String(length=80),
            existing_nullable=False,
        )
    with op.batch_alter_table("ledger_transactions") as batch:
        batch.alter_column(
            "idempotency_key",
            existing_type=sa.String(length=160),
            type_=sa.String(length=120),
            existing_nullable=False,
        )
