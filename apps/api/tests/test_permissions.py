from __future__ import annotations

from shadowgrid.database import SessionLocal
from shadowgrid.models import Organization, OrganizationMembership, PlayerProfile


def test_member_without_invite_permission_is_denied(client, auth_headers, joined_profile) -> None:
    db = SessionLocal()
    profile = db.get(PlayerProfile, joined_profile["id"])
    assert profile is not None
    profile.tutorial_step = 7
    org = Organization(
        world_id=profile.world_id, name="Permission Network", tag="PERM", archetype="family_network"
    )
    db.add(org)
    db.flush()
    db.add(OrganizationMembership(organization_id=org.id, profile_id=profile.id, role="member"))
    db.commit()
    org_id = org.id
    db.close()
    response = client.post(
        f"/api/v1/organizations/{org_id}/invites",
        headers=auth_headers,
        json={"email": "invitee@example.com"},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "organization.permission_denied"

    members = client.get(f"/api/v1/organizations/{org_id}/members", headers=auth_headers)
    assert members.status_code == 200
    assert members.json()[0]["role"] == "member"

    role_change = client.patch(
        f"/api/v1/organizations/{org_id}/members/{members.json()[0]['membership_id']}",
        headers=auth_headers,
        json={"role": "deputy"},
    )
    assert role_change.status_code == 403
    assert role_change.json()["error"]["code"] == "organization.permission_denied"


def test_admin_endpoint_rejects_normal_user(client, auth_headers) -> None:
    response = client.get("/api/v1/admin/summary", headers=auth_headers)
    assert response.status_code == 403


def test_profile_data_cannot_be_selected_by_arbitrary_id(
    client, auth_headers, joined_profile
) -> None:
    response = client.get(
        "/api/v1/resources?profile_id=00000000-0000-0000-0000-000000000000", headers=auth_headers
    )
    assert response.status_code == 200
    assert response.json()["balance"]["cash"] == 80000.0
