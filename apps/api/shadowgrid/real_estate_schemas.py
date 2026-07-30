from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class PropertySaleListingRequest(BaseModel):
    asking_price_cents: int = Field(ge=1, le=100_000_000_000)


class PropertyRentListingRequest(BaseModel):
    rent_cents_per_period: int = Field(ge=1, le=10_000_000_000)


class PropertyLeaseRequest(BaseModel):
    tenant_company_id: str = Field(min_length=36, max_length=36)
    term_periods: int = Field(ge=2, le=720)


class PropertyCompanyAssignmentRequest(BaseModel):
    company_id: str = Field(min_length=36, max_length=36)


class RealEstateIndexView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    city_id: str
    city_name: str
    district_id: str
    district_name: str
    price_index_bps: int
    rent_index_bps: int
    demand_bps: int
    safety_score: int
    infrastructure_score: int
    economic_score: int
    cartel_control_points: int
    event_multiplier_bps: int
    version: int
    updated_at: datetime


class RealEstatePropertyView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    city_id: str
    city_name: str
    district_id: str
    district_name: str
    property_code: str
    property_type: Literal["land", "building", "commercial_space", "headquarters"]
    name: str
    area_units: int
    base_value_cents: int
    improvement_value_cents: int
    owner_profile_id: str | None
    owner_name: str | None
    is_owned_by_me: bool
    company_use_id: str | None
    company_use_name: str | None
    status: Literal["available", "owned", "leased", "archived"]
    listing_type: Literal["sale", "rent"] | None
    asking_price_cents: int
    rent_cents_per_period: int
    effective_sale_price_cents: int
    effective_rent_cents_per_period: int
    headquarters_level: int
    version: int
    created_at: datetime
    updated_at: datetime


class PropertyTransferView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: str
    seller_profile_id: str | None
    buyer_profile_id: str
    price_cents: int
    price_index_bps: int
    transfer_type: Literal["system_sale", "resale"]
    transaction_id: str
    created_at: datetime


class PropertyLeasePaymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    period_number: int
    amount_cents: int
    status: Literal["paid", "defaulted"]
    transaction_id: str | None
    input_snapshot_json: dict[str, Any]
    paid_at: datetime


class PropertyLeaseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    property_id: str
    property_name: str
    landlord_profile_id: str
    landlord_name: str
    tenant_company_id: str
    tenant_company_name: str
    rent_cents_per_period: int
    term_periods: int
    periods_paid: int
    status: Literal["active", "completed", "defaulted", "cancelled"]
    default_reason: str | None
    starts_at: datetime
    ends_at: datetime
    next_payment_at: datetime
    completed_at: datetime | None
    defaulted_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime
    payments: list[PropertyLeasePaymentView]


class PropertyImprovementView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    property_id: str
    company_id: str
    improvement_type: Literal["headquarters_upgrade"]
    level_after: int
    cost_cents: int
    transaction_id: str
    created_at: datetime


class RealEstateConfigView(BaseModel):
    index_interval_minutes: int
    lease_interval_minutes: int
    max_lease_periods: int
    headquarters_upgrade_base_cost_cents: int
