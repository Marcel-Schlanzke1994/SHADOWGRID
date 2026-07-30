from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    event,
    inspect,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from shadowgrid.database import Base


def uuid_str() -> str:
    return str(uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    """Normalize database timestamps; SQLite discards timezone offsets on round-trip."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str]
    display_name: Mapped[str] = mapped_column(String(40))
    locale: Mapped[str] = mapped_column(String(16), default="en")
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    is_moderator: Mapped[bool] = mapped_column(Boolean, default=False)
    totp_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class RefreshSession(Base):
    __tablename__ = "refresh_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    family_id: Mapped[str] = mapped_column(String(36), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_agent: Mapped[str] = mapped_column(String(180), default="unknown")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user: Mapped[User] = relationship()


class OneTimeToken(Base):
    __tablename__ = "one_time_tokens"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    purpose: Mapped[str] = mapped_column(String(24))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (
        UniqueConstraint(
            "scope",
            "key_hash",
            "window_started_at",
            name="uq_rate_limit_scope_key_window",
        ),
        CheckConstraint(
            "attempts BETWEEN 1 AND 1000000",
            name="ck_rate_limit_attempts",
        ),
        Index("ix_rate_limit_expires", "expires_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    scope: Mapped[str] = mapped_column(String(40))
    key_hash: Mapped[str] = mapped_column(String(64))
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SeedRun(Base):
    __tablename__ = "seed_runs"
    __table_args__ = (
        UniqueConstraint("seed_key", "version", name="uq_seed_key_version"),
        CheckConstraint("version > 0", name="ck_seed_version_positive"),
        CheckConstraint("random_seed >= 0", name="ck_seed_random_nonnegative"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    seed_key: Mapped[str] = mapped_column(String(32))
    version: Mapped[int] = mapped_column(Integer)
    random_seed: Mapped[int] = mapped_column(Integer)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    recipient: Mapped[str] = mapped_column(String(320), index=True)
    subject: Mapped[str] = mapped_column(String(160))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class World(Base):
    __tablename__ = "worlds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), default="active")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    season_number: Mapped[int] = mapped_column(Integer, default=0)


class City(Base):
    __tablename__ = "cities"
    __table_args__ = (
        UniqueConstraint("world_id", "slug", "instance_key", name="uq_city_world_instance"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(100))
    region_key: Mapped[str] = mapped_column(String(40), default="nordrhein-westfalen")
    instance_key: Mapped[str] = mapped_column(String(24), default="sector-a")
    status: Mapped[str] = mapped_column(String(24), default="active")
    max_players: Mapped[int] = mapped_column(Integer, default=2_000)
    market_state_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerProfile(Base):
    __tablename__ = "player_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", "world_id", name="uq_profile_user_world"),
        CheckConstraint(
            "ai_strategy IS NULL OR ai_strategy IN "
            "('growth', 'efficiency', 'innovation', 'market_share', 'stability')",
            name="ck_profile_ai_strategy",
        ),
        CheckConstraint("ai_seed IS NULL OR ai_seed >= 0", name="ck_profile_ai_seed"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    codename: Mapped[str] = mapped_column(String(40))
    archetype: Mapped[str] = mapped_column(String(40))
    city_id: Mapped[str | None] = mapped_column(ForeignKey("cities.id"), nullable=True, index=True)
    home_district_id: Mapped[str | None] = mapped_column(ForeignKey("districts.id"), nullable=True)
    tutorial_step: Mapped[int] = mapped_column(Integer, default=0)
    loyalty: Mapped[int] = mapped_column(Integer, default=65)
    legitimacy: Mapped[int] = mapped_column(Integer, default=60)
    fear: Mapped[int] = mapped_column(Integer, default=5)
    investigation_pressure: Mapped[int] = mapped_column(Integer, default=0)
    stress: Mapped[int] = mapped_column(Integer, default=0)
    stability: Mapped[int] = mapped_column(Integer, default=70)
    operation_slots: Mapped[int] = mapped_column(Integer, default=2)
    is_local_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_strategy: Mapped[str | None] = mapped_column(String(24), nullable=True)
    ai_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protected_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recovery_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()
    world: Mapped[World] = relationship()
    resources: Mapped[ResourceBalance] = relationship(back_populates="profile", uselist=False)


class ResourceBalance(Base):
    __tablename__ = "resource_balances"

    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    influence: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    intelligence: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    logistics_capacity: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    personnel_capacity: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    profile: Mapped[PlayerProfile] = relationship(back_populates="resources")


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("world_id", "owner_type", "owner_id", "currency", name="uq_account_owner"),
        CheckConstraint(
            "owner_type IN ('profile', 'company', 'organization', 'system')",
            name="ck_account_owner_type",
        ),
        CheckConstraint(
            "owner_type = 'system' OR balance_cents >= 0",
            name="ck_account_nonnegative",
        ),
        CheckConstraint(
            "reserved_cents >= 0 AND "
            "((owner_type = 'system' AND reserved_cents = 0) OR reserved_cents <= balance_cents)",
            name="ck_account_reservation",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    owner_type: Mapped[str] = mapped_column(String(24))
    owner_id: Mapped[str] = mapped_column(String(36), index=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    balance_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"
    __table_args__ = (
        UniqueConstraint("world_id", "idempotency_key", name="uq_financial_transaction_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    actor_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id"), nullable=True, index=True
    )
    transaction_type: Mapped[str] = mapped_column(String(48))
    idempotency_key: Mapped[str] = mapped_column(String(120))
    reference_type: Mapped[str] = mapped_column(String(40))
    reference_id: Mapped[str] = mapped_column(String(36))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccountLedgerEntry(Base):
    __tablename__ = "account_ledger_entries"
    __table_args__ = (
        UniqueConstraint("transaction_id", "account_id", name="uq_transaction_account"),
        CheckConstraint("amount_cents <> 0", name="ck_account_entry_nonzero"),
        Index("ix_account_entry_account_created", "account_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("ledger_transactions.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    balance_after_cents: Mapped[int] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        UniqueConstraint(
            "owner_type",
            "owner_id",
            "idempotency_key",
            "resource_type",
            name="uq_ledger_idempotency",
        ),
        Index("ix_ledger_owner_created", "owner_type", "owner_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    owner_type: Mapped[str] = mapped_column(String(24))
    owner_id: Mapped[str] = mapped_column(String(36))
    resource_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    reason: Mapped[str] = mapped_column(String(80))
    reference_type: Mapped[str] = mapped_column(String(40))
    reference_id: Mapped[str] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class District(Base):
    __tablename__ = "districts"
    __table_args__ = (UniqueConstraint("world_id", "slug", name="uq_district_world_slug"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[str | None] = mapped_column(ForeignKey("cities.id"), nullable=True, index=True)
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(100))
    prosperity: Mapped[int] = mapped_column(Integer)
    employment: Mapped[int] = mapped_column(Integer)
    safety: Mapped[int] = mapped_column(Integer)
    authority_presence: Mapped[int] = mapped_column(Integer)
    digital_infrastructure: Mapped[int] = mapped_column(Integer)
    property_value: Mapped[int] = mapped_column(Integer)
    public_trust: Mapped[int] = mapped_column(Integer)
    media_attention: Mapped[int] = mapped_column(Integer)
    economic_activity: Mapped[int] = mapped_column(Integer)
    social_stability: Mapped[int] = mapped_column(Integer)
    map_x: Mapped[int] = mapped_column(Integer)
    map_y: Mapped[int] = mapped_column(Integer)
    map_points: Mapped[str] = mapped_column(String(200))


class DistrictInfluence(Base):
    __tablename__ = "district_influences"
    __table_args__ = (
        UniqueConstraint("district_id", "profile_id", "kind", name="uq_district_profile_influence"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    district_id: Mapped[str] = mapped_column(
        ForeignKey("districts.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24))
    points: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))


class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), index=True)
    business_type: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(100))
    level: Mapped[int] = mapped_column(Integer, default=1)
    revenue: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    operating_cost: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    personnel_need: Mapped[int] = mapped_column(Integer)
    logistics_need: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="operating")
    compliance: Mapped[int] = mapped_column(Integer, default=70)
    reputation: Mapped[int] = mapped_column(Integer, default=50)
    market_share: Mapped[int] = mapped_column(Integer, default=5)
    risk: Mapped[int] = mapped_column(Integer, default=10)
    upgrade_finishes_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Company(Base):
    __tablename__ = "companies"
    __table_args__ = (
        UniqueConstraint("world_id", "normalized_name", name="uq_company_world_name"),
        CheckConstraint(
            "industry IN ('gastronomy', 'logistics', 'technology')",
            name="ck_company_industry",
        ),
        CheckConstraint("enterprise_value_cents >= 0", name="ck_company_value_nonnegative"),
        CheckConstraint("revenue_cents >= 0", name="ck_company_revenue_nonnegative"),
        CheckConstraint("cost_cents >= 0", name="ck_company_cost_nonnegative"),
        CheckConstraint("debt_cents >= 0", name="ck_company_debt_nonnegative"),
        CheckConstraint("capacity BETWEEN 0 AND 10000", name="ck_company_capacity"),
        CheckConstraint("quality BETWEEN 0 AND 10000", name="ck_company_quality"),
        CheckConstraint("market_share_bps BETWEEN 0 AND 10000", name="ck_company_market_share"),
        CheckConstraint("reputation_bps BETWEEN 0 AND 10000", name="ck_company_reputation"),
        CheckConstraint("compliance_bps BETWEEN 0 AND 10000", name="ck_company_compliance"),
        CheckConstraint("innovation_bps BETWEEN 0 AND 10000", name="ck_company_innovation"),
        CheckConstraint("risk_bps BETWEEN 0 AND 10000", name="ck_company_risk"),
        CheckConstraint(
            "investigation_pressure_bps BETWEEN 0 AND 10000",
            name="ck_company_investigation_pressure",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    founder_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), index=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), unique=True)
    founding_transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id"), nullable=True, unique=True
    )
    industry: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(100))
    normalized_name: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(24), default="private")
    enterprise_value_cents: Mapped[int] = mapped_column(BigInteger)
    revenue_cents: Mapped[int] = mapped_column(BigInteger)
    cost_cents: Mapped[int] = mapped_column(BigInteger)
    profit_cents: Mapped[int] = mapped_column(BigInteger)
    debt_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    employees: Mapped[int] = mapped_column(Integer)
    capacity: Mapped[int] = mapped_column(Integer)
    quality: Mapped[int] = mapped_column(Integer)
    market_share_bps: Mapped[int] = mapped_column(Integer)
    reputation_bps: Mapped[int] = mapped_column(Integer)
    compliance_bps: Mapped[int] = mapped_column(Integer)
    innovation_bps: Mapped[int] = mapped_column(Integer)
    risk_bps: Mapped[int] = mapped_column(Integer)
    investigation_pressure_bps: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    account: Mapped[Account] = relationship(foreign_keys=[account_id])
    founder: Mapped[PlayerProfile] = relationship(foreign_keys=[founder_profile_id])

    @property
    def account_balance_cents(self) -> int:
        return self.account.balance_cents

    @property
    def is_local_simulation(self) -> bool:
        return self.founder.is_local_ai


class CompanyOwnership(Base):
    __tablename__ = "company_ownership"
    __table_args__ = (
        UniqueConstraint("company_id", "owner_profile_id", name="uq_company_owner"),
        CheckConstraint(
            "ownership_bps BETWEEN 1 AND 10000",
            name="ck_company_ownership_bps",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    owner_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    ownership_bps: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompanyInvestment(Base):
    __tablename__ = "company_investments"
    __table_args__ = (
        UniqueConstraint(
            "investor_profile_id",
            "idempotency_key",
            name="uq_company_investment_key",
        ),
        CheckConstraint("amount_cents > 0", name="ck_company_investment_positive"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    investor_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    transaction_id: Mapped[str] = mapped_column(ForeignKey("ledger_transactions.id"), unique=True)
    investment_type: Mapped[str] = mapped_column(String(32))
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    metric_before: Mapped[int] = mapped_column(Integer)
    metric_after: Mapped[int] = mapped_column(Integer)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompanyMetric(Base):
    __tablename__ = "company_metrics"
    __table_args__ = (UniqueConstraint("company_id", "version", name="uq_company_metric_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(String(40))
    reference_id: Mapped[str] = mapped_column(String(36))
    enterprise_value_cents: Mapped[int] = mapped_column(BigInteger)
    account_balance_cents: Mapped[int] = mapped_column(BigInteger)
    revenue_cents: Mapped[int] = mapped_column(BigInteger)
    cost_cents: Mapped[int] = mapped_column(BigInteger)
    profit_cents: Mapped[int] = mapped_column(BigInteger)
    capacity: Mapped[int] = mapped_column(Integer)
    quality: Mapped[int] = mapped_column(Integer)
    compliance_bps: Mapped[int] = mapped_column(Integer)
    innovation_bps: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CitySectorMarket(Base):
    __tablename__ = "city_sector_markets"
    __table_args__ = (
        UniqueConstraint("world_id", "city_id", "industry", name="uq_city_sector_market"),
        CheckConstraint(
            "industry IN ('gastronomy', 'logistics', 'technology')",
            name="ck_city_sector_market_industry",
        ),
        CheckConstraint("demand_units > 0", name="ck_city_sector_market_demand"),
        CheckConstraint("unit_revenue_cents > 0", name="ck_city_sector_market_revenue"),
        CheckConstraint(
            "variable_cost_per_unit_cents >= 0",
            name="ck_city_sector_market_variable_cost",
        ),
        CheckConstraint("fixed_cost_cents >= 0", name="ck_city_sector_market_fixed_cost"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    industry: Mapped[str] = mapped_column(String(32))
    demand_units: Mapped[int] = mapped_column(Integer)
    unit_revenue_cents: Mapped[int] = mapped_column(BigInteger)
    variable_cost_per_unit_cents: Mapped[int] = mapped_column(BigInteger)
    fixed_cost_cents: Mapped[int] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class EconomyTick(Base):
    __tablename__ = "economy_ticks"
    __table_args__ = (
        UniqueConstraint("world_id", "period_key", name="uq_economy_tick_period"),
        CheckConstraint(
            "status IN ('processing', 'completed', 'failed')",
            name="ck_economy_tick_status",
        ),
        CheckConstraint("company_count >= 0", name="ck_economy_tick_company_count"),
        CheckConstraint("market_count >= 0", name="ck_economy_tick_market_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    period_key: Mapped[str] = mapped_column(String(40))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="processing")
    company_count: Mapped[int] = mapped_column(Integer, default=0)
    market_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MarketEconomyReport(Base):
    __tablename__ = "market_economy_reports"
    __table_args__ = (
        UniqueConstraint("tick_id", "market_id", name="uq_tick_market_report"),
        CheckConstraint("demand_units > 0", name="ck_market_report_demand"),
        CheckConstraint("allocated_units >= 0", name="ck_market_report_allocated"),
        CheckConstraint("unfilled_units >= 0", name="ck_market_report_unfilled"),
        CheckConstraint("company_count >= 0", name="ck_market_report_company_count"),
        CheckConstraint(
            "allocated_share_bps BETWEEN 0 AND 10000",
            name="ck_market_report_share",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tick_id: Mapped[str] = mapped_column(ForeignKey("economy_ticks.id"), index=True)
    market_id: Mapped[str] = mapped_column(ForeignKey("city_sector_markets.id"), index=True)
    demand_units: Mapped[int] = mapped_column(Integer)
    allocated_units: Mapped[int] = mapped_column(Integer)
    unfilled_units: Mapped[int] = mapped_column(Integer)
    allocated_share_bps: Mapped[int] = mapped_column(Integer)
    company_count: Mapped[int] = mapped_column(Integer)
    total_revenue_cents: Mapped[int] = mapped_column(BigInteger)
    total_cost_cents: Mapped[int] = mapped_column(BigInteger)
    total_profit_cents: Mapped[int] = mapped_column(BigInteger)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompanyEconomyReport(Base):
    __tablename__ = "company_economy_reports"
    __table_args__ = (
        UniqueConstraint("tick_id", "company_id", name="uq_tick_company_report"),
        CheckConstraint("attractiveness_points > 0", name="ck_company_report_attractiveness"),
        CheckConstraint("allocated_units >= 0", name="ck_company_report_allocated"),
        CheckConstraint(
            "market_share_bps BETWEEN 0 AND 10000",
            name="ck_company_report_market_share",
        ),
        CheckConstraint("revenue_cents >= 0", name="ck_company_report_revenue"),
        CheckConstraint("cost_cents >= 0", name="ck_company_report_cost"),
        CheckConstraint(
            "enterprise_value_before_cents >= 0",
            name="ck_company_report_value_before",
        ),
        CheckConstraint(
            "enterprise_value_after_cents >= 0",
            name="ck_company_report_value_after",
        ),
        CheckConstraint("debt_delta_cents >= 0", name="ck_company_report_debt_delta"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tick_id: Mapped[str] = mapped_column(ForeignKey("economy_ticks.id"), index=True)
    market_report_id: Mapped[str] = mapped_column(
        ForeignKey("market_economy_reports.id"), index=True
    )
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    settlement_transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id"), nullable=True, unique=True
    )
    attractiveness_points: Mapped[int] = mapped_column(Integer)
    allocated_units: Mapped[int] = mapped_column(Integer)
    market_share_bps: Mapped[int] = mapped_column(Integer)
    revenue_cents: Mapped[int] = mapped_column(BigInteger)
    cost_cents: Mapped[int] = mapped_column(BigInteger)
    profit_cents: Mapped[int] = mapped_column(BigInteger)
    cash_delta_cents: Mapped[int] = mapped_column(BigInteger)
    debt_delta_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    enterprise_value_before_cents: Mapped[int] = mapped_column(BigInteger)
    enterprise_value_after_cents: Mapped[int] = mapped_column(BigInteger)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    modifiers_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ExchangeListing(Base):
    __tablename__ = "exchange_listings"
    __table_args__ = (
        UniqueConstraint("company_id", name="uq_exchange_listing_company"),
        UniqueConstraint("world_id", "symbol", name="uq_exchange_listing_symbol"),
        CheckConstraint(
            "status IN ('active', 'suspended', 'delisted')",
            name="ck_exchange_listing_status",
        ),
        CheckConstraint("total_shares > 0", name="ck_exchange_listing_total_shares"),
        CheckConstraint(
            "offered_shares > 0 AND offered_shares <= total_shares",
            name="ck_exchange_listing_offered_shares",
        ),
        CheckConstraint(
            "initial_price_cents > 0 AND last_price_cents > 0",
            name="ck_exchange_listing_prices",
        ),
        CheckConstraint("ipo_fee_cents >= 0", name="ck_exchange_listing_fee"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), unique=True)
    symbol: Mapped[str] = mapped_column(String(12))
    status: Mapped[str] = mapped_column(String(24), default="active")
    total_shares: Mapped[int] = mapped_column(BigInteger)
    offered_shares: Mapped[int] = mapped_column(BigInteger)
    initial_price_cents: Mapped[int] = mapped_column(BigInteger)
    last_price_cents: Mapped[int] = mapped_column(BigInteger)
    ipo_fee_cents: Mapped[int] = mapped_column(BigInteger)
    fee_transaction_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_transactions.id"),
        unique=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(80))
    listed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )
    company: Mapped[Company] = relationship(foreign_keys=[company_id])

    @property
    def company_name(self) -> str:
        return self.company.name

    @property
    def company_industry(self) -> str:
        return self.company.industry

    @property
    def enterprise_value_cents(self) -> int:
        return self.company.enterprise_value_cents

    @property
    def profit_cents(self) -> int:
        return self.company.profit_cents

    @property
    def debt_cents(self) -> int:
        return self.company.debt_cents


class ShareClass(Base):
    __tablename__ = "share_classes"
    __table_args__ = (
        UniqueConstraint("listing_id", "class_code", name="uq_share_class_code"),
        CheckConstraint("class_code = 'common'", name="ck_share_class_v1"),
        CheckConstraint("total_shares > 0", name="ck_share_class_total"),
        CheckConstraint("voting_rights_per_share >= 0", name="ck_share_class_votes"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    listing_id: Mapped[str] = mapped_column(ForeignKey("exchange_listings.id"), index=True)
    class_code: Mapped[str] = mapped_column(String(24), default="common")
    name: Mapped[str] = mapped_column(String(80), default="Common shares")
    total_shares: Mapped[int] = mapped_column(BigInteger)
    voting_rights_per_share: Mapped[int] = mapped_column(Integer, default=1)
    dividend_priority: Mapped[int] = mapped_column(Integer, default=0)
    tradable: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ShareHolding(Base):
    __tablename__ = "share_holdings"
    __table_args__ = (
        UniqueConstraint(
            "share_class_id",
            "profile_id",
            name="uq_share_holding_profile",
        ),
        UniqueConstraint(
            "share_class_id",
            "company_id",
            name="uq_share_holding_company",
        ),
        CheckConstraint(
            "(owner_type = 'profile' AND profile_id IS NOT NULL AND company_id IS NULL) OR "
            "(owner_type = 'company' AND company_id IS NOT NULL AND profile_id IS NULL)",
            name="ck_share_holding_owner",
        ),
        CheckConstraint("quantity >= 0", name="ck_share_holding_quantity"),
        CheckConstraint(
            "reserved_quantity >= 0 AND reserved_quantity <= quantity",
            name="ck_share_holding_reserved",
        ),
        CheckConstraint("average_cost_cents >= 0", name="ck_share_holding_average_cost"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    share_class_id: Mapped[str] = mapped_column(ForeignKey("share_classes.id"), index=True)
    owner_type: Mapped[str] = mapped_column(String(24))
    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id"),
        nullable=True,
        index=True,
    )
    company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id"),
        nullable=True,
        index=True,
    )
    quantity: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_quantity: Mapped[int] = mapped_column(BigInteger, default=0)
    average_cost_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ExchangeOrder(Base):
    __tablename__ = "exchange_orders"
    __table_args__ = (
        UniqueConstraint("owner_key", "idempotency_key", name="uq_exchange_order_key"),
        CheckConstraint("side IN ('buy', 'sell')", name="ck_exchange_order_side"),
        CheckConstraint(
            "order_type IN ('market', 'limit', 'ipo')",
            name="ck_exchange_order_type",
        ),
        CheckConstraint(
            "status IN ('open', 'partially_filled', 'filled', 'cancelled', 'expired')",
            name="ck_exchange_order_status",
        ),
        CheckConstraint(
            "(profile_id IS NOT NULL AND issuer_company_id IS NULL) OR "
            "(profile_id IS NULL AND issuer_company_id IS NOT NULL AND "
            "side = 'sell' AND order_type = 'ipo')",
            name="ck_exchange_order_owner",
        ),
        CheckConstraint(
            "(order_type = 'market' AND limit_price_cents IS NULL) OR "
            "(order_type IN ('limit', 'ipo') AND limit_price_cents > 0)",
            name="ck_exchange_order_price",
        ),
        CheckConstraint("original_quantity > 0", name="ck_exchange_order_quantity"),
        CheckConstraint(
            "remaining_quantity >= 0 AND remaining_quantity <= original_quantity",
            name="ck_exchange_order_remaining",
        ),
        CheckConstraint(
            "reserved_cash_cents >= 0 AND reserved_shares >= 0",
            name="ck_exchange_order_reservations",
        ),
        Index(
            "ix_exchange_order_book",
            "listing_id",
            "side",
            "status",
            "limit_price_cents",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    listing_id: Mapped[str] = mapped_column(ForeignKey("exchange_listings.id"), index=True)
    share_class_id: Mapped[str] = mapped_column(ForeignKey("share_classes.id"), index=True)
    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id"),
        nullable=True,
        index=True,
    )
    issuer_company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id"),
        nullable=True,
    )
    owner_key: Mapped[str] = mapped_column(String(48))
    side: Mapped[str] = mapped_column(String(8))
    order_type: Mapped[str] = mapped_column(String(12))
    limit_price_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    original_quantity: Mapped[int] = mapped_column(BigInteger)
    remaining_quantity: Mapped[int] = mapped_column(BigInteger)
    reserved_cash_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    reserved_shares: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(24), default="open")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        onupdate=utcnow,
    )


class ExchangeTrade(Base):
    __tablename__ = "exchange_trades"
    __table_args__ = (
        UniqueConstraint("buy_order_id", "sell_order_id", name="uq_exchange_trade_orders"),
        CheckConstraint("buyer_profile_id <> seller_owner_key", name="ck_exchange_no_self_trade"),
        CheckConstraint("quantity > 0", name="ck_exchange_trade_quantity"),
        CheckConstraint(
            "price_cents > 0 AND gross_cents = quantity * price_cents",
            name="ck_exchange_trade_value",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    listing_id: Mapped[str] = mapped_column(ForeignKey("exchange_listings.id"), index=True)
    share_class_id: Mapped[str] = mapped_column(ForeignKey("share_classes.id"), index=True)
    buy_order_id: Mapped[str] = mapped_column(ForeignKey("exchange_orders.id"), index=True)
    sell_order_id: Mapped[str] = mapped_column(ForeignKey("exchange_orders.id"), index=True)
    buyer_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id"),
        index=True,
    )
    seller_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id"),
        nullable=True,
        index=True,
    )
    seller_company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id"),
        nullable=True,
    )
    seller_owner_key: Mapped[str] = mapped_column(String(48))
    quantity: Mapped[int] = mapped_column(BigInteger)
    price_cents: Mapped[int] = mapped_column(BigInteger)
    gross_cents: Mapped[int] = mapped_column(BigInteger)
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_transactions.id"),
        unique=True,
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        index=True,
    )


class ShareLedgerEntry(Base):
    __tablename__ = "share_ledger_entries"
    __table_args__ = (
        UniqueConstraint("event_key", "holding_id", name="uq_share_ledger_event_holding"),
        CheckConstraint("quantity_delta <> 0", name="ck_share_ledger_nonzero"),
        CheckConstraint("balance_after >= 0", name="ck_share_ledger_balance"),
        Index("ix_share_ledger_holding_created", "holding_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    share_class_id: Mapped[str] = mapped_column(ForeignKey("share_classes.id"), index=True)
    holding_id: Mapped[str] = mapped_column(ForeignKey("share_holdings.id"), index=True)
    quantity_delta: Mapped[int] = mapped_column(BigInteger)
    balance_after: Mapped[int] = mapped_column(BigInteger)
    reason: Mapped[str] = mapped_column(String(32))
    reference_type: Mapped[str] = mapped_column(String(32))
    reference_id: Mapped[str] = mapped_column(String(36))
    event_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"
    __table_args__ = (
        UniqueConstraint("trade_id", name="uq_price_snapshot_trade"),
        CheckConstraint("price_cents > 0", name="ck_price_snapshot_price"),
        CheckConstraint("volume > 0", name="ck_price_snapshot_volume"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    listing_id: Mapped[str] = mapped_column(ForeignKey("exchange_listings.id"), index=True)
    trade_id: Mapped[str] = mapped_column(ForeignKey("exchange_trades.id"), unique=True)
    price_cents: Mapped[int] = mapped_column(BigInteger)
    volume: Mapped[int] = mapped_column(BigInteger)
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utcnow,
        index=True,
    )


class DividendDeclaration(Base):
    __tablename__ = "dividend_declarations"
    __table_args__ = (
        UniqueConstraint(
            "declared_by_profile_id",
            "idempotency_key",
            name="uq_dividend_declaration_key",
        ),
        CheckConstraint("per_share_cents > 0", name="ck_dividend_per_share"),
        CheckConstraint("total_paid_cents > 0", name="ck_dividend_total_paid"),
        CheckConstraint("status = 'paid'", name="ck_dividend_paid_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    listing_id: Mapped[str] = mapped_column(ForeignKey("exchange_listings.id"), index=True)
    share_class_id: Mapped[str] = mapped_column(ForeignKey("share_classes.id"))
    declared_by_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id"),
        index=True,
    )
    per_share_cents: Mapped[int] = mapped_column(BigInteger)
    total_paid_cents: Mapped[int] = mapped_column(BigInteger)
    eligible_shares: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(24), default="paid")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DividendEntitlement(Base):
    __tablename__ = "dividend_entitlements"
    __table_args__ = (
        UniqueConstraint(
            "declaration_id",
            "holding_id",
            name="uq_dividend_entitlement_holding",
        ),
        CheckConstraint("quantity > 0", name="ck_dividend_entitlement_quantity"),
        CheckConstraint("amount_cents > 0", name="ck_dividend_entitlement_amount"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    declaration_id: Mapped[str] = mapped_column(
        ForeignKey("dividend_declarations.id"),
        index=True,
    )
    holding_id: Mapped[str] = mapped_column(ForeignKey("share_holdings.id"))
    recipient_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id"),
        index=True,
    )
    quantity: Mapped[int] = mapped_column(BigInteger)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_transactions.id"),
        unique=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Facility(Base):
    __tablename__ = "facilities"
    __table_args__ = (UniqueConstraint("profile_id", "facility_type", name="uq_profile_facility"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    facility_type: Mapped[str] = mapped_column(String(40))
    level: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="active")
    finishes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Specialist(Base):
    __tablename__ = "specialists"
    __table_args__ = (
        CheckConstraint("level BETWEEN 1 AND 10", name="ck_specialist_level"),
        CheckConstraint("energy BETWEEN 0 AND 100", name="ck_specialist_energy"),
        CheckConstraint(
            "experience_points BETWEEN 0 AND 100000",
            name="ck_specialist_experience",
        ),
        CheckConstraint("salary_cents >= 0", name="ck_specialist_salary_cents"),
        CheckConstraint(
            "status IN ('available', 'hired', 'assigned', 'released')",
            name="ck_specialist_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(40))
    level: Mapped[int] = mapped_column(Integer, default=1)
    energy: Mapped[int] = mapped_column(Integer, default=100)
    experience_points: Mapped[int] = mapped_column(Integer, default=0)
    skills_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    competence: Mapped[int] = mapped_column(Integer)
    loyalty: Mapped[int] = mapped_column(Integer)
    ambition: Mapped[int] = mapped_column(Integer)
    stress: Mapped[int] = mapped_column(Integer, default=0)
    exposure: Mapped[int] = mapped_column(Integer, default=0)
    salary: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    salary_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    status: Mapped[str] = mapped_column(String(24), default="available")
    employer_company_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    assigned_operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    hired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SpecialistMarketCandidate(Base):
    __tablename__ = "specialist_market_candidates"
    __table_args__ = (
        UniqueConstraint(
            "world_id",
            "city_id",
            "market_cycle_key",
            "slot_number",
            name="uq_specialist_market_cycle_slot",
        ),
        CheckConstraint(
            "role IN ('finance_director', 'technology_expert', 'market_analyst', "
            "'compliance_officer', 'logistics_expert', 'diplomat')",
            name="ck_specialist_candidate_role",
        ),
        CheckConstraint("level BETWEEN 1 AND 10", name="ck_specialist_candidate_level"),
        CheckConstraint("energy BETWEEN 0 AND 100", name="ck_specialist_candidate_energy"),
        CheckConstraint(
            "loyalty BETWEEN 0 AND 100",
            name="ck_specialist_candidate_loyalty",
        ),
        CheckConstraint(
            "salary_cents > 0",
            name="ck_specialist_candidate_salary",
        ),
        CheckConstraint(
            "status IN ('available', 'hired', 'expired')",
            name="ck_specialist_candidate_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    market_cycle_key: Mapped[str] = mapped_column(String(16))
    slot_number: Mapped[int] = mapped_column(Integer)
    role: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(80))
    level: Mapped[int] = mapped_column(Integer)
    salary_cents: Mapped[int] = mapped_column(BigInteger)
    loyalty: Mapped[int] = mapped_column(Integer)
    energy: Mapped[int] = mapped_column(Integer)
    skills_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    deterministic_seed: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(24), default="available")
    hired_specialist_id: Mapped[str | None] = mapped_column(
        ForeignKey("specialists.id"), nullable=True, unique=True
    )
    available_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SpecialistPayrollTick(Base):
    __tablename__ = "specialist_payroll_ticks"
    __table_args__ = (
        UniqueConstraint("world_id", "period_key", name="uq_specialist_payroll_period"),
        UniqueConstraint("economy_tick_id", name="uq_specialist_payroll_economy_tick"),
        CheckConstraint(
            "status IN ('processing', 'completed')",
            name="ck_specialist_payroll_status",
        ),
        CheckConstraint("specialist_count >= 0", name="ck_specialist_payroll_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    economy_tick_id: Mapped[str] = mapped_column(ForeignKey("economy_ticks.id"))
    period_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="processing")
    specialist_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SpecialistPayrollReport(Base):
    __tablename__ = "specialist_payroll_reports"
    __table_args__ = (
        UniqueConstraint(
            "payroll_tick_id",
            "specialist_id",
            name="uq_specialist_payroll_report",
        ),
        CheckConstraint("salary_due_cents > 0", name="ck_payroll_salary_due"),
        CheckConstraint("salary_paid_cents >= 0", name="ck_payroll_salary_paid"),
        CheckConstraint("unpaid_cents >= 0", name="ck_payroll_unpaid"),
        CheckConstraint(
            "loyalty_before BETWEEN 0 AND 100 AND loyalty_after BETWEEN 0 AND 100",
            name="ck_payroll_loyalty",
        ),
        CheckConstraint(
            "energy_before BETWEEN 0 AND 100 AND energy_after BETWEEN 0 AND 100",
            name="ck_payroll_energy",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    payroll_tick_id: Mapped[str] = mapped_column(
        ForeignKey("specialist_payroll_ticks.id"), index=True
    )
    specialist_id: Mapped[str] = mapped_column(ForeignKey("specialists.id"), index=True)
    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id"), index=True)
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id"), nullable=True, unique=True
    )
    salary_due_cents: Mapped[int] = mapped_column(BigInteger)
    salary_paid_cents: Mapped[int] = mapped_column(BigInteger)
    unpaid_cents: Mapped[int] = mapped_column(BigInteger)
    loyalty_before: Mapped[int] = mapped_column(Integer)
    loyalty_after: Mapped[int] = mapped_column(Integer)
    energy_before: Mapped[int] = mapped_column(Integer)
    energy_after: Mapped[int] = mapped_column(Integer)
    level_before: Mapped[int] = mapped_column(Integer)
    level_after: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AiDecisionTick(Base):
    __tablename__ = "ai_decision_ticks"
    __table_args__ = (
        UniqueConstraint("world_id", "period_key", name="uq_ai_decision_period"),
        CheckConstraint(
            "status IN ('processing', 'completed')",
            name="ck_ai_decision_tick_status",
        ),
        CheckConstraint("profile_count >= 0", name="ck_ai_decision_profile_count"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id"), index=True)
    economy_tick_id: Mapped[str | None] = mapped_column(
        ForeignKey("economy_ticks.id"), nullable=True
    )
    period_key: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(24), default="processing")
    profile_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AiDecision(Base):
    __tablename__ = "ai_decisions"
    __table_args__ = (
        UniqueConstraint("tick_id", "profile_id", name="uq_ai_tick_profile"),
        CheckConstraint(
            "action_type IN ('found_company', 'invest', 'hold')",
            name="ck_ai_decision_action",
        ),
        CheckConstraint(
            "status IN ('completed', 'skipped')",
            name="ck_ai_decision_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tick_id: Mapped[str] = mapped_column(ForeignKey("ai_decision_ticks.id"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24))
    deterministic_seed: Mapped[str] = mapped_column(String(64))
    input_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Operation(Base):
    __tablename__ = "operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    operation_type: Mapped[str] = mapped_column(String(48))
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), index=True)
    specialist_id: Mapped[str] = mapped_column(ForeignKey("specialists.id"))
    target: Mapped[str] = mapped_column(String(120))
    budget: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    intelligence_spend: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    risk_posture: Mapped[str] = mapped_column(String(20))
    secrecy: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(24), default="running")
    result: Mapped[str | None] = mapped_column(String(32), nullable=True)
    outcome_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finishes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class IntelReport(Base):
    __tablename__ = "intel_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(140))
    summary: Mapped[str] = mapped_column(Text)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(36))
    visible_confidence: Mapped[int] = mapped_column(Integer)
    actual_accuracy: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(80))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="new")


class IntelligenceOperation(Base):
    __tablename__ = "intelligence_operations"
    __table_args__ = (
        UniqueConstraint(
            "actor_profile_id",
            "idempotency_key",
            name="uq_intelligence_operation_actor_key",
        ),
        CheckConstraint(
            "information_type IN ('public', 'analyzed', 'covert')",
            name="ck_intelligence_operation_type",
        ),
        CheckConstraint(
            "outcome IN ('success', 'partial', 'failure')",
            name="ck_intelligence_operation_outcome",
        ),
        CheckConstraint(
            "cost_cash_cents >= 0 AND cost_intelligence >= 0",
            name="ck_intelligence_operation_costs",
        ),
        CheckConstraint(
            "success_roll BETWEEN 0 AND 9999 AND detection_roll BETWEEN 0 AND 9999",
            name="ck_intelligence_operation_rolls",
        ),
        CheckConstraint(
            "success_chance_bps BETWEEN 0 AND 10000 AND detection_chance_bps BETWEEN 0 AND 10000",
            name="ck_intelligence_operation_chances",
        ),
        Index(
            "ix_intelligence_operation_actor_target_created",
            "actor_profile_id",
            "target_profile_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    actor_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    target_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    specialist_id: Mapped[str] = mapped_column(
        ForeignKey("specialists.id", ondelete="RESTRICT"), index=True
    )
    information_type: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(48))
    cost_cash_cents: Mapped[int] = mapped_column(BigInteger)
    cost_intelligence: Mapped[int] = mapped_column(BigInteger)
    random_seed: Mapped[str] = mapped_column(String(64))
    success_roll: Mapped[int] = mapped_column(Integer)
    detection_roll: Mapped[int] = mapped_column(Integer)
    success_chance_bps: Mapped[int] = mapped_column(Integer)
    detection_chance_bps: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    detected: Mapped[bool] = mapped_column(Boolean)
    investigation_pressure_delta: Mapped[int] = mapped_column(Integer, default=0)
    report_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    cooldown_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntelligenceReport(Base):
    __tablename__ = "intelligence_reports"
    __table_args__ = (
        CheckConstraint(
            "information_type IN ('public', 'analyzed', 'covert')",
            name="ck_intelligence_report_type",
        ),
        CheckConstraint(
            "accuracy_state IN ('correct', 'incomplete', 'outdated', 'intentionally_misleading')",
            name="ck_intelligence_report_accuracy",
        ),
        CheckConstraint(
            "confidence_bps BETWEEN 0 AND 10000",
            name="ck_intelligence_report_confidence",
        ),
        CheckConstraint(
            "expires_at > observed_at",
            name="ck_intelligence_report_expiry",
        ),
        Index("ix_intelligence_report_owner_created", "owner_profile_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    owner_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    information_type: Mapped[str] = mapped_column(String(24))
    category: Mapped[str] = mapped_column(String(48))
    statement: Mapped[str] = mapped_column(Text)
    confidence_bps: Mapped[int] = mapped_column(Integer)
    accuracy_state: Mapped[str] = mapped_column(String(32))
    source_category: Mapped[str] = mapped_column(String(80))
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    operation_id: Mapped[str | None] = mapped_column(
        ForeignKey("intelligence_operations.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    source_report_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    tradable: Mapped[bool] = mapped_column(Boolean, default=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IntelligenceReportOffer(Base):
    __tablename__ = "intelligence_report_offers"
    __table_args__ = (
        UniqueConstraint(
            "seller_profile_id",
            "idempotency_key",
            name="uq_intelligence_offer_seller_key",
        ),
        UniqueConstraint(
            "buyer_profile_id",
            "purchase_idempotency_key",
            name="uq_intelligence_offer_buyer_purchase_key",
        ),
        CheckConstraint("price_cents > 0", name="ck_intelligence_offer_price"),
        CheckConstraint(
            "status IN ('open', 'sold', 'cancelled', 'expired')",
            name="ck_intelligence_offer_status",
        ),
        Index("ix_intelligence_offer_world_status", "world_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    report_id: Mapped[str] = mapped_column(
        ForeignKey("intelligence_reports.id", ondelete="RESTRICT"), index=True
    )
    seller_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    buyer_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    purchased_report_id: Mapped[str | None] = mapped_column(
        ForeignKey("intelligence_reports.id", ondelete="RESTRICT"), nullable=True, unique=True
    )
    price_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(24), default="open")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    purchase_idempotency_key: Mapped[str | None] = mapped_column(String(80), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    sold_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StrategicAction(Base):
    __tablename__ = "strategic_actions"
    __table_args__ = (
        UniqueConstraint(
            "actor_profile_id",
            "idempotency_key",
            name="uq_strategic_action_actor_key",
        ),
        CheckConstraint(
            "action_type IN "
            "('delay_project', 'weaken_reputation', 'raise_operating_cost', "
            "'make_information_unreliable', 'stress_specialist')",
            name="ck_strategic_action_type",
        ),
        CheckConstraint(
            "outcome IN ('success', 'partial', 'failure')",
            name="ck_strategic_action_outcome",
        ),
        CheckConstraint(
            "cost_cash_cents >= 0 AND cost_intelligence >= 0",
            name="ck_strategic_action_costs",
        ),
        CheckConstraint(
            "success_roll BETWEEN 0 AND 9999 AND detection_roll BETWEEN 0 AND 9999",
            name="ck_strategic_action_rolls",
        ),
        Index(
            "ix_strategic_action_actor_target_created",
            "actor_profile_id",
            "target_profile_id",
            "created_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    actor_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    target_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    specialist_id: Mapped[str] = mapped_column(
        ForeignKey("specialists.id", ondelete="RESTRICT"), index=True
    )
    action_type: Mapped[str] = mapped_column(String(48))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    cost_cash_cents: Mapped[int] = mapped_column(BigInteger)
    cost_intelligence: Mapped[int] = mapped_column(BigInteger)
    random_seed: Mapped[str] = mapped_column(String(64))
    success_roll: Mapped[int] = mapped_column(Integer)
    detection_roll: Mapped[int] = mapped_column(Integer)
    success_chance_bps: Mapped[int] = mapped_column(Integer)
    detection_chance_bps: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    detected: Mapped[bool] = mapped_column(Boolean)
    investigation_pressure_delta: Mapped[int] = mapped_column(Integer, default=0)
    effect_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    cooldown_until: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StrategicEffect(Base):
    __tablename__ = "strategic_effects"
    __table_args__ = (
        CheckConstraint(
            "effect_type IN "
            "('project_delay', 'reputation_penalty', 'operating_cost_increase', "
            "'information_reliability_penalty', 'specialist_stress')",
            name="ck_strategic_effect_type",
        ),
        CheckConstraint("magnitude > 0", name="ck_strategic_effect_magnitude"),
        CheckConstraint("ends_at > starts_at", name="ck_strategic_effect_duration"),
        Index(
            "ix_strategic_effect_target_active",
            "target_type",
            "target_id",
            "starts_at",
            "ends_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    action_id: Mapped[str] = mapped_column(
        ForeignKey("strategic_actions.id", ondelete="RESTRICT"), unique=True
    )
    source_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    target_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    effect_type: Mapped[str] = mapped_column(String(48))
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    magnitude: Mapped[int] = mapped_column(Integer)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    evidence_type: Mapped[str] = mapped_column(String(48))
    strength: Mapped[int] = mapped_column(Integer)
    source_reference: Mapped[str] = mapped_column(String(80))
    internal_only: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("world_id", "name", name="uq_organization_world_name"),
        UniqueConstraint("world_id", "tag", name="uq_organization_world_tag"),
        CheckConstraint("stability BETWEEN 0 AND 100", name="ck_organization_stability"),
        CheckConstraint("member_limit > 0", name="ck_organization_member_limit"),
        CheckConstraint(
            "approval_threshold_cents > 0 AND single_spend_limit_cents >= approval_threshold_cents",
            name="ck_organization_spend_limits",
        ),
        CheckConstraint(
            "status IN ('active', 'dissolved')",
            name="ck_organization_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[str | None] = mapped_column(ForeignKey("cities.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    tag: Mapped[str] = mapped_column(String(8))
    archetype: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(String(500), default="")
    stability: Mapped[int] = mapped_column(Integer, default=70)
    treasury_cash: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    treasury_capital: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("0"))
    member_limit: Mapped[int] = mapped_column(Integer, default=20)
    governance_model: Mapped[str] = mapped_column(String(32), default="autocratic")
    reputation: Mapped[int] = mapped_column(Integer, default=50)
    investigation_pressure: Mapped[int] = mapped_column(Integer, default=0)
    approval_threshold_cents: Mapped[int] = mapped_column(BigInteger, default=250_000)
    single_spend_limit_cents: Mapped[int] = mapped_column(BigInteger, default=2_500_000)
    status: Mapped[str] = mapped_column(String(24), default="active")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    dissolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "profile_id", name="uq_org_profile"),
        Index(
            "uq_active_organization_membership_profile",
            "profile_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
        CheckConstraint(
            "status IN ('active', 'left', 'removed')",
            name="ck_organization_membership_status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), default="member")
    status: Mapped[str] = mapped_column(String(24), default="active")
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrganizationInvite(Base):
    __tablename__ = "organization_invites"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", "status", name="uq_org_email_invite_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), index=True
    )
    invited_by_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"))
    email: Mapped[str] = mapped_column(String(320))
    status: Mapped[str] = mapped_column(String(24), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    declined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CartelExpense(Base):
    __tablename__ = "cartel_expenses"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_cartel_expense_idempotency",
        ),
        CheckConstraint("amount_cents > 0", name="ck_cartel_expense_amount"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_cartel_expense_status",
        ),
        Index("ix_cartel_expense_org_created", "organization_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    requested_by_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    approved_by_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), nullable=True
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    purpose: Mapped[str] = mapped_column(String(240))
    requires_approval: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String(24), default="pending")
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    idempotency_key: Mapped[str] = mapped_column(String(120))
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CartelProject(Base):
    __tablename__ = "cartel_projects"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_cartel_project_idempotency",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')",
            name="ck_cartel_project_status",
        ),
        CheckConstraint(
            "required_cash_cents >= 0 AND required_influence >= 0 AND required_intelligence >= 0",
            name="ck_cartel_project_requirements",
        ),
        CheckConstraint(
            "contributed_cash_cents >= 0 AND contributed_influence >= 0 "
            "AND contributed_intelligence >= 0",
            name="ck_cartel_project_progress",
        ),
        Index("ix_cartel_project_org_status", "organization_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    district_id: Mapped[str] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    project_type: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="active")
    required_cash_cents: Mapped[int] = mapped_column(BigInteger)
    required_influence: Mapped[int] = mapped_column(BigInteger)
    required_intelligence: Mapped[int] = mapped_column(BigInteger)
    contributed_cash_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    contributed_influence: Mapped[int] = mapped_column(BigInteger, default=0)
    contributed_intelligence: Mapped[int] = mapped_column(BigInteger, default=0)
    influence_kind: Mapped[str] = mapped_column(String(24))
    influence_reward: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(120))
    created_by_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT")
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CartelProjectContribution(Base):
    __tablename__ = "cartel_project_contributions"
    __table_args__ = (
        UniqueConstraint(
            "profile_id",
            "idempotency_key",
            name="uq_cartel_project_contribution_idempotency",
        ),
        CheckConstraint(
            "resource_type IN ('cash', 'influence', 'intelligence')",
            name="ck_cartel_project_contribution_resource",
        ),
        CheckConstraint("amount_units > 0", name="ck_cartel_project_contribution_amount"),
        Index("ix_cartel_project_contribution_project", "project_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    project_id: Mapped[str] = mapped_column(
        ForeignKey("cartel_projects.id", ondelete="RESTRICT"), index=True
    )
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    resource_type: Mapped[str] = mapped_column(String(24))
    amount_units: Mapped[int] = mapped_column(BigInteger)
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(120))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CartelDistrictInfluence(Base):
    __tablename__ = "cartel_district_influences"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "district_id",
            "kind",
            name="uq_cartel_district_influence",
        ),
        CheckConstraint("points >= 0", name="ck_cartel_district_influence_nonnegative"),
        Index("ix_cartel_influence_district", "district_id", "points"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    organization_id: Mapped[str] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"), index=True
    )
    district_id: Mapped[str] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    kind: Mapped[str] = mapped_column(String(24))
    points: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Treaty(Base):
    __tablename__ = "treaties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    proposer_org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    recipient_org_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    treaty_type: Mapped[str] = mapped_column(String(40))
    terms_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    visibility: Mapped[str] = mapped_column(String(16), default="public")
    status: Mapped[str] = mapped_column(String(24), default="proposed")
    breach_score: Mapped[int] = mapped_column(Integer, default=0)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ResearchProject(Base):
    __tablename__ = "research_projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    organization_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    research_key: Mapped[str] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(32))
    status: Mapped[str] = mapped_column(String(24), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finishes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WorldEvent(Base):
    __tablename__ = "world_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    event_key: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(24), default="scheduled")
    effects_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class WorldEventDefinition(Base):
    __tablename__ = "world_event_definitions"
    __table_args__ = (
        UniqueConstraint(
            "event_key",
            "version",
            name="uq_world_event_definition_version",
        ),
        CheckConstraint("version > 0", name="ck_world_event_definition_version"),
        CheckConstraint(
            "default_scope_type IN ('world', 'city', 'district', 'industry', 'company')",
            name="ck_world_event_definition_scope",
        ),
        CheckConstraint(
            "default_duration_minutes BETWEEN 1 AND 43200",
            name="ck_world_event_definition_duration",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    event_key: Mapped[str] = mapped_column(String(60), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500))
    default_scope_type: Mapped[str] = mapped_column(String(24))
    default_duration_minutes: Mapped[int] = mapped_column(Integer)
    effect_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WorldEventInstance(Base):
    __tablename__ = "world_event_instances"
    __table_args__ = (
        UniqueConstraint(
            "world_id",
            "idempotency_key",
            name="uq_world_event_instance_key",
        ),
        CheckConstraint(
            "status IN ('scheduled', 'active', 'ended', 'cancelled')",
            name="ck_world_event_instance_status",
        ),
        CheckConstraint(
            "scope_type IN ('world', 'city', 'district', 'industry', 'company')",
            name="ck_world_event_instance_scope",
        ),
        CheckConstraint("template_version > 0", name="ck_world_event_instance_version"),
        CheckConstraint("ends_at > starts_at", name="ck_world_event_instance_duration"),
        Index(
            "ix_world_event_instance_active",
            "world_id",
            "status",
            "starts_at",
            "ends_at",
        ),
        Index(
            "ix_world_event_instance_scope",
            "scope_type",
            "scope_id",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    definition_id: Mapped[str] = mapped_column(
        ForeignKey("world_event_definitions.id", ondelete="RESTRICT"), index=True
    )
    event_key: Mapped[str] = mapped_column(String(60), index=True)
    template_version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(24), default="scheduled")
    scope_type: Mapped[str] = mapped_column(String(24))
    scope_id: Mapped[str] = mapped_column(String(60), index=True)
    effect_config_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    activated_by_user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(240), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeasonTemplate(Base):
    __tablename__ = "season_templates"
    __table_args__ = (
        UniqueConstraint("template_key", "version", name="uq_season_template_version"),
        CheckConstraint("version > 0", name="ck_season_template_version"),
        CheckConstraint(
            "duration_minutes BETWEEN 5 AND 201600",
            name="ck_season_template_duration",
        ),
        CheckConstraint("starting_cash_cents >= 0", name="ck_season_template_starting_cash"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    template_key: Mapped[str] = mapped_column(String(60), index=True)
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    phase_weights_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    goals_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    scoring_categories_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    starting_cash_cents: Mapped[int] = mapped_column(BigInteger)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (
        UniqueConstraint("world_id", "season_number", name="uq_season_world_number"),
        UniqueConstraint("world_id", "idempotency_key", name="uq_season_creation_key"),
        CheckConstraint("season_number >= 0", name="ck_season_number"),
        CheckConstraint(
            "phase IN ('setup', 'early', 'mid', 'late', 'scoring', 'archived')",
            name="ck_season_phase",
        ),
        CheckConstraint(
            "status IN ('active', 'scoring', 'archived')",
            name="ck_season_status",
        ),
        CheckConstraint("ends_at > starts_at", name="ck_season_duration"),
        Index("ix_season_world_status", "world_id", "status", "starts_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    template_id: Mapped[str] = mapped_column(
        ForeignKey("season_templates.id", ondelete="RESTRICT"), index=True
    )
    season_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    phase: Mapped[str] = mapped_column(String(16), default="setup")
    status: Mapped[str] = mapped_column(String(16), default="active")
    goals_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    scoring_categories_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    phase_schedule_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    starting_cash_cents: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    phase_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    scoring_started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeasonScoreSnapshot(Base):
    __tablename__ = "season_score_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "category",
            "entity_type",
            "entity_id",
            name="uq_season_score_entity",
        ),
        CheckConstraint("score_value >= 0", name="ck_season_score_nonnegative"),
        CheckConstraint("rank > 0", name="ck_season_score_rank"),
        Index("ix_season_score_category_rank", "season_id", "category", "rank"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    season_id: Mapped[str] = mapped_column(
        ForeignKey("seasons.id", ondelete="RESTRICT"), index=True
    )
    category: Mapped[str] = mapped_column(String(48), index=True)
    entity_type: Mapped[str] = mapped_column(String(24))
    entity_id: Mapped[str] = mapped_column(String(36))
    entity_name: Mapped[str] = mapped_column(String(140))
    score_value: Mapped[int] = mapped_column(BigInteger)
    rank: Mapped[int] = mapped_column(Integer)
    tied: Mapped[bool] = mapped_column(Boolean, default=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    tie_break_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class HallOfFameEntry(Base):
    __tablename__ = "hall_of_fame_entries"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "category",
            "entity_type",
            "entity_id",
            name="uq_hall_of_fame_entity",
        ),
        CheckConstraint("rank BETWEEN 1 AND 3", name="ck_hall_of_fame_rank"),
        CheckConstraint("score_value >= 0", name="ck_hall_of_fame_score"),
        Index("ix_hall_of_fame_category_season", "category", "season_id", "rank"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    season_id: Mapped[str] = mapped_column(
        ForeignKey("seasons.id", ondelete="RESTRICT"), index=True
    )
    season_number: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(48), index=True)
    entity_type: Mapped[str] = mapped_column(String(24))
    entity_id: Mapped[str] = mapped_column(String(36))
    entity_name: Mapped[str] = mapped_column(String(140))
    score_value: Mapped[int] = mapped_column(BigInteger)
    rank: Mapped[int] = mapped_column(Integer)
    tied: Mapped[bool] = mapped_column(Boolean, default=False)
    metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AccountReward(Base):
    __tablename__ = "account_rewards"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "season_id",
            "reward_type",
            "reward_key",
            name="uq_account_season_reward",
        ),
        CheckConstraint(
            "reward_type IN ('achievement', 'title', 'cosmetic')",
            name="ck_account_reward_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    season_id: Mapped[str] = mapped_column(
        ForeignKey("seasons.id", ondelete="RESTRICT"), index=True
    )
    reward_type: Mapped[str] = mapped_column(String(24))
    reward_key: Mapped[str] = mapped_column(String(80))
    label: Mapped[str] = mapped_column(String(140))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    awarded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SeasonArchiveSnapshot(Base):
    __tablename__ = "season_archive_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "season_id",
            "entity_type",
            "entity_id",
            name="uq_season_archive_entity",
        ),
        Index("ix_season_archive_type", "season_id", "entity_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    season_id: Mapped[str] = mapped_column(
        ForeignKey("seasons.id", ondelete="RESTRICT"), index=True
    )
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(60))
    snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    archived_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContractTender(Base):
    __tablename__ = "contract_tenders"
    __table_args__ = (
        UniqueConstraint(
            "issuer_company_id",
            "idempotency_key",
            name="uq_contract_tender_issuer_key",
        ),
        CheckConstraint(
            "contract_type IN ('supply', 'service')",
            name="ck_contract_tender_type",
        ),
        CheckConstraint(
            "status IN ('open', 'awarded', 'cancelled', 'expired')",
            name="ck_contract_tender_status",
        ),
        CheckConstraint("max_price_cents > 0", name="ck_contract_tender_price"),
        CheckConstraint(
            "duration_periods BETWEEN 1 AND 720",
            name="ck_contract_tender_periods",
        ),
        CheckConstraint("capacity_units > 0", name="ck_contract_tender_capacity"),
        CheckConstraint(
            "min_reputation_bps BETWEEN 0 AND 10000",
            name="ck_contract_tender_reputation",
        ),
        CheckConstraint(
            "min_compliance_bps BETWEEN 0 AND 10000",
            name="ck_contract_tender_compliance",
        ),
        Index("ix_contract_tender_world_status", "world_id", "status", "submission_ends_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    issuer_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    created_by_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    contract_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(140))
    description: Mapped[str] = mapped_column(String(500))
    max_price_cents: Mapped[int] = mapped_column(BigInteger)
    duration_periods: Mapped[int] = mapped_column(Integer)
    capacity_units: Mapped[int] = mapped_column(Integer)
    min_reputation_bps: Mapped[int] = mapped_column(Integer, default=0)
    min_compliance_bps: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="open")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    submission_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    awarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContractBid(Base):
    __tablename__ = "contract_bids"
    __table_args__ = (
        UniqueConstraint("tender_id", "bidder_company_id", name="uq_contract_bid_company"),
        UniqueConstraint(
            "bidder_company_id",
            "idempotency_key",
            name="uq_contract_bid_company_key",
        ),
        CheckConstraint(
            "status IN ('submitted', 'won', 'lost', 'withdrawn')",
            name="ck_contract_bid_status",
        ),
        CheckConstraint("price_cents > 0", name="ck_contract_bid_price"),
        CheckConstraint("capacity_units > 0", name="ck_contract_bid_capacity"),
        CheckConstraint("score_points >= 0", name="ck_contract_bid_score"),
        Index("ix_contract_bid_tender_score", "tender_id", "score_points", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    tender_id: Mapped[str] = mapped_column(
        ForeignKey("contract_tenders.id", ondelete="RESTRICT"), index=True
    )
    bidder_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    submitted_by_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    price_cents: Mapped[int] = mapped_column(BigInteger)
    capacity_units: Mapped[int] = mapped_column(Integer)
    score_points: Mapped[int] = mapped_column(Integer)
    score_breakdown_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="submitted")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CommercialContract(Base):
    __tablename__ = "commercial_contracts"
    __table_args__ = (
        UniqueConstraint("tender_id", name="uq_commercial_contract_tender"),
        UniqueConstraint(
            "issuer_company_id",
            "idempotency_key",
            name="uq_commercial_contract_issuer_key",
        ),
        CheckConstraint(
            "contract_type IN ('supply', 'service')",
            name="ck_commercial_contract_type",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'breached', 'cancelled')",
            name="ck_commercial_contract_status",
        ),
        CheckConstraint("price_cents_per_period > 0", name="ck_commercial_contract_price"),
        CheckConstraint(
            "duration_periods BETWEEN 1 AND 720",
            name="ck_commercial_contract_periods",
        ),
        CheckConstraint(
            "periods_settled BETWEEN 0 AND duration_periods",
            name="ck_commercial_contract_settled",
        ),
        CheckConstraint(
            "reserved_capacity_units > 0",
            name="ck_commercial_contract_capacity",
        ),
        CheckConstraint("ends_at > starts_at", name="ck_commercial_contract_duration"),
        Index(
            "ix_commercial_contract_due",
            "world_id",
            "status",
            "next_settlement_at",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    tender_id: Mapped[str] = mapped_column(
        ForeignKey("contract_tenders.id", ondelete="RESTRICT"), unique=True
    )
    bid_id: Mapped[str] = mapped_column(
        ForeignKey("contract_bids.id", ondelete="RESTRICT"), unique=True
    )
    issuer_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    provider_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    contract_type: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(140))
    price_cents_per_period: Mapped[int] = mapped_column(BigInteger)
    duration_periods: Mapped[int] = mapped_column(Integer)
    periods_settled: Mapped[int] = mapped_column(Integer, default=0)
    reserved_capacity_units: Mapped[int] = mapped_column(Integer)
    reputation_reward_bps: Mapped[int] = mapped_column(Integer, default=250)
    status: Mapped[str] = mapped_column(String(20), default="active")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_settlement_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    breach_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ContractSettlement(Base):
    __tablename__ = "contract_settlements"
    __table_args__ = (
        UniqueConstraint(
            "contract_id",
            "period_number",
            name="uq_contract_settlement_period",
        ),
        CheckConstraint("period_number > 0", name="ck_contract_settlement_period"),
        CheckConstraint("amount_cents > 0", name="ck_contract_settlement_amount"),
        CheckConstraint(
            "status IN ('paid', 'defaulted')",
            name="ck_contract_settlement_status",
        ),
        CheckConstraint(
            "(status = 'paid' AND transaction_id IS NOT NULL) OR "
            "(status = 'defaulted' AND transaction_id IS NULL)",
            name="ck_contract_settlement_transaction",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    contract_id: Mapped[str] = mapped_column(
        ForeignKey("commercial_contracts.id", ondelete="RESTRICT"), index=True
    )
    period_number: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LoanApplication(Base):
    __tablename__ = "loan_applications"
    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_loan_application_company_key",
        ),
        CheckConstraint("requested_principal_cents > 0", name="ck_loan_application_principal"),
        CheckConstraint(
            "term_periods BETWEEN 1 AND 720",
            name="ck_loan_application_term",
        ),
        CheckConstraint(
            "collateral_score_bps BETWEEN 0 AND 10000",
            name="ck_loan_application_collateral",
        ),
        CheckConstraint(
            "status IN ('offered', 'rejected', 'accepted', 'cancelled')",
            name="ck_loan_application_status",
        ),
        CheckConstraint(
            "(status = 'rejected' AND offered_interest_rate_bps IS NULL "
            "AND offered_installment_cents IS NULL) OR "
            "(status != 'rejected' AND offered_interest_rate_bps IS NOT NULL "
            "AND offered_installment_cents IS NOT NULL)",
            name="ck_loan_application_offer",
        ),
        Index("ix_loan_application_world_status", "world_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    applicant_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    requested_principal_cents: Mapped[int] = mapped_column(BigInteger)
    term_periods: Mapped[int] = mapped_column(Integer)
    collateral_score_bps: Mapped[int] = mapped_column(Integer)
    purpose: Mapped[str] = mapped_column(String(240))
    offered_interest_rate_bps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offered_installment_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    offered_total_repayment_cents: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    rejection_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    risk_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    offer_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CompanyLoan(Base):
    __tablename__ = "company_loans"
    __table_args__ = (
        UniqueConstraint("application_id", name="uq_company_loan_application"),
        UniqueConstraint(
            "company_id",
            "idempotency_key",
            name="uq_company_loan_company_key",
        ),
        CheckConstraint("principal_cents > 0", name="ck_company_loan_principal"),
        CheckConstraint("interest_rate_bps >= 0", name="ck_company_loan_interest_rate"),
        CheckConstraint("total_interest_cents >= 0", name="ck_company_loan_interest"),
        CheckConstraint(
            "total_repayment_cents = principal_cents + total_interest_cents",
            name="ck_company_loan_total",
        ),
        CheckConstraint(
            "scheduled_installment_cents > 0",
            name="ck_company_loan_installment",
        ),
        CheckConstraint(
            "term_periods BETWEEN 1 AND 720",
            name="ck_company_loan_term",
        ),
        CheckConstraint(
            "payments_made BETWEEN 0 AND term_periods",
            name="ck_company_loan_payments",
        ),
        CheckConstraint(
            "outstanding_principal_cents BETWEEN 0 AND principal_cents",
            name="ck_company_loan_outstanding_principal",
        ),
        CheckConstraint(
            "outstanding_interest_cents BETWEEN 0 AND total_interest_cents",
            name="ck_company_loan_outstanding_interest",
        ),
        CheckConstraint(
            "collateral_score_bps BETWEEN 0 AND 10000",
            name="ck_company_loan_collateral",
        ),
        CheckConstraint(
            "status IN ('active', 'repaid', 'defaulted', 'cancelled')",
            name="ck_company_loan_status",
        ),
        CheckConstraint("ends_at > starts_at", name="ck_company_loan_duration"),
        Index("ix_company_loan_due", "world_id", "status", "next_payment_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    application_id: Mapped[str] = mapped_column(
        ForeignKey("loan_applications.id", ondelete="RESTRICT"), unique=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    borrower_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    principal_cents: Mapped[int] = mapped_column(BigInteger)
    interest_rate_bps: Mapped[int] = mapped_column(Integer)
    total_interest_cents: Mapped[int] = mapped_column(BigInteger)
    total_repayment_cents: Mapped[int] = mapped_column(BigInteger)
    scheduled_installment_cents: Mapped[int] = mapped_column(BigInteger)
    term_periods: Mapped[int] = mapped_column(Integer)
    payments_made: Mapped[int] = mapped_column(Integer, default=0)
    outstanding_principal_cents: Mapped[int] = mapped_column(BigInteger)
    outstanding_interest_cents: Mapped[int] = mapped_column(BigInteger)
    collateral_score_bps: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="active")
    default_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    disbursement_transaction_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), unique=True
    )
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_payment_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    repaid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    defaulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LoanPayment(Base):
    __tablename__ = "loan_payments"
    __table_args__ = (
        UniqueConstraint("loan_id", "period_number", name="uq_loan_payment_period"),
        CheckConstraint("period_number > 0", name="ck_loan_payment_period"),
        CheckConstraint("amount_cents > 0", name="ck_loan_payment_amount"),
        CheckConstraint("principal_cents >= 0", name="ck_loan_payment_principal"),
        CheckConstraint("interest_cents >= 0", name="ck_loan_payment_interest"),
        CheckConstraint(
            "amount_cents = principal_cents + interest_cents",
            name="ck_loan_payment_components",
        ),
        CheckConstraint(
            "status IN ('paid', 'defaulted')",
            name="ck_loan_payment_status",
        ),
        CheckConstraint(
            "(status = 'paid' AND transaction_id IS NOT NULL) OR "
            "(status = 'defaulted' AND transaction_id IS NULL)",
            name="ck_loan_payment_transaction",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    loan_id: Mapped[str] = mapped_column(
        ForeignKey("company_loans.id", ondelete="RESTRICT"), index=True
    )
    period_number: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    principal_cents: Mapped[int] = mapped_column(BigInteger)
    interest_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BondIssue(Base):
    __tablename__ = "bond_issues"
    __table_args__ = (
        UniqueConstraint("world_id", "symbol", name="uq_bond_issue_world_symbol"),
        UniqueConstraint(
            "issuer_company_id",
            "idempotency_key",
            name="uq_bond_issue_company_key",
        ),
        CheckConstraint("face_value_cents > 0", name="ck_bond_issue_face_value"),
        CheckConstraint("total_units > 0", name="ck_bond_issue_total_units"),
        CheckConstraint(
            "sold_units BETWEEN 0 AND total_units",
            name="ck_bond_issue_sold_units",
        ),
        CheckConstraint(
            "coupon_rate_bps BETWEEN 1 AND 20000",
            name="ck_bond_issue_coupon_rate",
        ),
        CheckConstraint(
            "term_periods BETWEEN 1 AND 720",
            name="ck_bond_issue_term",
        ),
        CheckConstraint(
            "coupons_paid BETWEEN 0 AND term_periods",
            name="ck_bond_issue_coupons_paid",
        ),
        CheckConstraint(
            "status IN ('offering', 'active', 'repaid', 'defaulted', 'cancelled')",
            name="ck_bond_issue_status",
        ),
        CheckConstraint(
            "(status = 'offering' AND starts_at IS NULL AND ends_at IS NULL "
            "AND next_coupon_at IS NULL) OR status = 'cancelled' OR "
            "(status IN ('active', 'repaid', 'defaulted') "
            "AND starts_at IS NOT NULL AND ends_at IS NOT NULL "
            "AND next_coupon_at IS NOT NULL)",
            name="ck_bond_issue_schedule",
        ),
        Index("ix_bond_issue_due", "world_id", "status", "next_coupon_at"),
        Index("ix_bond_issue_offering", "world_id", "status", "offering_ends_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    issuer_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    created_by_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    symbol: Mapped[str] = mapped_column(String(12))
    title: Mapped[str] = mapped_column(String(140))
    face_value_cents: Mapped[int] = mapped_column(BigInteger)
    total_units: Mapped[int] = mapped_column(Integer)
    sold_units: Mapped[int] = mapped_column(Integer, default=0)
    coupon_rate_bps: Mapped[int] = mapped_column(Integer)
    term_periods: Mapped[int] = mapped_column(Integer)
    coupons_paid: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="offering")
    default_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    offering_ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_coupon_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    repaid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    defaulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BondSubscription(Base):
    __tablename__ = "bond_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "subscriber_profile_id",
            "idempotency_key",
            name="uq_bond_subscription_profile_key",
        ),
        CheckConstraint("quantity > 0", name="ck_bond_subscription_quantity"),
        CheckConstraint("amount_cents > 0", name="ck_bond_subscription_amount"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    issue_id: Mapped[str] = mapped_column(
        ForeignKey("bond_issues.id", ondelete="RESTRICT"), index=True
    )
    subscriber_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BondHolding(Base):
    __tablename__ = "bond_holdings"
    __table_args__ = (
        UniqueConstraint("issue_id", "profile_id", name="uq_bond_holding_profile"),
        CheckConstraint("quantity >= 0", name="ck_bond_holding_quantity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    issue_id: Mapped[str] = mapped_column(
        ForeignKey("bond_issues.id", ondelete="RESTRICT"), index=True
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    quantity: Mapped[int] = mapped_column(Integer)
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class BondLedgerEntry(Base):
    __tablename__ = "bond_ledger_entries"
    __table_args__ = (
        CheckConstraint("quantity_delta != 0", name="ck_bond_ledger_quantity"),
        CheckConstraint(
            "entry_type IN ('subscription', 'redemption')",
            name="ck_bond_ledger_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    issue_id: Mapped[str] = mapped_column(
        ForeignKey("bond_issues.id", ondelete="RESTRICT"), index=True
    )
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    quantity_delta: Mapped[int] = mapped_column(Integer)
    balance_after: Mapped[int] = mapped_column(Integer)
    entry_type: Mapped[str] = mapped_column(String(20))
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), unique=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BondSettlement(Base):
    __tablename__ = "bond_settlements"
    __table_args__ = (
        UniqueConstraint(
            "issue_id",
            "period_number",
            "profile_id",
            "payment_type",
            name="uq_bond_settlement_holder_period",
        ),
        CheckConstraint("period_number > 0", name="ck_bond_settlement_period"),
        CheckConstraint("quantity > 0", name="ck_bond_settlement_quantity"),
        CheckConstraint("amount_cents > 0", name="ck_bond_settlement_amount"),
        CheckConstraint(
            "payment_type IN ('coupon', 'redemption')",
            name="ck_bond_settlement_type",
        ),
        CheckConstraint(
            "status IN ('paid', 'defaulted')",
            name="ck_bond_settlement_status",
        ),
        CheckConstraint(
            "(status = 'paid' AND transaction_id IS NOT NULL) OR "
            "(status = 'defaulted' AND transaction_id IS NULL)",
            name="ck_bond_settlement_transaction",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    issue_id: Mapped[str] = mapped_column(
        ForeignKey("bond_issues.id", ondelete="RESTRICT"), index=True
    )
    period_number: Mapped[int] = mapped_column(Integer)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    payment_type: Mapped[str] = mapped_column(String(20))
    quantity: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    settled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RealEstateDistrictIndex(Base):
    __tablename__ = "real_estate_district_indices"
    __table_args__ = (
        UniqueConstraint("world_id", "district_id", name="uq_real_estate_index_district"),
        CheckConstraint(
            "price_index_bps BETWEEN 2500 AND 30000",
            name="ck_real_estate_index_price",
        ),
        CheckConstraint(
            "rent_index_bps BETWEEN 2500 AND 30000",
            name="ck_real_estate_index_rent",
        ),
        CheckConstraint(
            "demand_bps BETWEEN 0 AND 20000",
            name="ck_real_estate_index_demand",
        ),
        CheckConstraint(
            "event_multiplier_bps BETWEEN 2500 AND 30000",
            name="ck_real_estate_index_event",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id", ondelete="RESTRICT"), index=True)
    district_id: Mapped[str] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    price_index_bps: Mapped[int] = mapped_column(Integer, default=10_000)
    rent_index_bps: Mapped[int] = mapped_column(Integer, default=10_000)
    demand_bps: Mapped[int] = mapped_column(Integer, default=10_000)
    safety_score: Mapped[int] = mapped_column(Integer)
    infrastructure_score: Mapped[int] = mapped_column(Integer)
    economic_score: Mapped[int] = mapped_column(Integer)
    cartel_control_points: Mapped[int] = mapped_column(Integer, default=0)
    event_multiplier_bps: Mapped[int] = mapped_column(Integer, default=10_000)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class RealEstateIndexSnapshot(Base):
    __tablename__ = "real_estate_index_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "district_index_id",
            "period_key",
            name="uq_real_estate_snapshot_period",
        ),
        CheckConstraint(
            "price_index_bps BETWEEN 2500 AND 30000",
            name="ck_real_estate_snapshot_price",
        ),
        CheckConstraint(
            "rent_index_bps BETWEEN 2500 AND 30000",
            name="ck_real_estate_snapshot_rent",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    district_index_id: Mapped[str] = mapped_column(
        ForeignKey("real_estate_district_indices.id", ondelete="RESTRICT"),
        index=True,
    )
    period_key: Mapped[str] = mapped_column(String(24))
    price_index_bps: Mapped[int] = mapped_column(Integer)
    rent_index_bps: Mapped[int] = mapped_column(Integer)
    inputs_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RealEstateProperty(Base):
    __tablename__ = "real_estate_properties"
    __table_args__ = (
        UniqueConstraint("world_id", "property_code", name="uq_property_world_code"),
        CheckConstraint(
            "property_type IN ('land', 'building', 'commercial_space', 'headquarters')",
            name="ck_property_type",
        ),
        CheckConstraint("area_units > 0", name="ck_property_area"),
        CheckConstraint("base_value_cents > 0", name="ck_property_base_value"),
        CheckConstraint("improvement_value_cents >= 0", name="ck_property_improvement"),
        CheckConstraint(
            "status IN ('available', 'owned', 'leased', 'archived')",
            name="ck_property_status",
        ),
        CheckConstraint(
            "listing_type IS NULL OR listing_type IN ('sale', 'rent')",
            name="ck_property_listing_type",
        ),
        CheckConstraint("asking_price_cents >= 0", name="ck_property_asking_price"),
        CheckConstraint("rent_cents_per_period >= 0", name="ck_property_rent"),
        CheckConstraint(
            "headquarters_level BETWEEN 0 AND 10",
            name="ck_property_hq_level",
        ),
        CheckConstraint(
            "(owner_profile_id IS NULL AND status = 'available') OR "
            "(owner_profile_id IS NOT NULL AND status != 'available')",
            name="ck_property_owner_status",
        ),
        Index("ix_property_market", "world_id", "status", "listing_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id", ondelete="RESTRICT"), index=True)
    district_id: Mapped[str] = mapped_column(
        ForeignKey("districts.id", ondelete="RESTRICT"), index=True
    )
    property_code: Mapped[str] = mapped_column(String(80))
    property_type: Mapped[str] = mapped_column(String(24))
    name: Mapped[str] = mapped_column(String(140))
    area_units: Mapped[int] = mapped_column(Integer)
    base_value_cents: Mapped[int] = mapped_column(BigInteger)
    improvement_value_cents: Mapped[int] = mapped_column(BigInteger, default=0)
    owner_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    company_use_id: Mapped[str | None] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="available")
    listing_type: Mapped[str | None] = mapped_column(String(12), nullable=True)
    asking_price_cents: Mapped[int] = mapped_column(BigInteger)
    rent_cents_per_period: Mapped[int] = mapped_column(BigInteger, default=0)
    headquarters_level: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class PropertyTransfer(Base):
    __tablename__ = "property_transfers"
    __table_args__ = (
        CheckConstraint("price_cents > 0", name="ck_property_transfer_price"),
        CheckConstraint(
            "transfer_type IN ('system_sale', 'resale')",
            name="ck_property_transfer_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    property_id: Mapped[str] = mapped_column(
        ForeignKey("real_estate_properties.id", ondelete="RESTRICT"), index=True
    )
    seller_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    buyer_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    price_cents: Mapped[int] = mapped_column(BigInteger)
    price_index_bps: Mapped[int] = mapped_column(Integer)
    transfer_type: Mapped[str] = mapped_column(String(20))
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PropertyLease(Base):
    __tablename__ = "property_leases"
    __table_args__ = (
        CheckConstraint("rent_cents_per_period > 0", name="ck_property_lease_rent"),
        CheckConstraint(
            "term_periods BETWEEN 2 AND 720",
            name="ck_property_lease_term",
        ),
        CheckConstraint(
            "periods_paid BETWEEN 1 AND term_periods",
            name="ck_property_lease_paid",
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'defaulted', 'cancelled')",
            name="ck_property_lease_status",
        ),
        CheckConstraint("ends_at > starts_at", name="ck_property_lease_duration"),
        Index("ix_property_lease_due", "world_id", "status", "next_payment_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="RESTRICT"), index=True)
    property_id: Mapped[str] = mapped_column(
        ForeignKey("real_estate_properties.id", ondelete="RESTRICT"), index=True
    )
    landlord_profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="RESTRICT"), index=True
    )
    tenant_company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    rent_cents_per_period: Mapped[int] = mapped_column(BigInteger)
    term_periods: Mapped[int] = mapped_column(Integer)
    periods_paid: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="active")
    default_reason: Mapped[str | None] = mapped_column(String(160), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    next_payment_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    defaulted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PropertyLeasePayment(Base):
    __tablename__ = "property_lease_payments"
    __table_args__ = (
        UniqueConstraint(
            "lease_id",
            "period_number",
            name="uq_property_lease_payment_period",
        ),
        CheckConstraint("period_number > 0", name="ck_property_lease_payment_period"),
        CheckConstraint("amount_cents > 0", name="ck_property_lease_payment_amount"),
        CheckConstraint(
            "status IN ('paid', 'defaulted')",
            name="ck_property_lease_payment_status",
        ),
        CheckConstraint(
            "(status = 'paid' AND transaction_id IS NOT NULL) OR "
            "(status = 'defaulted' AND transaction_id IS NULL)",
            name="ck_property_lease_payment_transaction",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    lease_id: Mapped[str] = mapped_column(
        ForeignKey("property_leases.id", ondelete="RESTRICT"), index=True
    )
    period_number: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(20))
    transaction_id: Mapped[str | None] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
    )
    input_snapshot_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PropertyImprovement(Base):
    __tablename__ = "property_improvements"
    __table_args__ = (
        UniqueConstraint(
            "property_id",
            "level_after",
            name="uq_property_improvement_level",
        ),
        CheckConstraint(
            "improvement_type = 'headquarters_upgrade'",
            name="ck_property_improvement_type",
        ),
        CheckConstraint("level_after > 0", name="ck_property_improvement_level"),
        CheckConstraint("cost_cents > 0", name="ck_property_improvement_cost"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    property_id: Mapped[str] = mapped_column(
        ForeignKey("real_estate_properties.id", ondelete="RESTRICT"), index=True
    )
    company_id: Mapped[str] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), index=True
    )
    improvement_type: Mapped[str] = mapped_column(String(32))
    level_after: Mapped[int] = mapped_column(Integer)
    cost_cents: Mapped[int] = mapped_column(BigInteger)
    transaction_id: Mapped[str] = mapped_column(
        ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), unique=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notification_user_read_created", "user_id", "read_at", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    title: Mapped[str] = mapped_column(String(140))
    body: Mapped[str] = mapped_column(String(500))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_actor_created", "actor_user_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(36))
    request_id: Mapped[str] = mapped_column(String(60))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (
        UniqueConstraint("user_id", "key", "scope", name="uq_user_idempotency_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(80))
    scope: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(36))
    response_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CityMarket(Base):
    __tablename__ = "city_markets"
    __table_args__ = (UniqueConstraint("city_id", "resource_key", name="uq_city_market_resource"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)
    resource_key: Mapped[str] = mapped_column(String(40))
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("100"))
    supply: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("1000"))
    demand: Mapped[Decimal] = mapped_column(Numeric(18, 2), default=Decimal("1000"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class PvpOperation(Base):
    __tablename__ = "pvp_operations"
    __table_args__ = (
        UniqueConstraint("attacker_profile_id", "idempotency_key", name="uq_pvp_attacker_key"),
        Index("ix_pvp_world_status_resolves", "world_id", "status", "resolves_at"),
        Index("ix_pvp_defender_created", "defender_profile_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    attacker_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    attacker_cartel_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    defender_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    defender_cartel_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    operation_type: Mapped[str] = mapped_column(String(48))
    target_type: Mapped[str] = mapped_column(String(32), default="profile")
    target_id: Mapped[str] = mapped_column(String(36))
    district_id: Mapped[str | None] = mapped_column(ForeignKey("districts.id"), nullable=True)
    risk_posture: Mapped[str] = mapped_column(String(20), default="balanced")
    status: Mapped[str] = mapped_column(String(24), default="warning")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    warning_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    response_deadline_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolves_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attacker_commitment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    defender_commitment: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    attacker_report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    defender_report_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(80))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class PvpOperationParticipant(Base):
    __tablename__ = "pvp_operation_participants"
    __table_args__ = (UniqueConstraint("operation_id", "profile_id", name="uq_pvp_participant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("pvp_operations.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    cartel_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    side: Mapped[str] = mapped_column(String(16))
    contribution_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PvpDefenseAction(Base):
    __tablename__ = "pvp_defense_actions"
    __table_args__ = (
        UniqueConstraint("operation_id", "profile_id", name="uq_pvp_defense_profile"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("pvp_operations.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    action_type: Mapped[str] = mapped_column(String(48))
    commitment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PvpReport(Base):
    __tablename__ = "pvp_reports"
    __table_args__ = (UniqueConstraint("operation_id", "profile_id", name="uq_pvp_report_side"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    operation_id: Mapped[str] = mapped_column(
        ForeignKey("pvp_operations.id", ondelete="CASCADE"), index=True
    )
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    perspective: Mapped[str] = mapped_column(String(16))
    summary: Mapped[str] = mapped_column(String(500))
    confidence: Mapped[int] = mapped_column(Integer, default=50)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PvpCooldown(Base):
    __tablename__ = "pvp_cooldowns"
    __table_args__ = (
        UniqueConstraint(
            "attacker_profile_id", "defender_profile_id", "cooldown_type", name="uq_pvp_cooldown"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    attacker_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    defender_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    cooldown_type: Mapped[str] = mapped_column(String(32), default="direct_target")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PvpProtectionState(Base):
    __tablename__ = "pvp_protection_states"
    __table_args__ = (Index("ix_pvp_protection_profile_until", "profile_id", "protected_until"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    protection_type: Mapped[str] = mapped_column(String(32))
    reason: Mapped[str] = mapped_column(String(80))
    protected_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    offensive_lock: Mapped[bool] = mapped_column(Boolean, default=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PvpReputation(Base):
    __tablename__ = "pvp_reputation"

    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), primary_key=True
    )
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    reliability: Mapped[int] = mapped_column(Integer, default=50)
    economic_strength: Mapped[int] = mapped_column(Integer, default=0)
    diplomacy: Mapped[int] = mapped_column(Integer, default=50)
    aggression: Mapped[int] = mapped_column(Integer, default=0)
    defense: Mapped[int] = mapped_column(Integer, default=0)
    stability: Mapped[int] = mapped_column(Integer, default=50)
    treaty_breaches: Mapped[int] = mapped_column(Integer, default=0)
    attack_count: Mapped[int] = mapped_column(Integer, default=0)
    defense_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CartelWar(Base):
    __tablename__ = "cartel_wars"
    __table_args__ = (Index("ix_cartel_war_world_status", "world_id", "war_status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    attacker_cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    defender_cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    war_type: Mapped[str] = mapped_column(String(40), default="district_control")
    war_status: Mapped[str] = mapped_column(String(24), default="ultimatum")
    city_id: Mapped[str | None] = mapped_column(ForeignKey("cities.id"), nullable=True, index=True)
    objective_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    rules_config: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    declaration_reason: Mapped[str] = mapped_column(String(500), default="")
    preparation_starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active_starts_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    active_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    aftermath_ends_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attacker_score: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    defender_score: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    winner_cartel_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    resolution_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CartelWarParticipant(Base):
    __tablename__ = "cartel_war_participants"
    __table_args__ = (UniqueConstraint("war_id", "profile_id", name="uq_war_participant"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    war_id: Mapped[str] = mapped_column(
        ForeignKey("cartel_wars.id", ondelete="CASCADE"), index=True
    )
    cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    side: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(24), default="active")
    contribution_score: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CartelWarObjective(Base):
    __tablename__ = "cartel_war_objectives"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    war_id: Mapped[str] = mapped_column(
        ForeignKey("cartel_wars.id", ondelete="CASCADE"), index=True
    )
    objective_type: Mapped[str] = mapped_column(String(40))
    district_id: Mapped[str | None] = mapped_column(ForeignKey("districts.id"), nullable=True)
    target_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("100"))
    progress_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CartelWarOperation(Base):
    __tablename__ = "cartel_war_operations"
    __table_args__ = (
        UniqueConstraint("profile_id", "idempotency_key", name="uq_war_operation_profile_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    war_id: Mapped[str] = mapped_column(
        ForeignKey("cartel_wars.id", ondelete="CASCADE"), index=True
    )
    cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    operation_type: Mapped[str] = mapped_column(String(48))
    district_id: Mapped[str | None] = mapped_column(ForeignKey("districts.id"), nullable=True)
    commitment_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    score_delta: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), default="resolved")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CartelWarScore(Base):
    __tablename__ = "cartel_war_scores"
    __table_args__ = (UniqueConstraint("war_id", "cartel_id", name="uq_war_cartel_score"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    war_id: Mapped[str] = mapped_column(
        ForeignKey("cartel_wars.id", ondelete="CASCADE"), index=True
    )
    cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    territorial: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    economic: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    operations: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    intelligence: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    participation: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    stability: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    penalties: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CartelWarEvent(Base):
    __tablename__ = "cartel_war_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    war_id: Mapped[str] = mapped_column(
        ForeignKey("cartel_wars.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(48))
    actor_cartel_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    public_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    private_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class CartelWarTreaty(Base):
    __tablename__ = "cartel_war_treaties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    war_id: Mapped[str] = mapped_column(
        ForeignKey("cartel_wars.id", ondelete="CASCADE"), index=True
    )
    proposer_cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    treaty_type: Mapped[str] = mapped_column(String(40), default="ceasefire")
    terms_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="offered")
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TerritoryClaim(Base):
    __tablename__ = "territory_claims"
    __table_args__ = (Index("ix_territory_district_status", "district_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), index=True)
    cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="claimed")
    claim_strength: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("10"))
    visibility: Mapped[int] = mapped_column(Integer, default=10)
    version: Mapped[int] = mapped_column(Integer, default=1)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TerritoryControlPoint(Base):
    __tablename__ = "territory_control_points"
    __table_args__ = (UniqueConstraint("district_id", "point_type", name="uq_district_point"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), index=True)
    point_type: Mapped[str] = mapped_column(String(48))
    controlling_cartel_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True, index=True
    )
    control_value: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(24), default="neutral")
    version: Mapped[int] = mapped_column(Integer, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class TerritoryContribution(Base):
    __tablename__ = "territory_contributions"
    __table_args__ = (
        UniqueConstraint("profile_id", "idempotency_key", name="uq_territory_profile_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    claim_id: Mapped[str] = mapped_column(ForeignKey("territory_claims.id", ondelete="CASCADE"))
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), index=True)
    cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    contribution_type: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    idempotency_key: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TerritoryHistory(Base):
    __tablename__ = "territory_history"
    __table_args__ = (Index("ix_territory_history_district_created", "district_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    district_id: Mapped[str] = mapped_column(ForeignKey("districts.id"), index=True)
    event_type: Mapped[str] = mapped_column(String(48))
    previous_cartel_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    new_cartel_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Alliance(Base):
    __tablename__ = "alliances"
    __table_args__ = (UniqueConstraint("world_id", "name", name="uq_alliance_world_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    tag: Mapped[str] = mapped_column(String(12))
    charter: Mapped[str] = mapped_column(String(1_000), default="")
    governance_model: Mapped[str] = mapped_column(String(32), default="council")
    trust_score: Mapped[int] = mapped_column(Integer, default=50)
    member_limit: Mapped[int] = mapped_column(Integer, default=8)
    status: Mapped[str] = mapped_column(String(24), default="active")
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AllianceMembership(Base):
    __tablename__ = "alliance_memberships"
    __table_args__ = (UniqueConstraint("alliance_id", "cartel_id", name="uq_alliance_cartel"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    alliance_id: Mapped[str] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"))
    cartel_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    status: Mapped[str] = mapped_column(String(24), default="invited")
    role: Mapped[str] = mapped_column(String(32), default="member")
    contribution_limit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("25"))
    invited_by_cartel_id: Mapped[str | None] = mapped_column(
        ForeignKey("organizations.id"), nullable=True
    )
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leave_effective_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AllianceRole(Base):
    __tablename__ = "alliance_roles"
    __table_args__ = (UniqueConstraint("alliance_id", "role_key", name="uq_alliance_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    alliance_id: Mapped[str] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"))
    role_key: Mapped[str] = mapped_column(String(32))
    permissions_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AllianceTreaty(Base):
    __tablename__ = "alliance_treaties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    alliance_id: Mapped[str] = mapped_column(ForeignKey("alliances.id", ondelete="CASCADE"))
    treaty_type: Mapped[str] = mapped_column(String(40))
    counterparty_type: Mapped[str] = mapped_column(String(24))
    counterparty_id: Mapped[str] = mapped_column(String(36))
    terms_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(24), default="proposed")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerMessage(Base):
    __tablename__ = "player_messages"
    __table_args__ = (
        Index("ix_player_message_recipient_created", "recipient_profile_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    sender_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    recipient_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    body: Mapped[str] = mapped_column(String(1_000))
    status: Mapped[str] = mapped_column(String(24), default="delivered")
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatChannel(Base):
    __tablename__ = "chat_channels"
    __table_args__ = (
        UniqueConstraint("world_id", "channel_type", "scope_id", name="uq_chat_scope"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    channel_type: Mapped[str] = mapped_column(String(32))
    scope_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(100))
    moderated: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(24), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatMembership(Base):
    __tablename__ = "chat_memberships"
    __table_args__ = (UniqueConstraint("channel_id", "profile_id", name="uq_chat_member"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("chat_channels.id", ondelete="CASCADE"))
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    role: Mapped[str] = mapped_column(String(24), default="member")
    muted_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_message_channel_created", "channel_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    channel_id: Mapped[str] = mapped_column(ForeignKey("chat_channels.id", ondelete="CASCADE"))
    sender_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    body: Mapped[str] = mapped_column(String(1_000))
    moderation_state: Mapped[str] = mapped_column(String(24), default="visible")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class UserBlock(Base):
    __tablename__ = "user_blocks"
    __table_args__ = (UniqueConstraint("blocker_user_id", "blocked_user_id", name="uq_user_block"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    blocker_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    blocked_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ModerationReport(Base):
    __tablename__ = "moderation_reports"
    __table_args__ = (Index("ix_moderation_status_created", "status", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str | None] = mapped_column(
        ForeignKey("worlds.id", ondelete="CASCADE"), nullable=True, index=True
    )
    reporter_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_type: Mapped[str] = mapped_column(String(32))
    target_id: Mapped[str] = mapped_column(String(36))
    category: Mapped[str] = mapped_column(String(48))
    description: Mapped[str] = mapped_column(String(1_000), default="")
    risk_score: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(24), default="open")
    assigned_moderator_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class MarketOffer(Base):
    __tablename__ = "market_offers"
    __table_args__ = (
        UniqueConstraint("seller_profile_id", "idempotency_key", name="uq_market_seller_key"),
        Index("ix_market_city_status_created", "city_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    seller_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(24), default="open")
    idempotency_key: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MarketTrade(Base):
    __tablename__ = "market_trades"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    city_id: Mapped[str] = mapped_column(ForeignKey("cities.id"), index=True)
    offer_id: Mapped[str] = mapped_column(ForeignKey("market_offers.id"), unique=True)
    seller_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    buyer_profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    resource_type: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    total_price: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    review_state: Mapped[str] = mapped_column(String(24), default="clear")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class RealtimeEvent(Base):
    __tablename__ = "realtime_events"
    __table_args__ = (
        Index("ix_realtime_profile_created", "profile_id", "created_at"),
        Index("ix_realtime_world_created", "world_id", "created_at"),
        Index(
            "ix_realtime_audience_created",
            "world_id",
            "audience_type",
            "audience_id",
            "created_at",
        ),
        UniqueConstraint(
            "world_id",
            "dedupe_key",
            name="uq_realtime_world_dedupe",
        ),
        CheckConstraint(
            "event_version BETWEEN 1 AND 100",
            name="ck_realtime_event_version",
        ),
        CheckConstraint(
            "audience_type IN ('world', 'player', 'cartel', 'city')",
            name="ck_realtime_audience_type",
        ),
        CheckConstraint(
            "(audience_type = 'world' AND audience_id IS NULL) OR "
            "(audience_type != 'world' AND audience_id IS NOT NULL)",
            name="ck_realtime_audience_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
    event_version: Mapped[int] = mapped_column(Integer, default=1)
    audience_type: Mapped[str] = mapped_column(String(16), default="world")
    audience_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    dedupe_key: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AntiCheatRiskEvent(Base):
    __tablename__ = "anti_cheat_risk_events"
    __table_args__ = (Index("ix_anticheat_profile_created", "profile_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("player_profiles.id"), index=True)
    related_profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(String(48))
    risk_score: Mapped[int] = mapped_column(Integer)
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    review_status: Mapped[str] = mapped_column(String(24), default="unreviewed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def _reject_immutable_write(_: object, __: object, target: object) -> None:
    raise ValueError(f"{type(target).__name__} records are immutable")


def _reject_listing_contract_change(_: object, __: object, target: ExchangeListing) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "company_id",
        "symbol",
        "total_shares",
        "offered_shares",
        "initial_price_cents",
        "ipo_fee_cents",
        "fee_transaction_id",
        "idempotency_key",
        "listed_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("ExchangeListing issuance contract is immutable")


def _reject_share_class_contract_change(_: object, __: object, target: ShareClass) -> None:
    state = inspect(target)
    immutable_fields = (
        "listing_id",
        "class_code",
        "name",
        "total_shares",
        "voting_rights_per_share",
        "dividend_priority",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("ShareClass supply contract is immutable")


def _reject_cartel_expense_contract_change(_: object, __: object, target: CartelExpense) -> None:
    state = inspect(target)
    immutable_fields = (
        "organization_id",
        "requested_by_profile_id",
        "amount_cents",
        "purpose",
        "requires_approval",
        "idempotency_key",
        "requested_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("CartelExpense request contract is immutable")


def _reject_cartel_project_contract_change(_: object, __: object, target: CartelProject) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "organization_id",
        "district_id",
        "project_type",
        "title",
        "required_cash_cents",
        "required_influence",
        "required_intelligence",
        "influence_kind",
        "influence_reward",
        "idempotency_key",
        "created_by_profile_id",
        "starts_at",
        "ends_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("CartelProject contract is immutable")


def _reject_intelligence_offer_contract_change(
    _: object, __: object, target: IntelligenceReportOffer
) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "report_id",
        "seller_profile_id",
        "price_cents",
        "idempotency_key",
        "expires_at",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("IntelligenceReportOffer listing contract is immutable")


def _reject_world_event_definition_contract_change(
    _: object, __: object, target: WorldEventDefinition
) -> None:
    state = inspect(target)
    immutable_fields = (
        "event_key",
        "version",
        "title",
        "description",
        "default_scope_type",
        "default_duration_minutes",
        "effect_config_json",
        "created_by_user_id",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("WorldEventDefinition historical version is immutable")


def _reject_world_event_instance_contract_change(
    _: object, __: object, target: WorldEventInstance
) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "definition_id",
        "event_key",
        "template_version",
        "title",
        "description",
        "scope_type",
        "scope_id",
        "effect_config_json",
        "idempotency_key",
        "activated_by_user_id",
        "starts_at",
        "ends_at",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("WorldEventInstance concrete configuration is immutable")


def _reject_season_template_contract_change(_: object, __: object, target: SeasonTemplate) -> None:
    state = inspect(target)
    immutable_fields = (
        "template_key",
        "version",
        "name",
        "duration_minutes",
        "phase_weights_json",
        "goals_json",
        "scoring_categories_json",
        "starting_cash_cents",
        "created_by_user_id",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("SeasonTemplate historical version is immutable")


def _reject_contract_tender_terms_change(_: object, __: object, target: ContractTender) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "issuer_company_id",
        "created_by_profile_id",
        "contract_type",
        "title",
        "description",
        "max_price_cents",
        "duration_periods",
        "capacity_units",
        "min_reputation_bps",
        "min_compliance_bps",
        "idempotency_key",
        "submission_ends_at",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("ContractTender terms are immutable")


def _reject_contract_bid_terms_change(_: object, __: object, target: ContractBid) -> None:
    state = inspect(target)
    immutable_fields = (
        "tender_id",
        "bidder_company_id",
        "submitted_by_profile_id",
        "price_cents",
        "capacity_units",
        "score_points",
        "score_breakdown_json",
        "idempotency_key",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("ContractBid terms are immutable")


def _reject_commercial_contract_terms_change(
    _: object, __: object, target: CommercialContract
) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "tender_id",
        "bid_id",
        "issuer_company_id",
        "provider_company_id",
        "contract_type",
        "title",
        "price_cents_per_period",
        "duration_periods",
        "reserved_capacity_units",
        "reputation_reward_bps",
        "idempotency_key",
        "starts_at",
        "ends_at",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("CommercialContract terms are immutable")


def _reject_loan_application_terms_change(_: object, __: object, target: LoanApplication) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "company_id",
        "applicant_profile_id",
        "requested_principal_cents",
        "term_periods",
        "collateral_score_bps",
        "purpose",
        "offered_interest_rate_bps",
        "offered_installment_cents",
        "offered_total_repayment_cents",
        "rejection_reason",
        "risk_snapshot_json",
        "idempotency_key",
        "offer_expires_at",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("LoanApplication quote and inputs are immutable")


def _reject_company_loan_terms_change(_: object, __: object, target: CompanyLoan) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "application_id",
        "company_id",
        "borrower_profile_id",
        "principal_cents",
        "interest_rate_bps",
        "total_interest_cents",
        "total_repayment_cents",
        "scheduled_installment_cents",
        "term_periods",
        "collateral_score_bps",
        "idempotency_key",
        "disbursement_transaction_id",
        "starts_at",
        "ends_at",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("CompanyLoan terms are immutable")


def _reject_bond_issue_terms_change(_: object, __: object, target: BondIssue) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "issuer_company_id",
        "created_by_profile_id",
        "symbol",
        "title",
        "face_value_cents",
        "total_units",
        "coupon_rate_bps",
        "term_periods",
        "idempotency_key",
        "offering_ends_at",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("BondIssue terms are immutable")


def _reject_bond_holding_identity_change(_: object, __: object, target: BondHolding) -> None:
    state = inspect(target)
    immutable_fields = ("issue_id", "profile_id", "acquired_at")
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("BondHolding identity is immutable")


def _reject_property_identity_change(_: object, __: object, target: RealEstateProperty) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "city_id",
        "district_id",
        "property_code",
        "property_type",
        "name",
        "area_units",
        "base_value_cents",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("RealEstateProperty identity and base terms are immutable")


def _reject_property_lease_terms_change(_: object, __: object, target: PropertyLease) -> None:
    state = inspect(target)
    immutable_fields = (
        "world_id",
        "property_id",
        "landlord_profile_id",
        "tenant_company_id",
        "rent_cents_per_period",
        "term_periods",
        "idempotency_key",
        "starts_at",
        "ends_at",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("PropertyLease terms are immutable")


_REALTIME_EVENT_PATTERN = re.compile(r"^[a-z][a-z0-9_]*(?:\.[a-z][a-z0-9_]*)+$")


def _validate_realtime_event(_: object, __: object, target: RealtimeEvent) -> None:
    if target.event_version is None:
        target.event_version = 1
    if target.audience_type is None:
        target.audience_type = "world"
    if target.profile_id is not None and target.audience_type == "world":
        target.audience_type = "player"
        target.audience_id = target.profile_id
    if target.audience_type == "player":
        if target.audience_id is None and target.profile_id is not None:
            target.audience_id = target.profile_id
        if target.profile_id is None:
            target.profile_id = target.audience_id
    elif target.profile_id is not None:
        raise ValueError("Non-player realtime audiences cannot define profile_id")
    if not _REALTIME_EVENT_PATTERN.fullmatch(target.event_type):
        raise ValueError("Realtime event type must use versioned dotted naming")
    if not 1 <= target.event_version <= 100:
        raise ValueError("Realtime event version is outside the supported range")
    if target.audience_type == "world":
        if target.audience_id is not None:
            raise ValueError("World realtime audience cannot define audience_id")
    elif target.audience_type not in {"player", "cartel", "city"}:
        raise ValueError("Unsupported realtime audience")
    elif target.audience_id is None:
        raise ValueError("Scoped realtime audience requires audience_id")
    if not isinstance(target.payload_json, dict):
        raise ValueError("Realtime event payload must be an object")
    encoded = json.dumps(
        target.payload_json,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    if len(encoded) > 16_384:
        raise ValueError("Realtime event payload exceeds 16 KiB")


def _reject_notification_content_change(_: object, __: object, target: Notification) -> None:
    state = inspect(target)
    immutable_fields = (
        "user_id",
        "event_type",
        "title",
        "body",
        "metadata_json",
        "created_at",
    )
    if any(state.attrs[field].history.has_changes() for field in immutable_fields):
        raise ValueError("Notification content is immutable")


for immutable_model in (
    LedgerEntry,
    LedgerTransaction,
    AccountLedgerEntry,
    CompanyInvestment,
    CompanyMetric,
    MarketEconomyReport,
    CompanyEconomyReport,
    SpecialistPayrollReport,
    AiDecision,
    ExchangeTrade,
    ShareLedgerEntry,
    PriceSnapshot,
    DividendDeclaration,
    DividendEntitlement,
    CartelProjectContribution,
    IntelligenceOperation,
    IntelligenceReport,
    StrategicAction,
    StrategicEffect,
    SeasonScoreSnapshot,
    HallOfFameEntry,
    AccountReward,
    SeasonArchiveSnapshot,
    ContractSettlement,
    LoanPayment,
    BondSubscription,
    BondLedgerEntry,
    BondSettlement,
    RealEstateIndexSnapshot,
    PropertyTransfer,
    PropertyLeasePayment,
    PropertyImprovement,
    RealtimeEvent,
    MarketTrade,
    AuditLog,
):
    event.listen(immutable_model, "before_update", _reject_immutable_write)
    event.listen(immutable_model, "before_delete", _reject_immutable_write)

event.listen(ExchangeListing, "before_update", _reject_listing_contract_change)
event.listen(ExchangeListing, "before_delete", _reject_immutable_write)
event.listen(ShareClass, "before_update", _reject_share_class_contract_change)
event.listen(ShareClass, "before_delete", _reject_immutable_write)
event.listen(CartelExpense, "before_update", _reject_cartel_expense_contract_change)
event.listen(CartelExpense, "before_delete", _reject_immutable_write)
event.listen(CartelProject, "before_update", _reject_cartel_project_contract_change)
event.listen(CartelProject, "before_delete", _reject_immutable_write)
event.listen(
    IntelligenceReportOffer,
    "before_update",
    _reject_intelligence_offer_contract_change,
)
event.listen(IntelligenceReportOffer, "before_delete", _reject_immutable_write)
event.listen(
    WorldEventDefinition,
    "before_update",
    _reject_world_event_definition_contract_change,
)
event.listen(WorldEventDefinition, "before_delete", _reject_immutable_write)
event.listen(
    WorldEventInstance,
    "before_update",
    _reject_world_event_instance_contract_change,
)
event.listen(WorldEventInstance, "before_delete", _reject_immutable_write)
event.listen(
    SeasonTemplate,
    "before_update",
    _reject_season_template_contract_change,
)
event.listen(SeasonTemplate, "before_delete", _reject_immutable_write)
event.listen(ContractTender, "before_update", _reject_contract_tender_terms_change)
event.listen(ContractTender, "before_delete", _reject_immutable_write)
event.listen(ContractBid, "before_update", _reject_contract_bid_terms_change)
event.listen(ContractBid, "before_delete", _reject_immutable_write)
event.listen(
    CommercialContract,
    "before_update",
    _reject_commercial_contract_terms_change,
)
event.listen(CommercialContract, "before_delete", _reject_immutable_write)
event.listen(
    LoanApplication,
    "before_update",
    _reject_loan_application_terms_change,
)
event.listen(LoanApplication, "before_delete", _reject_immutable_write)
event.listen(CompanyLoan, "before_update", _reject_company_loan_terms_change)
event.listen(CompanyLoan, "before_delete", _reject_immutable_write)
event.listen(BondIssue, "before_update", _reject_bond_issue_terms_change)
event.listen(BondIssue, "before_delete", _reject_immutable_write)
event.listen(BondHolding, "before_update", _reject_bond_holding_identity_change)
event.listen(BondHolding, "before_delete", _reject_immutable_write)
event.listen(RealEstateDistrictIndex, "before_delete", _reject_immutable_write)
event.listen(RealEstateProperty, "before_update", _reject_property_identity_change)
event.listen(RealEstateProperty, "before_delete", _reject_immutable_write)
event.listen(PropertyLease, "before_update", _reject_property_lease_terms_change)
event.listen(PropertyLease, "before_delete", _reject_immutable_write)
event.listen(RealtimeEvent, "before_insert", _validate_realtime_event)
event.listen(Notification, "before_update", _reject_notification_content_change)
event.listen(Notification, "before_delete", _reject_immutable_write)
