from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from shadowgrid import main
from shadowgrid.config import Settings


def test_metrics_remain_available_to_local_prometheus(client: TestClient) -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "shadowgrid_http_requests_total" in response.text


def test_metrics_require_bearer_token_outside_local_development(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = "test-metrics-token-with-at-least-thirty-two-characters"
    production = Settings(
        app_env="production",
        local_demo_mode=False,
        secret_key="test-secret-key",
        refresh_pepper="test-refresh-pepper",
        seed_secret="test-seed-secret",
        metrics_token=token,
        web_origins=["https://play.shadowgrid.example"],
        smtp_host="smtp.shadowgrid.example",
        smtp_from="noreply@shadowgrid.example",
    )
    monkeypatch.setattr(main, "settings", production)

    assert client.get("/metrics").status_code == 404
    assert (
        client.get("/metrics", headers={"Authorization": "Bearer incorrect-token"}).status_code
        == 404
    )
    assert client.get("/metrics", headers={"Authorization": f"Bearer {token}"}).status_code == 200
