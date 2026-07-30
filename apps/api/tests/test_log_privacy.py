from __future__ import annotations

import logging

import pytest
from fastapi.testclient import TestClient


def test_auth_logs_exclude_credentials_tokens_and_direct_identifiers(
    client: TestClient,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    email = "log-privacy@example.com"
    password = "LogPrivacyPassword123"
    with caplog.at_level(logging.INFO):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "password": password,
                "display_name": "Log Privacy",
                "locale": "en",
                "terms_accepted": True,
            },
        )
    assert response.status_code == 201

    captured = capsys.readouterr()
    output = f"{caplog.text}\n{captured.out}\n{captured.err}"
    assert email not in output
    assert password not in output
    assert "verify-email?token=" not in output
    assert "access_token" not in output
    assert "refresh_token" not in output
