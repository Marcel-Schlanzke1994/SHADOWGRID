from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.finance import transaction_balance_cents
from shadowgrid.models import (
    Account,
    AuditLog,
    CartelDistrictInfluence,
    CartelExpense,
    CartelProject,
    CartelProjectContribution,
    City,
    District,
    LedgerTransaction,
    Organization,
    OrganizationMembership,
    PlayerProfile,
    ResourceBalance,
    TerritoryControlPoint,
    User,
    World,
)
from shadowgrid.security import hash_password
from sqlalchemy import func, select

PASSWORD = "StrongPassword123"


def _create_player(
    client: TestClient,
    email: str,
    codename: str,
) -> tuple[str, dict[str, str]]:
    with SessionLocal() as db:
        world = db.scalar(select(World))
        city = db.scalar(select(City))
        district = db.scalar(select(District))
        assert world is not None and city is not None and district is not None
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            display_name=codename,
            email_verified=True,
        )
        db.add(user)
        db.flush()
        profile = PlayerProfile(
            user_id=user.id,
            world_id=world.id,
            city_id=city.id,
            codename=codename,
            archetype="business_consortium",
            home_district_id=district.id,
            tutorial_step=7,
            protected_until=datetime.now(UTC) - timedelta(days=1),
        )
        db.add(profile)
        db.flush()
        db.add(
            ResourceBalance(
                profile_id=profile.id,
                cash=Decimal("500000"),
                capital=Decimal("250000"),
                influence=Decimal("500"),
                intelligence=Decimal("500"),
                logistics_capacity=Decimal("100"),
                personnel_capacity=Decimal("100"),
            )
        )
        profile_id = profile.id
        db.commit()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    return profile_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def _create_cartel(
    client: TestClient,
    headers: dict[str, str],
    *,
    name: str = "Rheinbund",
    tag: str = "RHB",
    key: str = "cartel-create-0001",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/cartels",
        headers={**headers, "Idempotency-Key": key},
        json={
            "name": name,
            "tag": tag,
            "archetype": "business_consortium",
            "description": "A test cartel",
            "governance_model": "directorate",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _invite_and_join(
    client: TestClient,
    leader_headers: dict[str, str],
    member_headers: dict[str, str],
    cartel_id: str,
    member_email: str,
    *,
    suffix: str,
) -> None:
    invitation = client.post(
        f"/api/v1/cartels/{cartel_id}/invitations",
        headers={**leader_headers, "Idempotency-Key": f"invite-{suffix}"},
        json={"email": member_email},
    )
    assert invitation.status_code == 201, invitation.text
    joined = client.post(
        f"/api/v1/cartels/{cartel_id}/join",
        headers={**member_headers, "Idempotency-Key": f"join-{suffix}"},
        json={"invitation_id": invitation.json()["id"]},
    )
    assert joined.status_code == 200, joined.text
    duplicate = client.post(
        f"/api/v1/cartels/{cartel_id}/join",
        headers={**member_headers, "Idempotency-Key": f"join-{suffix}"},
        json={"invitation_id": invitation.json()["id"]},
    )
    assert duplicate.status_code == 200


def test_cartel_creation_membership_roles_and_dissolution_guards(client: TestClient) -> None:
    leader_id, leader_headers = _create_player(
        client,
        "cartel-leader@example.com",
        "Cartel Leader",
    )
    member_id, member_headers = _create_player(
        client,
        "cartel-member@example.com",
        "Cartel Member",
    )
    cartel = _create_cartel(client, leader_headers)
    cartel_id = str(cartel["id"])
    duplicate = client.post(
        "/api/v1/cartels",
        headers={**leader_headers, "Idempotency-Key": "cartel-create-0001"},
        json={
            "name": "Rheinbund",
            "tag": "RHB",
            "archetype": "business_consortium",
            "description": "A test cartel",
            "governance_model": "directorate",
        },
    )
    assert duplicate.status_code == 201
    assert duplicate.json()["id"] == cartel_id
    second = client.post(
        "/api/v1/cartels",
        headers={**leader_headers, "Idempotency-Key": "cartel-create-0002"},
        json={
            "name": "Second cartel",
            "tag": "SEC",
            "archetype": "business_consortium",
        },
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "cartel.already_member"

    _invite_and_join(
        client,
        leader_headers,
        member_headers,
        cartel_id,
        "cartel-member@example.com",
        suffix="member",
    )
    role = client.patch(
        f"/api/v1/cartels/{cartel_id}/members/{member_id}",
        headers={**leader_headers, "Idempotency-Key": "role-finance"},
        json={"role": "finance_lead"},
    )
    assert role.status_code == 200
    assert role.json()["role"] == "finance_lead"
    transfer = client.post(
        f"/api/v1/cartels/{cartel_id}/leadership-transfer",
        headers={**leader_headers, "Idempotency-Key": "leader-transfer"},
        json={"target_profile_id": member_id},
    )
    assert transfer.status_code == 200
    duplicate_transfer = client.post(
        f"/api/v1/cartels/{cartel_id}/leadership-transfer",
        headers={**leader_headers, "Idempotency-Key": "leader-transfer"},
        json={"target_profile_id": member_id},
    )
    assert duplicate_transfer.status_code == 200
    left = client.post(
        f"/api/v1/cartels/{cartel_id}/leave",
        headers={**leader_headers, "Idempotency-Key": "leader-leaves"},
    )
    assert left.status_code == 200
    duplicate_leave = client.post(
        f"/api/v1/cartels/{cartel_id}/leave",
        headers={**leader_headers, "Idempotency-Key": "leader-leaves"},
    )
    assert duplicate_leave.status_code == 200
    protected = client.delete(
        f"/api/v1/cartels/{cartel_id}",
        headers={**member_headers, "Idempotency-Key": "dissolve-with-projectless"},
    )
    assert protected.status_code == 200
    duplicate_dissolution = client.delete(
        f"/api/v1/cartels/{cartel_id}",
        headers={**member_headers, "Idempotency-Key": "dissolve-with-projectless"},
    )
    assert duplicate_dissolution.status_code == 200

    with SessionLocal() as db:
        organization = db.get(Organization, cartel_id)
        assert organization is not None
        assert organization.status == "dissolved"
        memberships = list(
            db.scalars(
                select(OrganizationMembership).where(
                    OrganizationMembership.organization_id == cartel_id
                )
            )
        )
        assert {item.status for item in memberships} == {"left"}
        assert (
            db.scalar(
                select(func.count()).select_from(AuditLog).where(AuditLog.target_id == cartel_id)
            )
            >= 5
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(Account)
                .where(Account.owner_type == "organization", Account.owner_id == cartel_id)
            )
            == 1
        )
        leader_membership = next(item for item in memberships if item.profile_id == leader_id)
        assert leader_membership.role == "member"


def test_cartel_treasury_is_balanced_idempotent_and_requires_independent_approval(
    client: TestClient,
) -> None:
    leader_id, leader_headers = _create_player(
        client,
        "treasury-leader@example.com",
        "Treasury Leader",
    )
    finance_id, finance_headers = _create_player(
        client,
        "treasury-finance@example.com",
        "Treasury Finance",
    )
    cartel = _create_cartel(
        client,
        leader_headers,
        name="Treasury Guild",
        tag="TSY",
        key="treasury-cartel",
    )
    cartel_id = str(cartel["id"])
    _invite_and_join(
        client,
        leader_headers,
        finance_headers,
        cartel_id,
        "treasury-finance@example.com",
        suffix="finance",
    )
    assigned = client.patch(
        f"/api/v1/cartels/{cartel_id}/members/{finance_id}",
        headers={**leader_headers, "Idempotency-Key": "assign-finance"},
        json={"role": "finance_lead"},
    )
    assert assigned.status_code == 200

    deposit_headers = {**leader_headers, "Idempotency-Key": "cartel-deposit-0001"}
    first = client.post(
        f"/api/v1/cartels/{cartel_id}/treasury/deposit",
        headers=deposit_headers,
        json={"amount_cents": 2_000_000},
    )
    duplicate = client.post(
        f"/api/v1/cartels/{cartel_id}/treasury/deposit",
        headers=deposit_headers,
        json={"amount_cents": 2_000_000},
    )
    assert first.status_code == duplicate.status_code == 200
    assert first.json()["balance_cents"] == duplicate.json()["balance_cents"] == 2_000_000

    pending = client.post(
        f"/api/v1/cartels/{cartel_id}/treasury/expenses",
        headers={**finance_headers, "Idempotency-Key": "large-expense"},
        json={"amount_cents": 300_000, "purpose": "Strategic district permit"},
    )
    assert pending.status_code == 201
    assert pending.json()["status"] == "pending"
    expense_id = pending.json()["id"]
    self_approval = client.post(
        f"/api/v1/cartels/{cartel_id}/treasury/expenses/{expense_id}/approve",
        headers={**finance_headers, "Idempotency-Key": "self-approval"},
    )
    assert self_approval.status_code == 409
    assert self_approval.json()["error"]["code"] == "cartel.expense_self_approval"
    approved = client.post(
        f"/api/v1/cartels/{cartel_id}/treasury/expenses/{expense_id}/approve",
        headers={**leader_headers, "Idempotency-Key": "independent-approval"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by_profile_id"] == leader_id

    small = client.post(
        f"/api/v1/cartels/{cartel_id}/treasury/expenses",
        headers={**finance_headers, "Idempotency-Key": "small-expense"},
        json={"amount_cents": 100_000, "purpose": "Routine project supplies"},
    )
    assert small.status_code == 201
    assert small.json()["status"] == "approved"
    treasury = client.get(
        f"/api/v1/cartels/{cartel_id}/treasury",
        headers=leader_headers,
    )
    assert treasury.status_code == 200
    assert treasury.json()["balance_cents"] == 1_600_000

    with SessionLocal() as db:
        transactions = list(
            db.scalars(
                select(LedgerTransaction).where(
                    LedgerTransaction.reference_id.in_([cartel_id, expense_id])
                )
            )
        )
        assert transactions
        assert all(transaction_balance_cents(db, item.id) == 0 for item in transactions)
        expense = db.get(CartelExpense, expense_id)
        assert expense is not None
        expense.amount_cents += 1
        with pytest.raises(ValueError, match="request contract"):
            db.commit()
        db.rollback()


def test_concurrent_project_contributions_complete_influence_and_ranking(
    client: TestClient,
) -> None:
    leader_id, leader_headers = _create_player(
        client,
        "project-leader@example.com",
        "Project Leader",
    )
    member_id, member_headers = _create_player(
        client,
        "project-member@example.com",
        "Project Member",
    )
    cartel = _create_cartel(
        client,
        leader_headers,
        name="Project Network",
        tag="PRJ",
        key="project-cartel",
    )
    cartel_id = str(cartel["id"])
    _invite_and_join(
        client,
        leader_headers,
        member_headers,
        cartel_id,
        "project-member@example.com",
        suffix="project",
    )
    district = client.get("/api/v1/districts", headers=leader_headers).json()[0]
    with SessionLocal() as db:
        district_model = db.get(District, district["id"])
        assert district_model is not None and district_model.city_id is not None
        city_id = district_model.city_id

    for number in (1, 2):
        created = client.post(
            f"/api/v1/cartels/{cartel_id}/projects",
            headers={
                **leader_headers,
                "Idempotency-Key": f"media-project-{number}",
            },
            json={"project_type": "media_campaign", "district_id": district["id"]},
        )
        assert created.status_code == 201, created.text
        project_id = created.json()["id"]

        def contribute(
            headers: dict[str, str],
            amount: int,
            key: str,
            current_project_id: str = project_id,
        ) -> int:
            response = client.post(
                f"/api/v1/cartels/{cartel_id}/projects/{current_project_id}/contribute",
                headers={**headers, "Idempotency-Key": key},
                json={"resource_type": "cash", "amount_units": amount},
            )
            return response.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(
                pool.map(
                    lambda args: contribute(*args),
                    [
                        (leader_headers, 375_000, f"cash-leader-{number}"),
                        (member_headers, 375_000, f"cash-member-{number}"),
                    ],
                )
            )
        assert statuses == [200, 200]
        influence = client.post(
            f"/api/v1/cartels/{cartel_id}/projects/{project_id}/contribute",
            headers={
                **leader_headers,
                "Idempotency-Key": f"influence-project-{number}",
            },
            json={"resource_type": "influence", "amount_units": 60},
        )
        intelligence = client.post(
            f"/api/v1/cartels/{cartel_id}/projects/{project_id}/contribute",
            headers={
                **member_headers,
                "Idempotency-Key": f"intelligence-project-{number}",
            },
            json={"resource_type": "intelligence", "amount_units": 20},
        )
        assert influence.status_code == intelligence.status_code == 200
        assert intelligence.json()["status"] == "completed"
        duplicate = client.post(
            f"/api/v1/cartels/{cartel_id}/projects/{project_id}/contribute",
            headers={
                **member_headers,
                "Idempotency-Key": f"intelligence-project-{number}",
            },
            json={"resource_type": "intelligence", "amount_units": 20},
        )
        assert duplicate.status_code == 200
        assert duplicate.json()["contributed_intelligence"] == 20

    influence_map = client.get(
        f"/api/v1/influence/cities/{city_id}",
        headers=leader_headers,
    )
    assert influence_map.status_code == 200
    district_view = next(
        item for item in influence_map.json() if item["district_id"] == district["id"]
    )
    assert district_view["status"] == "controlled"
    assert district_view["controlling_cartel_id"] == cartel_id
    assert district_view["top_points"] == 110
    leaderboard = client.get(
        "/api/v1/leaderboards/cartels/current",
        headers=leader_headers,
    )
    assert leaderboard.status_code == 200
    assert leaderboard.json()[0]["cartel_id"] == cartel_id
    assert leaderboard.json()[0]["completed_projects"] == 2

    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(CartelProjectContribution)
                .where(CartelProjectContribution.organization_id == cartel_id)
            )
            == 8
        )
        influence = db.scalar(
            select(CartelDistrictInfluence).where(
                CartelDistrictInfluence.organization_id == cartel_id,
                CartelDistrictInfluence.district_id == district["id"],
            )
        )
        assert influence is not None and influence.points == 110
        point = db.scalar(
            select(TerritoryControlPoint).where(
                TerritoryControlPoint.district_id == district["id"],
                TerritoryControlPoint.point_type == "social_access",
            )
        )
        assert point is not None
        assert point.controlling_cartel_id == cartel_id
        assert point.status == "controlled"
        project = db.scalar(select(CartelProject).where(CartelProject.organization_id == cartel_id))
        assert project is not None
        project.required_influence += 1
        with pytest.raises(ValueError, match="contract"):
            db.commit()
        db.rollback()
        memberships = list(
            db.scalars(
                select(OrganizationMembership).where(
                    OrganizationMembership.profile_id.in_([leader_id, member_id]),
                    OrganizationMembership.status == "active",
                )
            )
        )
        assert len(memberships) == 2
