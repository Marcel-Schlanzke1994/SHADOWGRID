from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.models import (
    AuditLog,
    City,
    District,
    LedgerEntry,
    MarketTrade,
    ModerationReport,
    Organization,
    OrganizationMembership,
    PlayerProfile,
    PvpOperation,
    RealtimeEvent,
    ResourceBalance,
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
    *,
    protected: bool = False,
) -> tuple[str, str, dict[str, str]]:
    db = SessionLocal()
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
        protected_until=datetime.now(UTC)
        + (timedelta(days=2) if protected else -timedelta(days=2)),
    )
    db.add(profile)
    db.flush()
    db.add(
        ResourceBalance(
            profile_id=profile.id,
            cash=Decimal("500000"),
            capital=Decimal("250000"),
            influence=Decimal("100"),
            intelligence=Decimal("100"),
            logistics_capacity=Decimal("100"),
            personnel_capacity=Decimal("100"),
        )
    )
    profile_id = profile.id
    user_id = user.id
    db.commit()
    db.close()
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert login.status_code == 200
    return (
        profile_id,
        user_id,
        {"Authorization": f"Bearer {login.json()['access_token']}"},
    )


def _create_cartel(profile_id: str, name: str, tag: str) -> str:
    db = SessionLocal()
    profile = db.get(PlayerProfile, profile_id)
    assert profile is not None
    cartel = Organization(
        world_id=profile.world_id,
        city_id=profile.city_id,
        name=name,
        tag=tag,
        archetype="business_consortium",
        governance_model="directorate",
        treasury_cash=Decimal("250000"),
        treasury_capital=Decimal("250000"),
    )
    db.add(cartel)
    db.flush()
    db.add(
        OrganizationMembership(
            organization_id=cartel.id,
            profile_id=profile.id,
            role="director",
        )
    )
    cartel_id = cartel.id
    db.commit()
    db.close()
    return cartel_id


def test_pvp_lifecycle_is_idempotent_private_and_audited(client: TestClient) -> None:
    attacker_id, _, attacker_headers = _create_player(client, "attacker@example.com", "Attacker")
    defender_id, _, defender_headers = _create_player(client, "defender@example.com", "Defender")
    db = SessionLocal()
    district = db.scalar(select(District))
    assert district is not None
    district_id = district.id
    db.close()

    targets = client.get("/api/v1/pvp/targets", headers=attacker_headers)
    assert targets.status_code == 200
    assert {item["profile_id"] for item in targets.json()} == {defender_id}

    payload = {
        "defender_profile_id": defender_id,
        "operation_type": "intelligence_probe",
        "district_id": district_id,
        "risk_posture": "balanced",
    }
    preview = client.post("/api/v1/pvp/preview", headers=attacker_headers, json=payload)
    assert preview.status_code == 200
    assert preview.json()["can_launch"] is True

    launch_headers = {**attacker_headers, "Idempotency-Key": "pvp-launch-0001"}
    first = client.post("/api/v1/pvp/operations", headers=launch_headers, json=payload)
    duplicate = client.post("/api/v1/pvp/operations", headers=launch_headers, json=payload)
    assert first.status_code == duplicate.status_code == 201
    assert first.json()["id"] == duplicate.json()["id"]
    operation_id = first.json()["id"]
    second_session = client.post(
        "/api/v1/auth/login",
        json={"email": "attacker@example.com", "password": PASSWORD},
    )
    assert second_session.status_code == 200
    second_session_headers = {"Authorization": f"Bearer {second_session.json()['access_token']}"}
    same_operation = client.get(
        f"/api/v1/pvp/operations/{operation_id}", headers=second_session_headers
    )
    assert same_operation.status_code == 200

    defense = client.post(
        f"/api/v1/pvp/operations/{operation_id}/defend",
        headers=defender_headers,
        json={"action_type": "secure_information", "commitment": {"level": "standard"}},
    )
    assert defense.status_code == 200
    assert defense.json()["defense_submitted"] is True

    resolved = client.post(
        f"/api/v1/pvp/operations/{operation_id}/resolve",
        headers=second_session_headers,
    )
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    attacker_report_id = resolved.json()["my_report_id"]
    assert attacker_report_id

    defender_view = client.get(f"/api/v1/pvp/operations/{operation_id}", headers=defender_headers)
    assert defender_view.status_code == 200
    defender_report_id = defender_view.json()["my_report_id"]
    assert defender_report_id and defender_report_id != attacker_report_id

    attacker_report = client.get(
        f"/api/v1/pvp/reports/{attacker_report_id}", headers=attacker_headers
    )
    defender_report = client.get(
        f"/api/v1/pvp/reports/{defender_report_id}", headers=defender_headers
    )
    assert attacker_report.status_code == defender_report.status_code == 200
    assert attacker_report.json()["details_json"] != defender_report.json()["details_json"]
    assert "defense_action" not in attacker_report.json()["details_json"]
    assert defender_report.json()["details_json"]["defense_action"] == "secure_information"
    forbidden = client.get(f"/api/v1/pvp/reports/{defender_report_id}", headers=attacker_headers)
    assert forbidden.status_code == 404

    blocked = client.post(
        "/api/v1/pvp/operations",
        headers={**attacker_headers, "Idempotency-Key": "pvp-launch-0002"},
        json=payload,
    )
    assert blocked.status_code == 409
    assert "cooldown_active" in blocked.json()["error"]["reasons"]

    db = SessionLocal()
    assert db.scalar(select(func.count()).select_from(PvpOperation)) == 1
    assert (
        db.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .where(LedgerEntry.reason == "pvp_operation_reservation")
        )
        == 2
    )
    actions = set(db.scalars(select(AuditLog.action)))
    assert {"pvp.operation_launched", "pvp.defense_submitted", "pvp.operation_resolved"} <= actions
    event_types = set(db.scalars(select(RealtimeEvent.event_type)))
    assert {
        "pvp.operation_detected",
        "pvp.operation_updated",
        "pvp.operation_resolved",
    } <= event_types
    db.close()


def test_protection_blocks_pvp_and_communication_market_guards_work(
    client: TestClient,
) -> None:
    sender_id, _, sender_headers = _create_player(client, "sender@example.com", "Sender")
    protected_id, _, protected_headers = _create_player(
        client, "protected@example.com", "Protected", protected=True
    )

    preview = client.post(
        "/api/v1/pvp/preview",
        headers=sender_headers,
        json={
            "defender_profile_id": protected_id,
            "operation_type": "market_pressure",
            "risk_posture": "cautious",
        },
    )
    assert preview.status_code == 200
    assert preview.json()["can_launch"] is False
    assert "target_protected" in preview.json()["reasons"]

    blocked = client.post(
        "/api/v1/blocks",
        headers=protected_headers,
        json={"blocked_profile_id": sender_id},
    )
    assert blocked.status_code == 200
    direct = client.post(
        "/api/v1/messages",
        headers=sender_headers,
        json={"recipient_profile_id": protected_id, "body": "Hello"},
    )
    assert direct.status_code == 403
    assert direct.json()["error"]["code"] == "message.blocked"

    channels = client.get("/api/v1/chat/channels", headers=sender_headers)
    assert channels.status_code == 200
    city_channel = next(item for item in channels.json() if item["channel_type"] == "city")
    held = client.post(
        f"/api/v1/chat/channels/{city_channel['id']}/messages",
        headers=sender_headers,
        json={"body": "I will find your real address outside the game"},
    )
    assert held.status_code == 201
    assert held.json()["moderation_state"] == "held"
    assert held.json()["body"] == "Message held for moderator review."
    visible = client.get(
        f"/api/v1/chat/channels/{city_channel['id']}/messages", headers=sender_headers
    )
    assert visible.status_code == 200
    assert visible.json() == []

    offer_headers = {**sender_headers, "Idempotency-Key": "market-offer-0001"}
    offer_payload = {"resource_type": "intelligence", "amount": "5", "unit_price": "120"}
    offer = client.post("/api/v1/market/offers", headers=offer_headers, json=offer_payload)
    duplicate_offer = client.post(
        "/api/v1/market/offers", headers=offer_headers, json=offer_payload
    )
    assert offer.status_code == duplicate_offer.status_code == 201
    assert offer.json()["id"] == duplicate_offer.json()["id"]
    trade_headers = {**protected_headers, "Idempotency-Key": "market-trade-0001"}
    trade = client.post(f"/api/v1/market/offers/{offer.json()['id']}/accept", headers=trade_headers)
    duplicate_trade = client.post(
        f"/api/v1/market/offers/{offer.json()['id']}/accept", headers=trade_headers
    )
    assert trade.status_code == duplicate_trade.status_code == 200
    assert trade.json()["id"] == duplicate_trade.json()["id"]

    db = SessionLocal()
    report = db.scalar(
        select(ModerationReport).where(ModerationReport.target_id == held.json()["id"])
    )
    assert report is not None and report.risk_score == 90
    sender_balance = db.get(ResourceBalance, sender_id)
    buyer_balance = db.get(ResourceBalance, protected_id)
    assert sender_balance is not None and buyer_balance is not None
    assert sender_balance.intelligence == Decimal("95")
    assert sender_balance.cash == Decimal("500600")
    assert buyer_balance.intelligence == Decimal("105")
    assert buyer_balance.cash == Decimal("499400")
    db.close()


def test_territory_alliance_and_cartel_war_full_loop(client: TestClient) -> None:
    alpha_id, _, alpha_headers = _create_player(client, "alpha@example.com", "Alpha")
    beta_id, _, beta_headers = _create_player(client, "beta@example.com", "Beta")
    gamma_id, _, gamma_headers = _create_player(client, "gamma@example.com", "Gamma")
    alpha_cartel = _create_cartel(alpha_id, "Alpha Network", "ALP")
    beta_cartel = _create_cartel(beta_id, "Beta Network", "BET")
    gamma_cartel = _create_cartel(gamma_id, "Gamma Network", "GAM")
    db = SessionLocal()
    district = db.scalar(select(District))
    city = db.scalar(select(City))
    assert district is not None and city is not None
    district_id = district.id
    city_id = city.id
    db.close()

    claim = client.post(
        f"/api/v1/territories/{district_id}/claim",
        headers={**alpha_headers, "Idempotency-Key": "territory-claim-0001"},
        json={"claim_type": "influence"},
    )
    assert claim.status_code == 201
    for index in range(2):
        support = client.post(
            f"/api/v1/territories/{district_id}/support",
            headers={
                **alpha_headers,
                "Idempotency-Key": f"territory-support-000{index + 1}",
            },
            json={"contribution_type": "economic", "amount": "25"},
        )
        assert support.status_code == 200
    territory = client.get(f"/api/v1/territories/{district_id}", headers=alpha_headers)
    assert territory.status_code == 200
    assert territory.json()["controlling_cartel_id"] == alpha_cartel

    alliance = client.post(
        "/api/v1/alliances",
        headers=alpha_headers,
        json={
            "name": "Vesper Accord",
            "tag": "VAC",
            "charter": "Mutual coordination and transparent defensive support.",
            "governance_model": "council",
        },
    )
    assert alliance.status_code == 201
    alliance_id = alliance.json()["id"]
    invitation = client.post(
        f"/api/v1/alliances/{alliance_id}/invite",
        headers=alpha_headers,
        json={"cartel_id": beta_cartel, "contribution_limit": "25"},
    )
    assert invitation.status_code == 200
    accepted = client.post(f"/api/v1/alliances/{alliance_id}/accept", headers=beta_headers)
    assert accepted.status_code == 200
    alliance_view = client.get(f"/api/v1/alliances/{alliance_id}", headers=beta_headers)
    assert alliance_view.status_code == 200
    assert alliance_view.json()["member_count"] == 2
    allied_preview = client.post(
        "/api/v1/pvp/preview",
        headers=alpha_headers,
        json={
            "defender_profile_id": beta_id,
            "operation_type": "intelligence_probe",
            "risk_posture": "balanced",
        },
    )
    assert allied_preview.status_code == 200
    assert allied_preview.json()["can_launch"] is False
    assert "alliance_partner" in allied_preview.json()["reasons"]

    proposal = client.post(
        "/api/v1/cartel-wars/propose",
        headers=alpha_headers,
        json={
            "defender_cartel_id": gamma_cartel,
            "war_type": "district_control",
            "city_id": city_id,
            "district_id": district_id,
            "declaration_reason": "Competing claims require a bounded strategic contest.",
            "demand": "Withdraw the competing claim.",
            "peace_conditions": "Accept the recorded district result.",
        },
    )
    assert proposal.status_code == 201
    war_id = proposal.json()["id"]
    wrong_password = client.post(
        f"/api/v1/cartel-wars/{war_id}/declare",
        headers=alpha_headers,
        json={"password": "wrong-password"},
    )
    assert wrong_password.status_code == 403
    declared = client.post(
        f"/api/v1/cartel-wars/{war_id}/declare",
        headers=alpha_headers,
        json={"password": PASSWORD},
    )
    assert declared.status_code == 200
    active = client.get(f"/api/v1/cartel-wars/{war_id}", headers=alpha_headers)
    assert active.status_code == 200
    assert active.json()["war_status"] == "active"

    assert (
        client.post(
            f"/api/v1/cartel-wars/{war_id}/join",
            headers=alpha_headers,
            json={"side": "attacker"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            f"/api/v1/cartel-wars/{war_id}/join",
            headers=gamma_headers,
            json={"side": "defender"},
        ).status_code
        == 200
    )
    operation_headers = {**alpha_headers, "Idempotency-Key": "war-operation-0001"}
    operation_payload = {
        "operation_type": "territorial",
        "district_id": district_id,
        "cash": "5000",
        "influence": "1",
    }
    operation = client.post(
        f"/api/v1/cartel-wars/{war_id}/launch-operation",
        headers=operation_headers,
        json=operation_payload,
    )
    duplicate_operation = client.post(
        f"/api/v1/cartel-wars/{war_id}/launch-operation",
        headers=operation_headers,
        json=operation_payload,
    )
    assert operation.status_code == duplicate_operation.status_code == 200
    assert operation.json()["id"] == duplicate_operation.json()["id"]
    scores = client.get(f"/api/v1/cartel-wars/{war_id}/score", headers=alpha_headers)
    assert scores.status_code == 200
    alpha_score = next(item for item in scores.json() if item["cartel_id"] == alpha_cartel)
    assert Decimal(alpha_score["total"]) > 0
    outsider = client.get(f"/api/v1/cartel-wars/{war_id}/score", headers=beta_headers)
    assert outsider.status_code == 403

    offered = client.post(
        f"/api/v1/cartel-wars/{war_id}/offer-ceasefire",
        headers=alpha_headers,
        json={"terms": {"district": district_id, "cooldown_days": 7}},
    )
    assert offered.status_code == 200
    ceasefire = client.post(f"/api/v1/cartel-wars/{war_id}/accept-ceasefire", headers=gamma_headers)
    assert ceasefire.status_code == 200
    ended = client.get(f"/api/v1/cartel-wars/{war_id}", headers=gamma_headers)
    assert ended.status_code == 200
    assert ended.json()["war_status"] == "ended"
    assert ended.json()["resolution_type"] == "ceasefire"


def test_concurrent_market_acceptance_settles_exactly_once(client: TestClient) -> None:
    seller_id, _, seller_headers = _create_player(client, "seller@example.com", "Seller")
    buyer_one_id, _, buyer_one_headers = _create_player(
        client, "buyer-one@example.com", "Buyer One"
    )
    buyer_two_id, _, buyer_two_headers = _create_player(
        client, "buyer-two@example.com", "Buyer Two"
    )
    offer = client.post(
        "/api/v1/market/offers",
        headers={**seller_headers, "Idempotency-Key": "concurrent-offer-0001"},
        json={"resource_type": "intelligence", "amount": "5", "unit_price": "120"},
    )
    assert offer.status_code == 201
    offer_id = offer.json()["id"]

    def accept(headers: dict[str, str], key: str) -> int:
        response = client.post(
            f"/api/v1/market/offers/{offer_id}/accept",
            headers={**headers, "Idempotency-Key": key},
        )
        return int(response.status_code)

    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(
            pool.map(
                lambda args: accept(*args),
                (
                    (buyer_one_headers, "concurrent-trade-0001"),
                    (buyer_two_headers, "concurrent-trade-0002"),
                ),
            )
        )
    assert statuses.count(200) == 1
    assert all(status in {200, 404, 409} for status in statuses)

    db = SessionLocal()
    assert db.scalar(select(func.count()).select_from(MarketTrade)) == 1
    seller = db.get(ResourceBalance, seller_id)
    buyer_one = db.get(ResourceBalance, buyer_one_id)
    buyer_two = db.get(ResourceBalance, buyer_two_id)
    assert seller is not None and buyer_one is not None and buyer_two is not None
    assert seller.cash == Decimal("500600")
    assert seller.intelligence == Decimal("95")
    assert buyer_one.cash + buyer_two.cash == Decimal("999400")
    assert buyer_one.intelligence + buyer_two.intelligence == Decimal("205")
    db.close()
