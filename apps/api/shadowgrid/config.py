from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from pydantic import EmailStr, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env", PROJECT_ROOT / ".local" / "development.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "SHADOWGRID API"
    api_prefix: str = "/api/v1"
    database_url: str = f"sqlite:///{(PROJECT_ROOT / '.local' / 'shadowgrid.db').as_posix()}"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: SecretStr
    refresh_pepper: SecretStr
    seed_secret: SecretStr
    access_token_minutes: int = Field(default=10, ge=2, le=30)
    refresh_token_days: int = Field(default=30, ge=1, le=90)
    auth_login_rate_limit: int = Field(default=8, ge=1, le=1_000)
    auth_login_rate_window_seconds: int = Field(default=600, ge=10, le=86_400)
    auth_email_rate_limit: int = Field(default=5, ge=1, le=1_000)
    auth_email_rate_window_seconds: int = Field(default=3_600, ge=10, le=86_400)
    auth_token_rate_limit: int = Field(default=10, ge=1, le=1_000)
    auth_token_rate_window_seconds: int = Field(default=600, ge=10, le=86_400)
    season_days: int = Field(default=14, ge=1, le=140)
    seed_version: int = Field(default=1, ge=1, le=1_000_000)
    demo_random_seed: int = Field(default=28_001, ge=0, le=2_147_483_647)
    starting_cash_cents: int = Field(default=8_000_000, ge=0, le=1_000_000_000)
    company_founding_cost_cents: int = Field(
        default=2_000_000,
        ge=100_000,
        le=100_000_000,
    )
    ipo_min_enterprise_value_cents: int = Field(
        default=10_000_000,
        ge=1_000_000,
        le=100_000_000_000,
    )
    ipo_profitable_periods: int = Field(default=3, ge=1, le=24)
    ipo_min_compliance_bps: int = Field(default=6_000, ge=0, le=10_000)
    ipo_min_employees: int = Field(default=8, ge=1, le=100_000)
    ipo_max_investigation_pressure_bps: int = Field(default=2_500, ge=0, le=10_000)
    ipo_fee_cents: int = Field(default=500_000, ge=1, le=1_000_000_000)
    exchange_order_rate_limit_per_minute: int = Field(default=60, ge=1, le=10_000)
    exchange_max_price_deviation_bps: int = Field(default=5_000, ge=100, le=10_000)
    cartel_creation_cost_cents: int = Field(default=1_000_000, ge=0, le=1_000_000_000)
    cartel_default_approval_threshold_cents: int = Field(
        default=250_000,
        ge=1,
        le=1_000_000_000,
    )
    cartel_default_single_spend_limit_cents: int = Field(
        default=2_500_000,
        ge=1,
        le=10_000_000_000,
    )
    cartel_control_threshold: int = Field(default=100, ge=1, le=1_000_000)
    cartel_control_margin: int = Field(default=20, ge=0, le=1_000_000)
    intelligence_operation_rate_limit_per_minute: int = Field(default=12, ge=1, le=1_000)
    intelligence_operation_cooldown_minutes: int = Field(default=30, ge=1, le=10_080)
    strategic_action_rate_limit_per_minute: int = Field(default=6, ge=1, le=1_000)
    strategic_action_cooldown_minutes: int = Field(default=120, ge=1, le=10_080)
    strategic_effect_minutes: int = Field(default=180, ge=1, le=43_200)
    contract_settlement_interval_minutes: int = Field(default=60, ge=1, le=10_080)
    contract_tender_max_duration_periods: int = Field(default=168, ge=1, le=720)
    contract_reputation_reward_bps: int = Field(default=250, ge=0, le=2_000)
    contract_breach_reputation_penalty_bps: int = Field(
        default=750,
        ge=0,
        le=5_000,
    )
    contract_breach_investigation_penalty_bps: int = Field(
        default=250,
        ge=0,
        le=5_000,
    )
    loan_payment_interval_minutes: int = Field(default=1_440, ge=1, le=43_200)
    loan_offer_valid_minutes: int = Field(default=1_440, ge=5, le=43_200)
    loan_max_principal_cents: int = Field(default=100_000_000, ge=100_000, le=100_000_000_000)
    loan_max_term_periods: int = Field(default=30, ge=1, le=720)
    loan_base_interest_rate_bps: int = Field(default=800, ge=0, le=10_000)
    loan_min_interest_rate_bps: int = Field(default=200, ge=0, le=10_000)
    loan_max_interest_rate_bps: int = Field(default=5_000, ge=1, le=20_000)
    loan_default_reputation_penalty_bps: int = Field(default=750, ge=0, le=5_000)
    loan_default_investigation_penalty_bps: int = Field(default=1_000, ge=0, le=5_000)
    bond_coupon_interval_minutes: int = Field(default=1_440, ge=1, le=43_200)
    bond_offering_minutes: int = Field(default=1_440, ge=5, le=43_200)
    bond_max_principal_cents: int = Field(default=100_000_000, ge=100_000, le=100_000_000_000)
    bond_max_term_periods: int = Field(default=30, ge=1, le=720)
    bond_default_reputation_penalty_bps: int = Field(default=1_000, ge=0, le=5_000)
    bond_default_investigation_penalty_bps: int = Field(default=1_250, ge=0, le=5_000)
    real_estate_index_interval_minutes: int = Field(default=1_440, ge=1, le=43_200)
    property_lease_interval_minutes: int = Field(default=1_440, ge=1, le=43_200)
    property_max_lease_periods: int = Field(default=30, ge=2, le=720)
    headquarters_upgrade_base_cost_cents: int = Field(
        default=500_000, ge=100_000, le=100_000_000_000
    )
    local_demo_mode: bool = True
    alpha_open_registration: bool = False
    web_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    public_web_url: str | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "noreply@shadowgrid.local"
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_starttls: bool = False
    smtp_use_ssl: bool = False
    translation_provider: str = "disabled"
    allow_external_deploy: bool = False
    analytics_enabled: bool = False
    metrics_token: SecretStr | None = None
    log_level: str = "INFO"
    web_dist_path: Path | None = None
    bootstrap_admin_email: EmailStr | None = None
    bootstrap_admin_password: SecretStr | None = None
    test_operation_seconds: int = Field(default=0, ge=0, le=30)

    @field_validator("web_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def validate_deployment_origins(self) -> Settings:
        environment = self.app_env.strip().lower()
        self.app_env = environment
        if self.smtp_starttls and self.smtp_use_ssl:
            raise ValueError("SMTP_STARTTLS and SMTP_USE_SSL are mutually exclusive")
        if (self.smtp_username is None) != (self.smtp_password is None):
            raise ValueError("SMTP_USERNAME and SMTP_PASSWORD must be configured together")
        if environment not in {"production", "staging"}:
            return self
        if self.metrics_token is None or len(self.metrics_token.get_secret_value()) < 32:
            raise ValueError(
                "METRICS_TOKEN with at least 32 characters is required outside local development"
            )
        if not self.web_origins:
            raise ValueError("WEB_ORIGINS must be explicit outside local development")
        public_urls = [*self.web_origins]
        if self.public_web_url is not None:
            public_urls.append(self.public_web_url)
        for origin in public_urls:
            parsed = urlsplit(origin)
            if (
                origin == "*"
                or parsed.scheme != "https"
                or parsed.hostname in {None, "localhost", "127.0.0.1", "::1"}
                or parsed.username is not None
                or parsed.password is not None
                or parsed.query
                or parsed.fragment
                or parsed.path not in {"", "/"}
            ):
                raise ValueError(
                    "Production and staging public web URLs must be explicit HTTPS origins"
                )
        if self.smtp_host.strip().lower() in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("Production and staging SMTP_HOST must be non-local")
        if self.smtp_from.lower().endswith((".local", ".invalid")):
            raise ValueError("Production and staging SMTP_FROM must be a routable address")
        return self

    @property
    def web_url(self) -> str:
        """Return the browser origin used in transactional email links."""
        return (self.public_web_url or self.web_origins[0]).rstrip("/")

    @property
    def demo_mode_enabled(self) -> bool:
        """Demo data is never enabled in production, regardless of environment input."""
        return self.local_demo_mode and self.app_env not in {"production", "staging"}

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_driver(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        return value

    @field_validator("translation_provider")
    @classmethod
    def validate_translation_provider(cls, value: str) -> str:
        allowed = {"disabled", "provider_a", "provider_b", "local"}
        if value not in allowed:
            raise ValueError("unsupported translation provider")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
