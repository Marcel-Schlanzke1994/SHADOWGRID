from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
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
    region_key: Mapped[str] = mapped_column(String(40), default="vesper-region")
    instance_key: Mapped[str] = mapped_column(String(24), default="sector-a")
    status: Mapped[str] = mapped_column(String(24), default="active")
    max_players: Mapped[int] = mapped_column(Integer, default=2_000)
    market_state_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlayerProfile(Base):
    __tablename__ = "player_profiles"
    __table_args__ = (UniqueConstraint("user_id", "world_id", name="uq_profile_user_world"),)

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

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    profile_id: Mapped[str] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    role: Mapped[str] = mapped_column(String(40))
    competence: Mapped[int] = mapped_column(Integer)
    loyalty: Mapped[int] = mapped_column(Integer)
    ambition: Mapped[int] = mapped_column(Integer)
    stress: Mapped[int] = mapped_column(Integer, default=0)
    exposure: Mapped[int] = mapped_column(Integer, default=0)
    salary: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    status: Mapped[str] = mapped_column(String(24), default="available")
    assigned_operation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
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
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("organization_id", "profile_id", name="uq_org_profile"),)

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


class Notification(Base):
    __tablename__ = "notifications"

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
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_str)
    world_id: Mapped[str] = mapped_column(ForeignKey("worlds.id", ondelete="CASCADE"), index=True)
    profile_id: Mapped[str | None] = mapped_column(
        ForeignKey("player_profiles.id", ondelete="CASCADE"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(64))
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
