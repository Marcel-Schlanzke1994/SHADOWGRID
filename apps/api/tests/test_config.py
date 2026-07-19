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
