from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.models import (
    AuditLog,
    EmailOutbox,
    LedgerEntry,
    OneTimeToken,
    Organization,
    OrganizationInvite,
    RefreshSession,
    User,
)
from sqlalchemy import func, select


def test_privacy_export_is_scoped_and_uses_exact_decimal_strings(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    response = client.get("/api/v1/privacy/export", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["account"]["email"] == "player@example.com"
    assert payload["profiles"] == [
        {
            "id": joined_profile["id"],
            "world_id": joined_profile["world_id"],
            "codename": "Test Network",
            "archetype": "business_consortium",
        }
    ]
    assert payload["ledger"]
    assert all(isinstance(entry["amount"], str) for entry in payload["ledger"])
    assert all(isinstance(entry["balance_after"], str) for entry in payload["ledger"])


def test_account_deletion_pseudonymizes_direct_identifiers_and_revokes_sessions(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    mobile_login = client.post(
        "/api/v1/auth/login",
        headers={"X-Client-Kind": "mobile"},
        json={"email": "player@example.com", "password": "StrongPassword123"},
    )
    assert mobile_login.status_code == 200
    refresh_token = mobile_login.json()["refresh_token"]

    db = SessionLocal()
    user = db.scalar(select(User).where(User.email == "player@example.com"))
    assert user is not None
    user_id = user.id
    organization = Organization(
        world_id=str(joined_profile["world_id"]),
        name="Privacy Test Organization",
        tag="PRIV",
        archetype="syndicate",
    )
    db.add(organization)
    db.flush()
    db.add(
        OrganizationInvite(
            organization_id=organization.id,
            email=user.email,
            invited_by_profile_id=str(joined_profile["id"]),
            status="pending",
            expires_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    db.add(
        EmailOutbox(
            recipient=user.email,
            subject="Private subject",
            body="Private one-time link",
        )
    )
    db.add(
        OneTimeToken(
            user_id=user.id,
            purpose="password_reset",
            token_hash="a" * 64,
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    ledger_count_before = int(db.scalar(select(func.count()).select_from(LedgerEntry)) or 0)
    db.commit()
    db.close()

    response = client.delete("/api/v1/privacy/account", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["message"] == "Account disabled and personal identifiers pseudonymized."
    assert client.get("/api/v1/auth/me", headers=auth_headers).status_code == 401
    assert (
        client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token}).status_code
        == 401
    )

    db = SessionLocal()
    deleted = db.get(User, user_id)
    assert deleted is not None
    assert deleted.disabled_at is not None
    assert deleted.email == f"deleted-{user_id}@shadowgrid.invalid"
    assert deleted.display_name == "Deleted player"
    assert deleted.locale == "en"
    assert deleted.email_verified is False
    assert deleted.totp_secret is None
    assert all(
        session.revoked_at is not None and session.user_agent == "deleted-account"
        for session in db.scalars(select(RefreshSession).where(RefreshSession.user_id == user_id))
    )
    redacted_email = db.scalar(select(EmailOutbox).where(EmailOutbox.recipient == deleted.email))
    assert redacted_email is not None
    assert redacted_email.subject == "Deleted account email"
    assert redacted_email.body == "Content removed during account deletion."
    assert redacted_email.status == "cancelled"
    token = db.scalar(select(OneTimeToken).where(OneTimeToken.user_id == user_id))
    assert token is not None
    assert token.consumed_at is not None
    invite = db.scalar(select(OrganizationInvite).where(OrganizationInvite.email == deleted.email))
    assert invite is not None
    assert invite.status == "revoked"
    assert int(db.scalar(select(func.count()).select_from(LedgerEntry)) or 0) == (
        ledger_count_before
    )
    event = db.scalar(
        select(AuditLog).where(
            AuditLog.actor_user_id == user_id,
            AuditLog.action == "privacy.account_pseudonymized",
        )
    )
    assert event is not None
    assert event.metadata_json == {
        "direct_identifiers_removed": True,
        "sessions_revoked": True,
    }
    db.close()
