from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateTenderRequest(BaseModel):
    issuer_company_id: str = Field(min_length=36, max_length=36)
    contract_type: Literal["supply", "service"]
    title: str = Field(min_length=3, max_length=140)
    description: str = Field(default="", max_length=500)
    max_price_cents: int = Field(ge=1, le=100_000_000_000)
    duration_periods: int = Field(ge=1, le=720)
    capacity_units: int = Field(ge=1, le=10_000)
    min_reputation_bps: int = Field(default=0, ge=0, le=10_000)
    min_compliance_bps: int = Field(default=0, ge=0, le=10_000)
    submission_minutes: int = Field(default=60, ge=5, le=10_080)


class SubmitBidRequest(BaseModel):
    bidder_company_id: str = Field(min_length=36, max_length=36)
    price_cents: int = Field(ge=1, le=100_000_000_000)


class AwardBidRequest(BaseModel):
    bid_id: str = Field(min_length=36, max_length=36)


class TenderView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    issuer_company_id: str
    issuer_company_name: str
    created_by_profile_id: str
    contract_type: Literal["supply", "service"]
    title: str
    description: str
    max_price_cents: int
    duration_periods: int
    capacity_units: int
    min_reputation_bps: int
    min_compliance_bps: int
    status: Literal["open", "awarded", "cancelled", "expired"]
    submission_ends_at: datetime
    awarded_at: datetime | None
    created_at: datetime
    bid_count: int


class BidView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    tender_id: str
    bidder_company_id: str
    bidder_company_name: str
    submitted_by_profile_id: str
    price_cents: int
    capacity_units: int
    score_points: int
    score_breakdown_json: dict[str, int]
    status: Literal["submitted", "won", "lost", "withdrawn"]
    created_at: datetime


class CommercialContractView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    tender_id: str
    bid_id: str
    issuer_company_id: str
    issuer_company_name: str
    provider_company_id: str
    provider_company_name: str
    contract_type: Literal["supply", "service"]
    title: str
    price_cents_per_period: int
    duration_periods: int
    periods_settled: int
    reserved_capacity_units: int
    reputation_reward_bps: int
    status: Literal["active", "completed", "breached", "cancelled"]
    starts_at: datetime
    ends_at: datetime
    next_settlement_at: datetime
    completed_at: datetime | None
    breached_at: datetime | None
    breach_reason: str | None
    created_at: datetime


class ContractSettlementView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    contract_id: str
    period_number: int
    amount_cents: int
    status: Literal["paid", "defaulted"]
    transaction_id: str | None
    input_snapshot_json: dict[str, Any]
    settled_at: datetime


class ContractConfigView(BaseModel):
    settlement_interval_minutes: int
    max_duration_periods: int
    reputation_reward_bps: int
    breach_reputation_penalty_bps: int
    breach_investigation_penalty_bps: int

    @model_validator(mode="after")
    def validate_bounds(self) -> ContractConfigView:
        if self.settlement_interval_minutes <= 0 or self.max_duration_periods <= 0:
            raise ValueError("contract configuration must be positive")
        return self
