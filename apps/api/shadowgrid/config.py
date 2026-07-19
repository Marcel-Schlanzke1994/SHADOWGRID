from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr, field_validator
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
    season_days: int = Field(default=14, ge=1, le=140)
    web_origins: Annotated[list[str], NoDecode] = ["http://localhost:5173"]
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "noreply@shadowgrid.local"
    translation_provider: str = "disabled"
    allow_external_deploy: bool = False
    log_level: str = "INFO"
    web_dist_path: Path | None = None
    test_operation_seconds: int = Field(default=0, ge=0, le=30)

    @field_validator("web_origins", mode="before")
    @classmethod
    def parse_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
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
