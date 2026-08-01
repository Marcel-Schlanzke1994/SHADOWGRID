from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CreateLoanApplicationRequest(BaseModel):
    company_id: str = Field(min_length=36, max_length=36)
    requested_principal_cents: int = Field(ge=100_000, le=100_000_000_000)
    term_periods: int = Field(ge=1, le=720)
    collateral_score_bps: int = Field(ge=0, le=10_000)
    purpose: str = Field(min_length=3, max_length=240)


class LoanApplicationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    company_id: str
    company_name: str
    applicant_profile_id: str
    requested_principal_cents: int
    term_periods: int
    collateral_score_bps: int
    purpose: str
    offered_interest_rate_bps: int | None
    offered_installment_cents: int | None
    offered_total_repayment_cents: int | None
    status: Literal["offered", "rejected", "accepted", "cancelled"]
    rejection_reason: str | None
    risk_snapshot_json: dict[str, int]
    offer_expires_at: datetime | None
    accepted_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


class CompanyLoanView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    world_id: str
    application_id: str
    company_id: str
    company_name: str
    borrower_profile_id: str
    principal_cents: int
    interest_rate_bps: int
    total_interest_cents: int
    total_repayment_cents: int
    scheduled_installment_cents: int
    term_periods: int
    payments_made: int
    outstanding_principal_cents: int
    outstanding_interest_cents: int
    collateral_score_bps: int
    status: Literal["active", "repaid", "defaulted", "cancelled"]
    default_reason: str | None
    disbursement_transaction_id: str
    starts_at: datetime
    ends_at: datetime
    next_payment_at: datetime
    repaid_at: datetime | None
    defaulted_at: datetime | None
    cancelled_at: datetime | None
    created_at: datetime


class LoanPaymentView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    loan_id: str
    period_number: int
    amount_cents: int
    principal_cents: int
    interest_cents: int
    status: Literal["paid", "defaulted"]
    transaction_id: str | None
    input_snapshot_json: dict[str, Any]
    paid_at: datetime


class LoanConfigView(BaseModel):
    payment_interval_minutes: int
    offer_valid_minutes: int
    max_principal_cents: int
    max_term_periods: int
    min_interest_rate_bps: int
    max_interest_rate_bps: int
    default_reputation_penalty_bps: int
    default_investigation_penalty_bps: int

    @model_validator(mode="after")
    def validate_bounds(self) -> LoanConfigView:
        if self.min_interest_rate_bps > self.max_interest_rate_bps:
            raise ValueError("minimum loan interest rate exceeds maximum")
        return self
