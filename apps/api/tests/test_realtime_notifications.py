from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.domain import create_notification
from shadowgrid.models import (
    District,
    Organization,
    OrganizationMembership,
    PlayerProfile,
    RealtimeEvent,
    User,
    World,
)
from shadowgrid.realtime import emit_realtime_event
from shadowgrid.security import hash_password
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

PASSWORD = "StrongPassword123"


def _join_player(
    client: TestClient,
    *,
    suffix: str,
) -> tuple[dict[str, str], str, str]:
    email = f"realtime-{suffix}@example.com"
    with SessionLocal() as db:
        world = db.scalar(select(World))
        district = db.scalar(select(District))
        assert world is not None and district is not None
        db.add(
            User(
                email=email,
                password_hash=hash_password(PASSWORD),
                display_name=f"Realtime {suffix}",
                email_verified=True,
            )
        )
        db.commit()
        world_id = world.id
        district_id = district.id
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200, login.text
    token = str(login.json()["access_token"])
    headers = {"Authorization": f"Bearer {token}"}
    joined = client.post(
        f"/api/v1/worlds/{world_id}/join",
        headers={**headers, "Idempotency-Key": f"realtime-join-{suffix}"},
        json={
            "codename": f"Realtime {suffix}",
            "archetype": "business_consortium",
            "home_district_id": district_id,
        },
    )
    assert joined.status_code == 200, joined.text
    return headers, str(joined.json()["id"]), token


def _event_ids(client: TestClient, headers: dict[str, str]) -> set[str]:
    response = client.get("/api/v1/realtime/events", headers=headers)
    assert response.status_code == 200, response.text
    return {str(item["id"]) for item in response.json()}


def test_versioned_payload_validation_deduplication_and_immutability(
    client: TestClient,
) -> None:
    _, profile_id, _ = _join_player(client, suffix="validation")
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        assert profile is not None
        with pytest.raises(ValueError, match="missing fields"):
            emit_realtime_event(
                db,
                world_id=profile.world_id,
                event_type="exchange.order.updated",
                payload={"order_id": "order-1"},
            )
        with pytest.raises(ValueError, match="16 KiB"):
            emit_realtime_event(
                db,
                world_id=profile.world_id,
                event_type="game.notice.created",
                payload={"body": "x" * 17_000},
            )
        first = emit_realtime_event(
            db,
            world_id=profile.world_id,
            event_type="player.resources.updated",
            payload={
                "profile_id": profile.id,
                "resource_type": "cash",
                "balance_cents": 8_000_000,
            },
            audience_type="player",
            audience_id=profile.id,
            dedupe_key="realtime-validation-event",
        )
        repeated = emit_realtime_event(
            db,
            world_id=profile.world_id,
            event_type="player.resources.updated",
            payload={
                "profile_id": profile.id,
                "resource_type": "cash",
                "balance_cents": 8_000_000,
            },
            audience_type="player",
            audience_id=profile.id,
            dedupe_key="realtime-validation-event",
        )
        assert first.id == repeated.id
        db.commit()
        first.event_version = 2
        with pytest.raises(ValueError, match="immutable"):
            db.flush()


def test_world_city_cartel_and_player_audiences_are_isolated(
    client: TestClient,
) -> None:
    first_headers, first_id, _ = _join_player(client, suffix="first")
    second_headers, second_id, _ = _join_player(client, suffix="second")
    outsider_headers, outsider_id, _ = _join_player(client, suffix="outsider")
    with SessionLocal() as db:
        first = db.get(PlayerProfile, first_id)
        second = db.get(PlayerProfile, second_id)
        outsider = db.get(PlayerProfile, outsider_id)
        assert first is not None and second is not None and outsider is not None
        cartel = Organization(
            world_id=first.world_id,
            city_id=first.city_id,
            name="Realtime Circle",
            tag="RTC",
            archetype="business_consortium",
            description="Room isolation fixture.",
            governance_model="directorate",
        )
        db.add(cartel)
        db.flush()
        db.add_all(
            (
                OrganizationMembership(
                    organization_id=cartel.id,
                    profile_id=first.id,
                    role="leader",
                    status="active",
                ),
                OrganizationMembership(
                    organization_id=cartel.id,
                    profile_id=second.id,
                    role="member",
                    status="active",
                ),
            )
        )
        db.flush()
        world_event = emit_realtime_event(
            db,
            world_id=first.world_id,
            event_type="game.world_notice.created",
            payload={"notice_id": "world"},
            dedupe_key="room-world",
        )
        city_event = emit_realtime_event(
            db,
            world_id=first.world_id,
            event_type="market.snapshot.created",
            payload={"tick_id": "tick-city"},
            audience_type="city",
            audience_id=first.city_id,
            dedupe_key="room-city",
        )
        cartel_event = emit_realtime_event(
            db,
            world_id=first.world_id,
            event_type="cartel.project.updated",
            payload={"project_id": "project-room", "status": "active"},
            audience_type="cartel",
            audience_id=cartel.id,
            dedupe_key="room-cartel",
        )
        first_event = emit_realtime_event(
            db,
            world_id=first.world_id,
            event_type="game.private_notice.created",
            payload={"notice_id": "first"},
            audience_type="player",
            audience_id=first.id,
            dedupe_key="room-first",
        )
        second_event = emit_realtime_event(
            db,
            world_id=first.world_id,
            event_type="game.private_notice.created",
            payload={"notice_id": "second"},
            audience_type="player",
            audience_id=second.id,
            dedupe_key="room-second",
        )
        db.commit()

    first_ids = _event_ids(client, first_headers)
    second_ids = _event_ids(client, second_headers)
    outsider_ids = _event_ids(client, outsider_headers)
    common = {world_event.id, city_event.id}
    assert common | {cartel_event.id, first_event.id} <= first_ids
    assert common | {cartel_event.id, second_event.id} <= second_ids
    assert common <= outsider_ids
    assert second_event.id not in first_ids
    assert first_event.id not in second_ids
    assert cartel_event.id not in outsider_ids
    assert first_event.id not in outsider_ids
    assert second_event.id not in outsider_ids

    first_channels = client.get(
        "/api/v1/realtime/channels",
        headers=first_headers,
    )
    outsider_channels = client.get(
        "/api/v1/realtime/channels",
        headers=outsider_headers,
    )
    assert first_channels.status_code == outsider_channels.status_code == 200
    assert f"cartel:{cartel.id}" in first_channels.json()["channels"]
    assert all(
        not channel.startswith("cartel:") for channel in outsider_channels.json()["channels"]
    )

    after_world = client.get(
        f"/api/v1/realtime/events?after_id={world_event.id}",
        headers=first_headers,
    )
    assert after_world.status_code == 200
    assert world_event.id not in {item["id"] for item in after_world.json()}
    foreign_cursor = client.get(
        f"/api/v1/realtime/events?after_id={second_event.id}",
        headers=first_headers,
    )
    assert foreign_cursor.status_code == 404
    assert foreign_cursor.json()["error"]["code"] == "realtime.cursor_not_found"


def test_authenticated_websocket_reconnect_resumes_after_durable_cursor(
    client: TestClient,
) -> None:
    headers, profile_id, token = _join_player(client, suffix="socket")
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        assert profile is not None
        world_id = profile.world_id

    with client.websocket_connect("/api/v1/ws") as socket:
        socket.send_json(
            {
                "access_token": token,
                "world_id": world_id,
                "protocol_version": 1,
            }
        )
        connected = socket.receive_json()
        assert connected["type"] == "connected"
        assert connected["event_version"] == 1
        assert f"player:{profile_id}" in connected["payload"]["channels"]
        with SessionLocal() as db:
            first = emit_realtime_event(
                db,
                world_id=world_id,
                event_type="game.socket_notice.created",
                payload={"notice_id": "socket-first"},
                audience_type="player",
                audience_id=profile_id,
                dedupe_key="socket-first",
            )
            db.commit()
            first_id = first.id
        received = socket.receive_json()
        assert received["event_id"] == first_id
        assert received["event_version"] == 1
        assert received["channel"] == f"player:{profile_id}"

    with SessionLocal() as db:
        second = emit_realtime_event(
            db,
            world_id=world_id,
            event_type="game.socket_notice.created",
            payload={"notice_id": "socket-second"},
            audience_type="player",
            audience_id=profile_id,
            dedupe_key="socket-second",
        )
        db.commit()
        second_id = second.id

    with client.websocket_connect("/api/v1/ws") as resumed_socket:
        resumed_socket.send_json(
            {
                "access_token": token,
                "world_id": world_id,
                "last_event_id": first_id,
                "protocol_version": 1,
            }
        )
        connected = resumed_socket.receive_json()
        assert connected["payload"]["resumed_after"] == first_id
        resumed = resumed_socket.receive_json()
        assert resumed["event_id"] == second_id

    with client.websocket_connect("/api/v1/ws") as invalid_socket:
        invalid_socket.send_json({"access_token": "short"})
        with pytest.raises(WebSocketDisconnect) as error:
            invalid_socket.receive_json()
        assert error.value.code == 4400

    with client.websocket_connect("/api/v1/ws") as oversized_socket:
        oversized_socket.send_text("x" * 16_385)
        with pytest.raises(WebSocketDisconnect) as error:
            oversized_socket.receive_json()
        assert error.value.code == 1009

    feed = client.get("/api/v1/realtime/events", headers=headers)
    assert feed.status_code == 200
    assert {item["id"] for item in feed.json()} >= {first_id, second_id}


def test_notifications_have_unread_read_all_and_owner_isolation(
    client: TestClient,
) -> None:
    first_headers, first_id, _ = _join_player(client, suffix="notify-first")
    second_headers, _, _ = _join_player(client, suffix="notify-second")
    with SessionLocal() as db:
        first = db.get(PlayerProfile, first_id)
        assert first is not None
        first_notification = create_notification(
            db,
            first.user_id,
            "company.warning.created",
            "Company liquidity warning",
            "An abstract payment warning requires review.",
            {"company_id": "company-1", "severity": "warning"},
        )
        second_notification = create_notification(
            db,
            first.user_id,
            "cartel.invitation.created",
            "Cartel invitation",
            "An invitation is waiting.",
            {"cartel_id": "cartel-1"},
        )
        db.commit()
        first_notification_id = first_notification.id
        second_notification_id = second_notification.id

    unread = client.get(
        "/api/v1/notifications?unread_only=true",
        headers=first_headers,
    )
    count = client.get(
        "/api/v1/notifications/unread-count",
        headers=first_headers,
    )
    assert unread.status_code == count.status_code == 200
    assert {item["id"] for item in unread.json()} == {
        first_notification_id,
        second_notification_id,
    }
    assert count.json() == {"unread_count": 2}
    assert unread.json()[0]["metadata_json"]

    foreign_read = client.post(
        f"/api/v1/notifications/{first_notification_id}/read",
        headers=second_headers,
    )
    assert foreign_read.status_code == 404
    first_read = client.post(
        f"/api/v1/notifications/{first_notification_id}/read",
        headers=first_headers,
    )
    repeated_read = client.post(
        f"/api/v1/notifications/{first_notification_id}/read",
        headers=first_headers,
    )
    assert first_read.status_code == repeated_read.status_code == 200
    assert client.get(
        "/api/v1/notifications/unread-count",
        headers=first_headers,
    ).json() == {"unread_count": 1}
    read_all = client.post(
        "/api/v1/notifications/read-all",
        headers=first_headers,
    )
    repeated_all = client.post(
        "/api/v1/notifications/read-all",
        headers=first_headers,
    )
    assert read_all.status_code == repeated_all.status_code == 200
    assert client.get(
        "/api/v1/notifications/unread-count",
        headers=first_headers,
    ).json() == {"unread_count": 0}
    assert (
        client.get(
            "/api/v1/notifications?unread_only=true",
            headers=first_headers,
        ).json()
        == []
    )
    with SessionLocal() as db:
        notification_event = db.scalar(
            select(RealtimeEvent).where(
                RealtimeEvent.event_type == "notification.created",
                RealtimeEvent.audience_id == first_id,
            )
        )
        assert notification_event is not None
        assert notification_event.event_version == 1
        assert notification_event.audience_type == "player"


def test_expired_events_are_not_replayed(client: TestClient) -> None:
    headers, profile_id, _ = _join_player(client, suffix="expiry")
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        assert profile is not None
        expired = RealtimeEvent(
            world_id=profile.world_id,
            profile_id=profile.id,
            event_type="game.expired_notice.created",
            event_version=1,
            audience_type="player",
            audience_id=profile.id,
            payload_json={"notice_id": "expired"},
            created_at=datetime.now(UTC) - timedelta(days=2),
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        db.add(expired)
        db.commit()
        expired_id = expired.id
    assert expired_id not in _event_ids(client, headers)
