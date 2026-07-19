from __future__ import annotations

import os
from collections.abc import Generator

os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = "sqlite:///./shadowgrid-test.db"
os.environ["SECRET_KEY"] = "test-secret-key-with-at-least-thirty-two-characters"
os.environ["REFRESH_PEPPER"] = "test-refresh-pepper-with-at-least-thirty-two-characters"
os.environ["SEED_SECRET"] = "test-seed-secret-with-at-least-thirty-two-characters"
os.environ["TEST_OPERATION_SECONDS"] = "0"
os.environ["ALLOW_EXTERNAL_DEPLOY"] = "false"

import pytest
from fastapi.testclient import TestClient
from shadowgrid.database import Base, SessionLocal, engine
from shadowgrid.game_config import DISTRICTS
from shadowgrid.main import app
from shadowgrid.models import District, User, World
from shadowgrid.security import hash_password
from sqlalchemy import select


@pytest.fixture(autouse=True)
def clean_database() -> Generator[None]:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    world = World(
        slug="test-world",
        name="Test Vesper",
        status="active",
        ends_at=__import__("datetime").datetime.now(__import__("datetime").UTC)
        + __import__("datetime").timedelta(days=14),
    )
    db.add(world)
    db.flush()
    for data in DISTRICTS:
        db.add(
            District(
                world_id=world.id,
                slug=data[0],
                name=data[1],
                prosperity=data[2],
                employment=data[3],
                safety=data[4],
                authority_presence=data[5],
                digital_infrastructure=data[6],
                property_value=data[7],
                public_trust=data[8],
                media_attention=data[9],
                economic_activity=data[10],
                social_stability=data[11],
                map_x=data[12],
                map_y=data[13],
                map_points=data[14],
            )
        )
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client() -> Generator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def verified_user() -> User:
    db = SessionLocal()
    user = User(
        email="player@example.com",
        password_hash=hash_password("StrongPassword123"),
        display_name="Test Player",
        email_verified=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.expunge(user)
    db.close()
    return user


@pytest.fixture
def auth_headers(client: TestClient, verified_user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login", json={"email": verified_user.email, "password": "StrongPassword123"}
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def joined_profile(client: TestClient, auth_headers: dict[str, str]) -> dict[str, object]:
    db = SessionLocal()
    world = db.scalar(select(World))
    district = db.scalar(select(District))
    assert world and district
    response = client.post(
        f"/api/v1/worlds/{world.id}/join",
        headers={**auth_headers, "Idempotency-Key": "test-world-join-0001"},
        json={
            "codename": "Test Network",
            "archetype": "business_consortium",
            "home_district_id": district.id,
        },
    )
    db.close()
    assert response.status_code == 200
    return response.json()
