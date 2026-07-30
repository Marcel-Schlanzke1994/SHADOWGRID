from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from shadowgrid import api as api_module
from shadowgrid.database import SessionLocal
from shadowgrid.models import EmailOutbox, OneTimeToken, User
from sqlalchemy import select


def _token_from_message(message: EmailOutbox, path: str) -> str:
    link = next(line for line in message.body.splitlines() if path in line)
    return parse_qs(urlparse(link).query)["token"][0]


@pytest.fixture(autouse=True)
def disable_network_delivery(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_module,
        "deliver_email",
        lambda _db, _message, _settings: True,
    )


def test_verification_email_localization_expiry_and_replay(
    client: TestClient,
) -> None:
    for locale, email, subject_fragment, body_fragment in (
        ("en", "verify-en@example.com", "Verify your", "Welcome to SHADOWGRID"),
        ("de", "verify-de@example.com", "Bestätige dein", "Willkommen bei SHADOWGRID"),
    ):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "display_name": f"Verify {locale}",
                "password": "StrongPassword123",
                "locale": locale,
                "terms_accepted": True,
            },
        )
        assert response.status_code == 201
        with SessionLocal() as db:
            message = db.scalar(select(EmailOutbox).where(EmailOutbox.recipient == email))
            assert message is not None
            assert subject_fragment in message.subject
            assert body_fragment in message.body
            assert "http://localhost:5173/verify-email?token=" in message.body
            token = _token_from_message(message, "/verify-email?token=")

        verified = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert verified.status_code == 200
        replay = client.post("/api/v1/auth/verify-email", json={"token": token})
        assert replay.status_code == 400
        assert replay.json()["error"]["code"] == "auth.invalid_one_time_token"

    expired_email = "verify-expired@example.com"
    assert (
        client.post(
            "/api/v1/auth/register",
            json={
                "email": expired_email,
                "display_name": "Expired Verification",
                "password": "StrongPassword123",
                "locale": "en",
                "terms_accepted": True,
            },
        ).status_code
        == 201
    )
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == expired_email))
        assert user is not None
        item = db.scalar(
            select(OneTimeToken).where(
                OneTimeToken.user_id == user.id,
                OneTimeToken.purpose == "verify_email",
            )
        )
        message = db.scalar(select(EmailOutbox).where(EmailOutbox.recipient == expired_email))
        assert item is not None and message is not None
        item.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        expired_token = _token_from_message(message, "/verify-email?token=")
        db.commit()
    expired = client.post("/api/v1/auth/verify-email", json={"token": expired_token})
    assert expired.status_code == 400
    assert expired.json()["error"]["code"] == "auth.invalid_one_time_token"


def test_password_reset_is_generic_single_use_and_revokes_sessions(
    client: TestClient,
    verified_user: User,
) -> None:
    mobile_login = client.post(
        "/api/v1/auth/login",
        headers={"X-Client-Kind": "mobile"},
        json={
            "email": verified_user.email,
            "password": "StrongPassword123",
        },
    )
    assert mobile_login.status_code == 200
    old_refresh = mobile_login.json()["refresh_token"]

    missing = client.post(
        "/api/v1/auth/password/forgot",
        json={"email": "missing-account@example.com"},
    )
    known = client.post(
        "/api/v1/auth/password/forgot",
        json={"email": verified_user.email},
    )
    assert missing.status_code == known.status_code == 200
    assert missing.json() == known.json()

    with SessionLocal() as db:
        message = db.scalar(
            select(EmailOutbox)
            .where(EmailOutbox.recipient == verified_user.email)
            .order_by(EmailOutbox.created_at.desc())
        )
        assert message is not None
        assert message.subject == "Reset your SHADOWGRID password"
        assert "http://localhost:5173/reset-password?token=" in message.body
        token = _token_from_message(message, "/reset-password?token=")

    reset = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": "NewStrongPassword456"},
    )
    assert reset.status_code == 200
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": verified_user.email,
                "password": "StrongPassword123",
            },
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login",
            json={
                "email": verified_user.email,
                "password": "NewStrongPassword456",
            },
        ).status_code
        == 200
    )
    replay = client.post(
        "/api/v1/auth/password/reset",
        json={"token": token, "password": "AnotherPassword789"},
    )
    assert replay.status_code == 400
    assert replay.json()["error"]["code"] == "auth.invalid_one_time_token"


def test_email_and_token_endpoints_are_rate_limited(client: TestClient) -> None:
    forgot_payload = {"email": "forgot-limit@example.com"}
    for _ in range(5):
        assert client.post("/api/v1/auth/password/forgot", json=forgot_payload).status_code == 200
    limited = client.post("/api/v1/auth/password/forgot", json=forgot_payload)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "auth.rate_limited"
    assert int(limited.headers["retry-after"]) >= 1

    for _ in range(10):
        invalid = client.post(
            "/api/v1/auth/verify-email",
            json={"token": "same-invalid-token"},
        )
        assert invalid.status_code == 400
    token_limited = client.post(
        "/api/v1/auth/verify-email",
        json={"token": "same-invalid-token"},
    )
    assert token_limited.status_code == 429
    assert token_limited.json()["error"]["code"] == "auth.rate_limited"
