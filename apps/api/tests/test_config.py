import pytest
from pydantic import ValidationError
from shadowgrid.config import Settings


def test_railway_postgres_url_uses_psycopg3_driver() -> None:
    settings = Settings(
        secret_key="test-secret-key",
        refresh_pepper="test-refresh-pepper",
        seed_secret="test-seed-secret",
        database_url="postgresql://shadowgrid:password@postgres.railway.internal:5432/railway",
    )

    assert settings.database_url.startswith("postgresql+psycopg://")


def test_legacy_postgres_url_uses_psycopg3_driver() -> None:
    settings = Settings(
        secret_key="test-secret-key",
        refresh_pepper="test-refresh-pepper",
        seed_secret="test-seed-secret",
        database_url="postgres://shadowgrid:password@localhost:5432/shadowgrid",
    )

    assert settings.database_url.startswith("postgresql+psycopg://")


def test_demo_mode_is_always_disabled_in_production() -> None:
    settings = Settings(
        app_env="production",
        local_demo_mode=True,
        secret_key="test-secret-key",
        refresh_pepper="test-refresh-pepper",
        seed_secret="test-seed-secret",
        metrics_token="test-metrics-token-with-at-least-thirty-two-characters",
        web_origins=["https://shadowgrid.example"],
        smtp_host="smtp.shadowgrid.example",
        smtp_from="noreply@shadowgrid.example",
    )

    assert settings.demo_mode_enabled is False


@pytest.mark.parametrize(
    "origins",
    [
        [],
        ["*"],
        ["http://shadowgrid.example"],
        ["https://localhost:3000"],
        ["https://shadowgrid.example/path"],
    ],
)
def test_production_rejects_unsafe_cors_origins(origins: list[str]) -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            local_demo_mode=False,
            secret_key="test-secret-key",
            refresh_pepper="test-refresh-pepper",
            seed_secret="test-seed-secret",
            metrics_token="test-metrics-token-with-at-least-thirty-two-characters",
            web_origins=origins,
            smtp_host="smtp.shadowgrid.example",
            smtp_from="noreply@shadowgrid.example",
        )


def test_production_accepts_explicit_https_cors_origins() -> None:
    settings = Settings(
        app_env="production",
        local_demo_mode=False,
        secret_key="test-secret-key",
        refresh_pepper="test-refresh-pepper",
        seed_secret="test-seed-secret",
        metrics_token="test-metrics-token-with-at-least-thirty-two-characters",
        web_origins=["https://play.shadowgrid.example"],
        smtp_host="smtp.shadowgrid.example",
        smtp_from="noreply@shadowgrid.example",
    )

    assert settings.web_origins == ["https://play.shadowgrid.example"]


def test_production_requires_a_strong_metrics_token() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            local_demo_mode=False,
            secret_key="test-secret-key",
            refresh_pepper="test-refresh-pepper",
            seed_secret="test-seed-secret",
            web_origins=["https://play.shadowgrid.example"],
            smtp_host="smtp.shadowgrid.example",
            smtp_from="noreply@shadowgrid.example",
        )


def test_analytics_are_disabled_by_default() -> None:
    settings = Settings(
        secret_key="test-secret-key",
        refresh_pepper="test-refresh-pepper",
        seed_secret="test-seed-secret",
    )

    assert settings.analytics_enabled is False


def test_production_rejects_unsafe_public_email_url() -> None:
    with pytest.raises(ValidationError):
        Settings(
            app_env="production",
            secret_key="test-secret-key",
            refresh_pepper="test-refresh-pepper",
            seed_secret="test-seed-secret",
            metrics_token="test-metrics-token-with-at-least-thirty-two-characters",
            web_origins=["https://play.shadowgrid.example"],
            public_web_url="http://localhost:5173",
            smtp_host="smtp.shadowgrid.example",
            smtp_from="noreply@shadowgrid.example",
        )


def test_smtp_transport_modes_and_credentials_are_consistent() -> None:
    common = {
        "secret_key": "test-secret-key",
        "refresh_pepper": "test-refresh-pepper",
        "seed_secret": "test-seed-secret",
    }
    with pytest.raises(ValidationError):
        Settings(**common, smtp_starttls=True, smtp_use_ssl=True)
    with pytest.raises(ValidationError):
        Settings(**common, smtp_username="mailer")


def test_exchange_configuration_is_integer_bounded() -> None:
    settings = Settings(
        secret_key="test-secret-key",
        refresh_pepper="test-refresh-pepper",
        seed_secret="test-seed-secret",
        ipo_fee_cents=500_000,
        exchange_order_rate_limit_per_minute=60,
        exchange_max_price_deviation_bps=5_000,
    )

    assert settings.ipo_fee_cents == 500_000
    assert settings.exchange_order_rate_limit_per_minute == 60
    assert settings.exchange_max_price_deviation_bps == 5_000

    with pytest.raises(ValidationError):
        Settings(
            secret_key="test-secret-key",
            refresh_pepper="test-refresh-pepper",
            seed_secret="test-seed-secret",
            exchange_max_price_deviation_bps=10_001,
        )
