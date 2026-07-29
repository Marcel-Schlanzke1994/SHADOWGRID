from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.models import EmailOutbox, User
from sqlalchemy import select


def test_health_has_secure_headers_and_server_time(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-request-id"]
    assert response.headers["x-server-time"]


def test_login_refresh_rotation_and_reuse_revokes_family(
    client: TestClient, verified_user: User
) -> None:
    login = client.post(
        "/api/v1/auth/login",
        headers={"X-Client-Kind": "mobile"},
        json={"email": verified_user.email, "password": "StrongPassword123"},
    )
    assert login.status_code == 200
    first = login.json()["refresh_token"]
    rotated = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert rotated.status_code == 200
    second = rotated.json()["refresh_token"]
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert reuse.status_code == 401
    family_revoked = client.post("/api/v1/auth/refresh", json={"refresh_token": second})
    assert family_revoked.status_code == 401


def test_unverified_user_cannot_login(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "new@example.com",
            "display_name": "New Player",
            "password": "StrongPassword123",
            "locale": "en",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 201
    login = client.post(
        "/api/v1/auth/login", json={"email": "new@example.com", "password": "StrongPassword123"}
    )
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "auth.email_unverified"


def test_registration_email_uses_configured_web_origin(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={
            "email": "link-test@example.com",
            "display_name": "Link Tester",
            "password": "StrongPassword123",
            "locale": "en",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 201
    with SessionLocal() as db:
        message = db.scalar(
            select(EmailOutbox).where(EmailOutbox.recipient == "link-test@example.com")
        )
        assert message is not None
        assert "http://localhost:5173/verify-email?token=" in message.body


def test_registration_verification_and_session_rotation_lifecycle(
    client: TestClient,
) -> None:
    email = "lifecycle-player@example.com"
    password = "StrongPassword123"
    registered = client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "display_name": "Lifecycle Player",
            "password": password,
            "locale": "de",
            "terms_accepted": True,
        },
    )
    assert registered.status_code == 201
    assert (
        client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        ).status_code
        == 403
    )

    with SessionLocal() as db:
        message = db.scalar(select(EmailOutbox).where(EmailOutbox.recipient == email))
        assert message is not None
        verification_url = next(
            line for line in message.body.splitlines() if "/verify-email?token=" in line
        )
    token = parse_qs(urlparse(verification_url).query)["token"][0]
    verified = client.post("/api/v1/auth/verify-email", json={"token": token})
    assert verified.status_code == 200

    login = client.post(
        "/api/v1/auth/login",
        headers={"X-Client-Kind": "mobile"},
        json={"email": email, "password": password},
    )
    assert login.status_code == 200
    rotated = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login.json()["refresh_token"]},
    )
    assert rotated.status_code == 200
    assert rotated.json()["refresh_token"] != login.json()["refresh_token"]


def test_validation_error_uses_stable_shape(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request.validation"
    assert body["error"]["request_id"]
    assert "server_time" in body


def test_login_rate_limit_is_shared_and_returns_retry_window(client: TestClient) -> None:
    payload = {"email": "rate-limit@example.com", "password": "WrongPassword123"}
    for _ in range(8):
        response = client.post("/api/v1/auth/login", json=payload)
        assert response.status_code == 401

    limited = client.post("/api/v1/auth/login", json=payload)
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "auth.rate_limited"
    assert int(limited.headers["retry-after"]) >= 1


def test_streaming_request_body_is_limited_without_content_length(
    client: TestClient,
) -> None:
    chunks = iter([b'{"padding":"', b"x" * 600_000, b"y" * 600_000, b'"}'])
    response = client.post(
        "/api/v1/auth/register",
        content=chunks,
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request.too_large"
