from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from shadowgrid.config import get_settings
from shadowgrid.contracts import advance_contracts, available_capacity_units
from shadowgrid.database import SessionLocal
from shadowgrid.finance import transaction_balance_cents
from shadowgrid.models import (
    AuditLog,
    CommercialContract,
    Company,
    ContractBid,
    ContractSettlement,
    ContractTender,
    District,
    LedgerTransaction,
    RealtimeEvent,
    User,
    World,
)
from shadowgrid.security import hash_password
from sqlalchemy import func, select

PASSWORD = "StrongPassword123"


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _join_player(
    client: TestClient,
    *,
    suffix: str,
) -> tuple[dict[str, str], str]:
    email = f"contract-{suffix}@example.com"
    with SessionLocal() as db:
        world = db.scalar(select(World))
        district = db.scalar(select(District))
        assert world is not None and district is not None
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            display_name=f"Contract {suffix}",
            email_verified=True,
        )
        db.add(user)
        db.commit()
        world_id = world.id
        district_id = district.id
    headers = _login(client, email)
    joined = client.post(
        f"/api/v1/worlds/{world_id}/join",
        headers={**headers, "Idempotency-Key": f"contract-join-{suffix}"},
        json={
            "codename": f"Contract {suffix}",
            "archetype": "business_consortium",
            "home_district_id": district_id,
        },
    )
    assert joined.status_code == 200, joined.text
    return headers, str(joined.json()["id"])


def _create_company(
    client: TestClient,
    headers: dict[str, str],
    *,
    suffix: str,
) -> str:
    district = client.get("/api/v1/districts", headers=headers).json()[0]
    response = client.post(
        "/api/v1/companies",
        headers={**headers, "Idempotency-Key": f"contract-company-{suffix}"},
        json={
            "name": f"Contract {suffix} GmbH",
            "industry": "logistics",
            "district_id": district["id"],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _create_tender(
    client: TestClient,
    headers: dict[str, str],
    company_id: str,
    *,
    key: str,
    price_cents: int = 200_000,
    periods: int = 2,
    submission_minutes: int = 60,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/contracts/tenders",
        headers={**headers, "Idempotency-Key": key},
        json={
            "issuer_company_id": company_id,
            "contract_type": "supply",
            "title": "Regional logistics supply",
            "description": "A fictional capacity contract.",
            "max_price_cents": price_cents,
            "duration_periods": periods,
            "capacity_units": 10,
            "min_reputation_bps": 0,
            "min_compliance_bps": 0,
            "submission_minutes": submission_minutes,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _submit_bid(
    client: TestClient,
    headers: dict[str, str],
    tender_id: str,
    company_id: str,
    *,
    key: str,
    price_cents: int,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/contracts/tenders/{tender_id}/bids",
        headers={**headers, "Idempotency-Key": key},
        json={
            "bidder_company_id": company_id,
            "price_cents": price_cents,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_tender_bid_award_capacity_visibility_and_idempotency(
    client: TestClient,
) -> None:
    issuer_headers, _ = _join_player(client, suffix="issuer")
    bidder_headers, _ = _join_player(client, suffix="bidder")
    issuer_company_id = _create_company(client, issuer_headers, suffix="Issuer")
    bidder_company_id = _create_company(client, bidder_headers, suffix="Bidder")

    tender = _create_tender(
        client,
        issuer_headers,
        issuer_company_id,
        key="contract-tender-001",
    )
    duplicate_tender = _create_tender(
        client,
        issuer_headers,
        issuer_company_id,
        key="contract-tender-001",
    )
    assert duplicate_tender["id"] == tender["id"]

    forbidden = client.post(
        "/api/v1/contracts/tenders",
        headers={**bidder_headers, "Idempotency-Key": "contract-not-owned"},
        json={
            "issuer_company_id": issuer_company_id,
            "contract_type": "service",
            "title": "Unauthorized tender",
            "description": "",
            "max_price_cents": 100_000,
            "duration_periods": 2,
            "capacity_units": 5,
            "submission_minutes": 60,
        },
    )
    assert forbidden.status_code == 403

    bid = _submit_bid(
        client,
        bidder_headers,
        str(tender["id"]),
        bidder_company_id,
        key="contract-bid-001",
        price_cents=180_000,
    )
    duplicate_bid = _submit_bid(
        client,
        bidder_headers,
        str(tender["id"]),
        bidder_company_id,
        key="contract-bid-001",
        price_cents=180_000,
    )
    assert duplicate_bid["id"] == bid["id"]
    assert int(bid["score_points"]) > 0
    assert "price_advantage_bps" in bid["score_breakdown_json"]

    bidder_view = client.get(
        f"/api/v1/contracts/tenders/{tender['id']}/bids",
        headers=bidder_headers,
    )
    issuer_view = client.get(
        f"/api/v1/contracts/tenders/{tender['id']}/bids",
        headers=issuer_headers,
    )
    assert bidder_view.status_code == issuer_view.status_code == 200
    assert len(bidder_view.json()) == len(issuer_view.json()) == 1

    forbidden_award = client.post(
        f"/api/v1/contracts/tenders/{tender['id']}/award",
        headers={**bidder_headers, "Idempotency-Key": "contract-award-forbidden"},
        json={"bid_id": bid["id"]},
    )
    assert forbidden_award.status_code == 403
    award_headers = {
        **issuer_headers,
        "Idempotency-Key": "contract-award-001",
    }
    awarded = client.post(
        f"/api/v1/contracts/tenders/{tender['id']}/award",
        headers=award_headers,
        json={"bid_id": bid["id"]},
    )
    repeated = client.post(
        f"/api/v1/contracts/tenders/{tender['id']}/award",
        headers=award_headers,
        json={"bid_id": bid["id"]},
    )
    assert awarded.status_code == repeated.status_code == 201
    assert awarded.json()["id"] == repeated.json()["id"]
    assert awarded.json()["reserved_capacity_units"] == 10

    with SessionLocal() as db:
        bidder_company = db.get(Company, bidder_company_id)
        stored_bid = db.get(ContractBid, bid["id"])
        assert bidder_company is not None and stored_bid is not None
        assert available_capacity_units(db, bidder_company) == bidder_company.capacity - 10
        stored_bid.price_cents += 1
        with pytest.raises(ValueError, match="immutable"):
            db.flush()


def test_paid_contract_periods_use_balanced_ledger_and_complete_once(
    client: TestClient,
) -> None:
    issuer_headers, _ = _join_player(client, suffix="payer")
    bidder_headers, _ = _join_player(client, suffix="provider")
    issuer_company_id = _create_company(client, issuer_headers, suffix="Payer")
    bidder_company_id = _create_company(client, bidder_headers, suffix="Provider")
    tender = _create_tender(
        client,
        issuer_headers,
        issuer_company_id,
        key="contract-paid-tender",
        price_cents=200_000,
        periods=2,
    )
    bid = _submit_bid(
        client,
        bidder_headers,
        str(tender["id"]),
        bidder_company_id,
        key="contract-paid-bid",
        price_cents=150_000,
    )
    awarded = client.post(
        f"/api/v1/contracts/tenders/{tender['id']}/award",
        headers={**issuer_headers, "Idempotency-Key": "contract-paid-award"},
        json={"bid_id": bid["id"]},
    )
    assert awarded.status_code == 201, awarded.text
    contract_id = str(awarded.json()["id"])

    with SessionLocal() as db:
        contract = db.get(CommercialContract, contract_id)
        issuer = db.get(Company, issuer_company_id)
        provider = db.get(Company, bidder_company_id)
        assert contract is not None and issuer is not None and provider is not None
        issuer_before = issuer.account.balance_cents
        provider_before = provider.account.balance_cents
        reputation_before = (issuer.reputation_bps, provider.reputation_bps)
        at = contract.next_settlement_at + timedelta(
            minutes=get_settings().contract_settlement_interval_minutes
        )
        result = advance_contracts(db, get_settings(), at=at)
        assert result == {
            "tenders_expired": 0,
            "periods_settled": 2,
            "contracts_breached": 0,
            "contracts_completed": 1,
        }
        stored = db.get(CommercialContract, contract_id)
        db.refresh(issuer)
        db.refresh(provider)
        assert stored is not None and stored.status == "completed"
        assert issuer.account.balance_cents == issuer_before - 300_000
        assert provider.account.balance_cents == provider_before + 300_000
        assert issuer.reputation_bps == reputation_before[0] + 250
        assert provider.reputation_bps == reputation_before[1] + 250
        settlements = list(
            db.scalars(
                select(ContractSettlement)
                .where(ContractSettlement.contract_id == contract_id)
                .order_by(ContractSettlement.period_number)
            )
        )
        assert [item.status for item in settlements] == ["paid", "paid"]
        for settlement in settlements:
            assert settlement.transaction_id is not None
            assert transaction_balance_cents(db, settlement.transaction_id) == 0
        counts = (
            db.scalar(
                select(func.count())
                .select_from(ContractSettlement)
                .where(ContractSettlement.contract_id == contract_id)
            ),
            db.scalar(
                select(func.count())
                .select_from(LedgerTransaction)
                .where(LedgerTransaction.transaction_type == "contract_settlement")
            ),
        )
        assert advance_contracts(db, get_settings(), at=at) == {
            "tenders_expired": 0,
            "periods_settled": 0,
            "contracts_breached": 0,
            "contracts_completed": 0,
        }
        assert (
            db.scalar(
                select(func.count())
                .select_from(ContractSettlement)
                .where(ContractSettlement.contract_id == contract_id)
            ),
            db.scalar(
                select(func.count())
                .select_from(LedgerTransaction)
                .where(LedgerTransaction.transaction_type == "contract_settlement")
            ),
        ) == counts


def test_payment_default_and_tender_expiry_are_abstract_and_retry_safe(
    client: TestClient,
) -> None:
    issuer_headers, _ = _join_player(client, suffix="defaulting")
    bidder_headers, _ = _join_player(client, suffix="protected")
    issuer_company_id = _create_company(client, issuer_headers, suffix="Defaulting")
    bidder_company_id = _create_company(client, bidder_headers, suffix="Protected")
    tender = _create_tender(
        client,
        issuer_headers,
        issuer_company_id,
        key="contract-default-tender",
        price_cents=2_500_000,
        periods=2,
    )
    bid = _submit_bid(
        client,
        bidder_headers,
        str(tender["id"]),
        bidder_company_id,
        key="contract-default-bid",
        price_cents=2_500_000,
    )
    awarded = client.post(
        f"/api/v1/contracts/tenders/{tender['id']}/award",
        headers={**issuer_headers, "Idempotency-Key": "contract-default-award"},
        json={"bid_id": bid["id"]},
    )
    assert awarded.status_code == 201, awarded.text

    expiring = _create_tender(
        client,
        issuer_headers,
        issuer_company_id,
        key="contract-expiring-tender",
        submission_minutes=5,
    )
    with SessionLocal() as db:
        contract = db.get(CommercialContract, awarded.json()["id"])
        issuer = db.get(Company, issuer_company_id)
        expiring_tender = db.get(ContractTender, expiring["id"])
        assert contract is not None and issuer is not None and expiring_tender is not None
        reputation_before = issuer.reputation_bps
        pressure_before = issuer.investigation_pressure_bps
        at = max(contract.next_settlement_at, expiring_tender.submission_ends_at) + timedelta(
            seconds=1
        )
        result = advance_contracts(db, get_settings(), at=at)
        assert result["contracts_breached"] == 1
        assert result["tenders_expired"] == 1
        stored = db.get(CommercialContract, contract.id)
        expired = db.get(ContractTender, expiring_tender.id)
        db.refresh(issuer)
        assert stored is not None and stored.status == "breached"
        assert stored.breach_reason == "payment_default"
        assert expired is not None and expired.status == "expired"
        assert issuer.reputation_bps == (
            reputation_before - get_settings().contract_breach_reputation_penalty_bps
        )
        assert issuer.investigation_pressure_bps == (
            pressure_before + get_settings().contract_breach_investigation_penalty_bps
        )
        settlement = db.scalar(
            select(ContractSettlement).where(ContractSettlement.contract_id == contract.id)
        )
        assert settlement is not None
        assert settlement.status == "defaulted"
        assert settlement.transaction_id is None
        event_count = db.scalar(
            select(func.count())
            .select_from(RealtimeEvent)
            .where(RealtimeEvent.event_type == "contract.breached")
        )
        assert advance_contracts(db, get_settings(), at=at) == {
            "tenders_expired": 0,
            "periods_settled": 0,
            "contracts_breached": 0,
            "contracts_completed": 0,
        }
        assert (
            db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(RealtimeEvent.event_type == "contract.breached")
            )
            == event_count
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(
                    AuditLog.action == "contract.tender_expired",
                    AuditLog.target_id == expiring_tender.id,
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(
                    RealtimeEvent.event_type == "contract.tender_expired",
                    RealtimeEvent.payload_json["tender_id"].as_string() == expiring_tender.id,
                )
            )
            == 1
        )
