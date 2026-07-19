from __future__ import annotations

from fastapi.testclient import TestClient
from shadowgrid.models import User


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


def test_validation_error_uses_stable_shape(client: TestClient) -> None:
    response = client.post("/api/v1/auth/register", json={"email": "not-an-email"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "request.validation"
    assert body["error"]["request_id"]
    assert "server_time" in body
