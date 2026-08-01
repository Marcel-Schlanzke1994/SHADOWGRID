from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CreateBondIssueRequest(BaseModel):
    issuer_company_id: str = Field(min_length=36, max_length=36)
    symbol: str = Field(min_length=2, max_length=12)
    title: str = Field(min_length=3, max_length=140)
    face_value_cents: int = Field(ge=1, le=100_000_000_000)
    total_units: int = Field(ge=1, le=1_000_000)
    coupon_rate_bps: int = Field(ge=1, le=20_000)
    term_periods: int = Field(ge=1, le=720)


class SubscribeBondRequest(BaseModel):
    quantity: int = Field(ge=1, le=1_000_000)


class BondIssueView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    issuer_company_id: str
    issuer_company_name: str
    created_by_profile_id: str
    symbol: str
    title: str
    face_value_cents: int
    total_units: int
    sold_units: int
    coupon_rate_bps: int
    term_periods: int
    coupons_paid: int
    status: Literal["offering", "active", "repaid", "defaulted", "cancelled"]
    default_reason: str | None
    offering_ends_at: datetime
    starts_at: datetime | None
    ends_at: datetime | None
    next_coupon_at: datetime | None
    activated_at: datetime | None
    repaid_at: datetime | None
    defaulted_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    holder_count: int


class BondSubscriptionView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    issue_id: str
    subscriber_profile_id: str
    quantity: int
    amount_cents: int
    transaction_id: str
    created_at: datetime


class BondHoldingView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    issue_id: str
    symbol: str
    title: str
    issuer_company_name: str
    profile_id: str
    quantity: int
    face_value_cents: int
    coupon_rate_bps: int
    issue_status: str
    acquired_at: datetime
    updated_at: datetime


class BondSettlementView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    issue_id: str
    period_number: int
    profile_id: str
    payment_type: Literal["coupon", "redemption"]
    quantity: int
    amount_cents: int
    status: Literal["paid", "defaulted"]
    transaction_id: str | None
    input_snapshot_json: dict[str, Any]
    settled_at: datetime


class BondConfigView(BaseModel):
    coupon_interval_minutes: int
    offering_minutes: int
    max_principal_cents: int
    max_term_periods: int
    default_reputation_penalty_bps: int
    default_investigation_penalty_bps: int
