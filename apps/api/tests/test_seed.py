from __future__ import annotations

import importlib

import pytest
from shadowgrid.config import Settings


def test_demo_seed_refuses_production_even_when_flag_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_module = importlib.import_module("shadowgrid.seed")
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
    monkeypatch.setattr(seed_module, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="disabled"):
        seed_module.seed()
