"""Add Phase 6 cartel governance, treasury projects and influence."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from shadowgrid import models  # noqa: F401
from shadowgrid.database import Base

revision = "0008_cartels"
down_revision = "0007_exchange"
branch_labels = None
depends_on = None

NEW_TABLES = (
    "cartel_expenses",
    "cartel_projects",
    "cartel_project_contributions",
    "cartel_district_influences",
)


def _uuid() -> str:
    return str(uuid4())


def _replace_account_owner_constraint(bind: sa.Connection) -> None:
    checks = {
        str(item["name"])
        for item in sa.inspect(bind).get_check_constraints("accounts")
        if item["name"] is not None
    }
    sql = "owner_type IN ('profile', 'company', 'organization', 'system')"
    if bind.dialect.name == "sqlite":
        if "ck_account_owner_type" not in checks:
            return
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = OFF")
        with op.batch_alter_table("accounts", recreate="always") as batch:
            batch.drop_constraint("ck_account_owner_type", type_="check")
            batch.create_check_constraint("ck_account_owner_type", sql)
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = ON")
    else:
        if "ck_account_owner_type" in checks:
            op.drop_constraint("ck_account_owner_type", "accounts", type_="check")
        op.create_check_constraint("ck_account_owner_type", "accounts", sql)


def _add_organization_columns_and_constraints(bind: sa.Connection) -> None:
    inspector = sa.inspect(bind)
    columns = {str(item["name"]) for item in inspector.get_columns("organizations")}
    constraints = {
        str(item["name"])
        for item in (
            inspector.get_check_constraints("organizations")
            + inspector.get_unique_constraints("organizations")
        )
        if item["name"] is not None
    }
    missing_columns = {
        "approval_threshold_cents",
        "single_spend_limit_cents",
        "status",
        "dissolved_at",
    } - columns
    required_constraints = {
        "uq_organization_world_name",
        "uq_organization_world_tag",
        "ck_organization_stability",
        "ck_organization_member_limit",
        "ck_organization_spend_limits",
        "ck_organization_status",
    }
    missing_constraints = required_constraints - constraints
    if not missing_columns and not missing_constraints:
        return

    kwargs = {"recreate": "always"} if bind.dialect.name == "sqlite" else {}
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = OFF")
    with op.batch_alter_table("organizations", **kwargs) as batch:
        if "approval_threshold_cents" in missing_columns:
            batch.add_column(
                sa.Column(
                    "approval_threshold_cents",
                    sa.BigInteger(),
                    nullable=False,
                    server_default="250000",
                )
            )
        if "single_spend_limit_cents" in missing_columns:
            batch.add_column(
                sa.Column(
                    "single_spend_limit_cents",
                    sa.BigInteger(),
                    nullable=False,
                    server_default="2500000",
                )
            )
        if "status" in missing_columns:
            batch.add_column(
                sa.Column("status", sa.String(length=24), nullable=False, server_default="active")
            )
        if "dissolved_at" in missing_columns:
            batch.add_column(sa.Column("dissolved_at", sa.DateTime(timezone=True), nullable=True))
        if "uq_organization_world_name" in missing_constraints:
            batch.create_unique_constraint(
                "uq_organization_world_name",
                ["world_id", "name"],
            )
        if "uq_organization_world_tag" in missing_constraints:
            batch.create_unique_constraint(
                "uq_organization_world_tag",
                ["world_id", "tag"],
            )
        if "ck_organization_stability" in missing_constraints:
            batch.create_check_constraint(
                "ck_organization_stability",
                "stability BETWEEN 0 AND 100",
            )
        if "ck_organization_member_limit" in missing_constraints:
            batch.create_check_constraint(
                "ck_organization_member_limit",
                "member_limit > 0",
            )
        if "ck_organization_spend_limits" in missing_constraints:
            batch.create_check_constraint(
                "ck_organization_spend_limits",
                "approval_threshold_cents > 0 "
                "AND single_spend_limit_cents >= approval_threshold_cents",
            )
        if "ck_organization_status" in missing_constraints:
            batch.create_check_constraint(
                "ck_organization_status",
                "status IN ('active', 'dissolved')",
            )
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = ON")


def _add_membership_invariant(bind: sa.Connection) -> None:
    indexes = {
        str(item["name"]) for item in sa.inspect(bind).get_indexes("organization_memberships")
    }
    if "uq_active_organization_membership_profile" not in indexes:
        op.create_index(
            "uq_active_organization_membership_profile",
            "organization_memberships",
            ["profile_id"],
            unique=True,
            sqlite_where=sa.text("status = 'active'"),
            postgresql_where=sa.text("status = 'active'"),
        )


def _reconcile_active_memberships(bind: sa.Connection) -> None:
    metadata = sa.MetaData()
    memberships = sa.Table("organization_memberships", metadata, autoload_with=bind)
    audit_logs = sa.Table("audit_logs", metadata, autoload_with=bind)
    duplicate_profiles = bind.execute(
        sa.select(memberships.c.profile_id)
        .where(memberships.c.status == "active")
        .group_by(memberships.c.profile_id)
        .having(sa.func.count() > 1)
    ).scalars()
    now = datetime.now(UTC)
    for profile_id in duplicate_profiles:
        active_rows = list(
            bind.execute(
                sa.select(memberships)
                .where(
                    memberships.c.profile_id == profile_id,
                    memberships.c.status == "active",
                )
                .order_by(memberships.c.joined_at, memberships.c.id)
            ).mappings()
        )
        kept = active_rows[0]
        for removed in active_rows[1:]:
            bind.execute(
                memberships.update()
                .where(memberships.c.id == removed["id"])
                .values(status="removed")
            )
            bind.execute(
                audit_logs.insert().values(
                    id=_uuid(),
                    actor_user_id=None,
                    action="migration.cartel_membership_reconciled",
                    target_type="organization",
                    target_id=removed["organization_id"],
                    request_id="migration-0008-cartels",
                    metadata_json={
                        "profile_id": profile_id,
                        "kept_membership_id": kept["id"],
                        "removed_membership_id": removed["id"],
                    },
                    created_at=now,
                )
            )


def _add_membership_status_constraint(bind: sa.Connection) -> None:
    checks = {
        str(item["name"])
        for item in sa.inspect(bind).get_check_constraints("organization_memberships")
        if item["name"] is not None
    }
    if "ck_organization_membership_status" in checks:
        return
    condition = "status IN ('active', 'left', 'removed')"
    if bind.dialect.name == "sqlite":
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = OFF")
        with op.batch_alter_table("organization_memberships", recreate="always") as batch:
            batch.create_check_constraint("ck_organization_membership_status", condition)
        with op.get_context().autocommit_block():
            op.execute("PRAGMA foreign_keys = ON")
    else:
        op.create_check_constraint(
            "ck_organization_membership_status",
            "organization_memberships",
            condition,
        )


def _add_invite_timestamps(bind: sa.Connection) -> None:
    columns = {str(item["name"]) for item in sa.inspect(bind).get_columns("organization_invites")}
    if "accepted_at" not in columns:
        op.add_column(
            "organization_invites",
            sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "declined_at" not in columns:
        op.add_column(
            "organization_invites",
            sa.Column("declined_at", sa.DateTime(timezone=True), nullable=True),
        )
    if "created_at" not in columns:
        op.add_column(
            "organization_invites",
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )


def _backfill_cartel_accounts(bind: sa.Connection) -> None:
    metadata = sa.MetaData()
    organizations = sa.Table("organizations", metadata, autoload_with=bind)
    accounts = sa.Table("accounts", metadata, autoload_with=bind)
    transactions = sa.Table("ledger_transactions", metadata, autoload_with=bind)
    entries = sa.Table("account_ledger_entries", metadata, autoload_with=bind)
    now = datetime.now(UTC)
    for organization in bind.execute(
        sa.select(
            organizations.c.id,
            organizations.c.world_id,
            organizations.c.treasury_cash,
        )
    ).mappings():
        existing = (
            bind.execute(
                sa.select(accounts).where(
                    accounts.c.world_id == organization["world_id"],
                    accounts.c.owner_type == "organization",
                    accounts.c.owner_id == organization["id"],
                    accounts.c.currency == "EUR",
                )
            )
            .mappings()
            .first()
        )
        if existing is not None:
            continue
        cartel_account_id = _uuid()
        opening_cents = int(
            (Decimal(str(organization["treasury_cash"])) * Decimal(100)).to_integral_value()
        )
        bind.execute(
            accounts.insert().values(
                id=cartel_account_id,
                world_id=organization["world_id"],
                owner_type="organization",
                owner_id=organization["id"],
                currency="EUR",
                balance_cents=opening_cents,
                reserved_cents=0,
                version=1,
                created_at=now,
                updated_at=now,
            )
        )
        if opening_cents <= 0:
            continue
        system = (
            bind.execute(
                sa.select(accounts).where(
                    accounts.c.world_id == organization["world_id"],
                    accounts.c.owner_type == "system",
                    accounts.c.owner_id == organization["world_id"],
                    accounts.c.currency == "EUR",
                )
            )
            .mappings()
            .first()
        )
        if system is None:
            system_account_id = _uuid()
            system_balance = -opening_cents
            bind.execute(
                accounts.insert().values(
                    id=system_account_id,
                    world_id=organization["world_id"],
                    owner_type="system",
                    owner_id=organization["world_id"],
                    currency="EUR",
                    balance_cents=system_balance,
                    reserved_cents=0,
                    version=1,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            system_account_id = str(system["id"])
            system_balance = int(system["balance_cents"]) - opening_cents
            bind.execute(
                accounts.update()
                .where(accounts.c.id == system_account_id)
                .values(
                    balance_cents=system_balance,
                    version=int(system["version"]) + 1,
                    updated_at=now,
                )
            )
        transaction_id = _uuid()
        bind.execute(
            transactions.insert().values(
                id=transaction_id,
                world_id=organization["world_id"],
                actor_profile_id=None,
                transaction_type="cartel_legacy_opening_balance",
                idempotency_key=f"cartel-opening:{organization['id']}",
                reference_type="organization",
                reference_id=organization["id"],
                metadata_json={},
                created_at=now,
            )
        )
        bind.execute(
            entries.insert(),
            [
                {
                    "id": _uuid(),
                    "transaction_id": transaction_id,
                    "account_id": system_account_id,
                    "amount_cents": -opening_cents,
                    "balance_after_cents": system_balance,
                    "created_at": now,
                },
                {
                    "id": _uuid(),
                    "transaction_id": transaction_id,
                    "account_id": cartel_account_id,
                    "amount_cents": opening_cents,
                    "balance_after_cents": opening_cents,
                    "created_at": now,
                },
            ],
        )


def upgrade() -> None:
    bind = op.get_bind()
    _replace_account_owner_constraint(bind)
    _add_organization_columns_and_constraints(bind)
    _reconcile_active_memberships(bind)
    _add_membership_status_constraint(bind)
    _add_membership_invariant(bind)
    _add_invite_timestamps(bind)
    _backfill_cartel_accounts(bind)
    existing_tables = set(sa.inspect(bind).get_table_names())
    tables = [Base.metadata.tables[name] for name in NEW_TABLES if name not in existing_tables]
    Base.metadata.create_all(bind=bind, tables=tables, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(
        bind=bind,
        tables=[Base.metadata.tables[name] for name in NEW_TABLES],
        checkfirst=True,
    )
    indexes = {
        str(item["name"]) for item in sa.inspect(bind).get_indexes("organization_memberships")
    }
    if "uq_active_organization_membership_profile" in indexes:
        op.drop_index(
            "uq_active_organization_membership_profile",
            table_name="organization_memberships",
        )
    invite_columns = {
        str(item["name"]) for item in sa.inspect(bind).get_columns("organization_invites")
    }
    for column in ("created_at", "declined_at", "accepted_at"):
        if column in invite_columns:
            op.drop_column("organization_invites", column)
