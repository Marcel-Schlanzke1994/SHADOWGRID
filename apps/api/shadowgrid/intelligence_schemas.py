from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class IntelligenceOperationRequest(BaseModel):
    target_profile_id: str
    specialist_id: str
    information_type: str = Field(pattern=r"^(public|analyzed|covert)$")
    category: str = Field(
        min_length=2,
        max_length=48,
        pattern=r"^(economy|companies|exchange|cartel|territory|specialists|reputation)$",
    )


class IntelligenceOperationView(ORMModel):
    id: str
    target_profile_id: str
    specialist_id: str
    information_type: str
    category: str
    cost_cash_cents: int
    cost_intelligence: int
    success_chance_bps: int
    detection_chance_bps: int
    outcome: str
    detected: bool
    investigation_pressure_delta: int
    report_id: str | None
    cooldown_until: datetime
    created_at: datetime


class IntelligenceReportView(ORMModel):
    id: str
    owner_profile_id: str
    target_type: str
    target_id: str
    information_type: str
    category: str
    statement: str
    confidence_bps: int
    source_category: str
    source_report_id: str | None
    tradable: bool
    observed_at: datetime
    expires_at: datetime
    created_at: datetime
    is_expired: bool = False
    age_seconds: int = 0


class IntelligenceReportAdminView(IntelligenceReportView):
    accuracy_state: str
    snapshot_json: dict[str, object]
    operation_id: str | None


class IntelligenceOfferRequest(BaseModel):
    price_cents: int = Field(gt=0, le=1_000_000_000)
    expires_in_hours: int = Field(default=24, ge=1, le=168)


class IntelligenceOfferView(ORMModel):
    id: str
    report_id: str
    seller_profile_id: str
    buyer_profile_id: str | None
    purchased_report_id: str | None
    price_cents: int
    status: str
    expires_at: datetime
    sold_at: datetime | None
    created_at: datetime
    category: str = ""
    target_type: str = ""
    target_id: str = ""
    confidence_bps: int = 0


class StrategicActionRequest(BaseModel):
    target_profile_id: str
    specialist_id: str
    action_type: str = Field(
        pattern=r"^(delay_project|weaken_reputation|raise_operating_cost|"
        r"make_information_unreliable|stress_specialist)$"
    )
    target_id: str


class StrategicActionView(ORMModel):
    id: str
    target_profile_id: str
    specialist_id: str
    action_type: str
    target_type: str
    target_id: str
    cost_cash_cents: int
    cost_intelligence: int
    success_chance_bps: int
    detection_chance_bps: int
    outcome: str
    detected: bool
    investigation_pressure_delta: int
    effect_id: str | None
    cooldown_until: datetime
    created_at: datetime


class StrategicEffectView(ORMModel):
    id: str
    effect_type: str
    target_type: str
    target_id: str
    magnitude: int
    starts_at: datetime
    ends_at: datetime


class IntelligenceAdminOperationView(BaseModel):
    kind: str
    id: str
    actor_profile_id: str
    target_profile_id: str
    action_type: str
    outcome: str
    detected: bool
    success_roll: int
    detection_roll: int
    random_seed: str
    created_at: datetime
