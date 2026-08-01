from __future__ import annotations

from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.finance import (
    ensure_system_account,
    post_balanced_transfer,
    transaction_balance_cents,
)
from shadowgrid.loans import advance_loans
from shadowgrid.models import (
    AuditLog,
    Company,
    CompanyLoan,
    District,
    LedgerTransaction,
    LoanApplication,
    LoanPayment,
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
) -> dict[str, str]:
    email = f"loan-{suffix}@example.com"
    with SessionLocal() as db:
        world = db.scalar(select(World))
        district = db.scalar(select(District))
        assert world is not None and district is not None
        db.add(
            User(
                email=email,
                password_hash=hash_password(PASSWORD),
                display_name=f"Loan {suffix}",
                email_verified=True,
            )
        )
        db.commit()
        world_id = world.id
        district_id = district.id
    headers = _login(client, email)
    joined = client.post(
        f"/api/v1/worlds/{world_id}/join",
        headers={**headers, "Idempotency-Key": f"loan-join-{suffix}"},
        json={
            "codename": f"Loan {suffix}",
            "archetype": "business_consortium",
            "home_district_id": district_id,
        },
    )
    assert joined.status_code == 200, joined.text
    return headers


def _create_company(
    client: TestClient,
    headers: dict[str, str],
    *,
    suffix: str,
) -> str:
    district = client.get("/api/v1/districts", headers=headers).json()[0]
    response = client.post(
        "/api/v1/companies",
        headers={**headers, "Idempotency-Key": f"loan-company-{suffix}"},
        json={
            "name": f"Loan {suffix} GmbH",
            "industry": "technology",
            "district_id": district["id"],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _apply(
    client: TestClient,
    headers: dict[str, str],
    company_id: str,
    *,
    key: str,
    principal_cents: int = 600_000,
    term_periods: int = 3,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/loans/applications",
        headers={**headers, "Idempotency-Key": key},
        json={
            "company_id": company_id,
            "requested_principal_cents": principal_cents,
            "term_periods": term_periods,
            "collateral_score_bps": 5_000,
            "purpose": "Fictional working capital expansion",
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _accept(
    client: TestClient,
    headers: dict[str, str],
    application_id: str,
    *,
    key: str,
) -> dict[str, object]:
    response = client.post(
        f"/api/v1/loans/applications/{application_id}/accept",
        headers={**headers, "Idempotency-Key": key},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_loan_application_underwriting_rbac_acceptance_and_idempotency(
    client: TestClient,
) -> None:
    owner_headers = _join_player(client, suffix="owner")
    outsider_headers = _join_player(client, suffix="outsider")
    company_id = _create_company(client, owner_headers, suffix="Owner")

    forbidden = client.post(
        "/api/v1/loans/applications",
        headers={**outsider_headers, "Idempotency-Key": "loan-forbidden"},
        json={
            "company_id": company_id,
            "requested_principal_cents": 600_000,
            "term_periods": 3,
            "collateral_score_bps": 5_000,
            "purpose": "Unauthorized application",
        },
    )
    assert forbidden.status_code == 403

    application = _apply(
        client,
        owner_headers,
        company_id,
        key="loan-application-001",
    )
    duplicate_application = _apply(
        client,
        owner_headers,
        company_id,
        key="loan-application-001",
    )
    assert application["id"] == duplicate_application["id"]
    assert application["status"] == "offered"
    assert int(application["offered_interest_rate_bps"]) > 0
    assert int(application["offered_total_repayment_cents"]) > 600_000

    rejected = _apply(
        client,
        owner_headers,
        company_id,
        key="loan-application-rejected",
        principal_cents=100_000_000,
    )
    assert rejected["status"] == "rejected"
    assert rejected["rejection_reason"] == "lending_limit_exceeded"

    with SessionLocal() as db:
        company = db.get(Company, company_id)
        assert company is not None
        balance_before = company.account.balance_cents
        debt_before = company.debt_cents

    loan = _accept(
        client,
        owner_headers,
        str(application["id"]),
        key="loan-accept-001",
    )
    repeated = _accept(
        client,
        owner_headers,
        str(application["id"]),
        key="loan-accept-001",
    )
    assert loan["id"] == repeated["id"]
    assert loan["status"] == "active"

    with SessionLocal() as db:
        company = db.get(Company, company_id)
        stored = db.get(CompanyLoan, loan["id"])
        application_row = db.get(LoanApplication, application["id"])
        assert company is not None and stored is not None and application_row is not None
        assert company.account.balance_cents == balance_before + 600_000
        assert company.debt_cents == debt_before + 600_000
        assert transaction_balance_cents(db, stored.disbursement_transaction_id) == 0
        assert application_row.status == "accepted"
        application_row.requested_principal_cents += 1
        with pytest.raises(ValueError, match="immutable"):
            db.flush()


def test_due_installments_sum_exactly_use_balanced_ledger_and_repay_once(
    client: TestClient,
) -> None:
    headers = _join_player(client, suffix="repayer")
    company_id = _create_company(client, headers, suffix="Repayer")
    application = _apply(
        client,
        headers,
        company_id,
        key="loan-repay-application",
        principal_cents=600_001,
        term_periods=3,
    )
    loan_payload = _accept(
        client,
        headers,
        str(application["id"]),
        key="loan-repay-accept",
    )
    loan_id = str(loan_payload["id"])

    with SessionLocal() as db:
        loan = db.get(CompanyLoan, loan_id)
        company = db.get(Company, company_id)
        assert loan is not None and company is not None
        at = loan.next_payment_at + timedelta(
            minutes=get_settings().loan_payment_interval_minutes * 2,
            seconds=1,
        )
        result = advance_loans(db, get_settings(), at=at)
        assert result == {
            "offers_expired": 0,
            "payments_paid": 3,
            "loans_defaulted": 0,
            "loans_repaid": 1,
        }
        stored = db.get(CompanyLoan, loan_id)
        db.refresh(company)
        assert stored is not None and stored.status == "repaid"
        assert stored.outstanding_principal_cents == 0
        assert stored.outstanding_interest_cents == 0
        assert company.debt_cents == 0
        payments = list(
            db.scalars(
                select(LoanPayment)
                .where(LoanPayment.loan_id == loan_id)
                .order_by(LoanPayment.period_number)
            )
        )
        assert len(payments) == 3
        assert sum(item.principal_cents for item in payments) == stored.principal_cents
        assert sum(item.interest_cents for item in payments) == stored.total_interest_cents
        assert sum(item.amount_cents for item in payments) == stored.total_repayment_cents
        assert all(
            item.transaction_id is not None
            and transaction_balance_cents(db, item.transaction_id) == 0
            for item in payments
        )
        transaction_count = db.scalar(
            select(func.count())
            .select_from(LedgerTransaction)
            .where(LedgerTransaction.transaction_type == "loan_installment")
        )
        assert advance_loans(db, get_settings(), at=at) == {
            "offers_expired": 0,
            "payments_paid": 0,
            "loans_defaulted": 0,
            "loans_repaid": 0,
        }
        assert (
            db.scalar(
                select(func.count())
                .select_from(LedgerTransaction)
                .where(LedgerTransaction.transaction_type == "loan_installment")
            )
            == transaction_count
        )


def test_default_and_offer_expiry_are_abstract_audited_and_retry_safe(
    client: TestClient,
) -> None:
    headers = _join_player(client, suffix="default")
    company_id = _create_company(client, headers, suffix="Default")
    application = _apply(
        client,
        headers,
        company_id,
        key="loan-default-application",
        principal_cents=600_000,
        term_periods=3,
    )
    expiring = _apply(
        client,
        headers,
        company_id,
        key="loan-expiring-application",
        principal_cents=100_000,
        term_periods=2,
    )
    loan_payload = _accept(
        client,
        headers,
        str(application["id"]),
        key="loan-default-accept",
    )

    with SessionLocal() as db:
        loan = db.get(CompanyLoan, loan_payload["id"])
        company = db.get(Company, company_id)
        expiring_application = db.get(LoanApplication, expiring["id"])
        assert loan is not None and company is not None
        assert expiring_application is not None
        assert expiring_application.offer_expires_at is not None
        reputation_before = company.reputation_bps
        pressure_before = company.investigation_pressure_bps
        available = company.account.balance_cents - company.account.reserved_cents
        post_balanced_transfer(
            db,
            world_id=company.world_id,
            source_account=company.account,
            target_account=ensure_system_account(db, company.world_id),
            amount_cents=available,
            transaction_type="loan_test_cash_drain",
            idempotency_key=f"loan-test-drain:{loan.id}",
            reference_type="company_loan",
            reference_id=loan.id,
            actor_profile_id=None,
        )
        db.commit()
        at = max(loan.next_payment_at, expiring_application.offer_expires_at) + timedelta(seconds=1)
        result = advance_loans(db, get_settings(), at=at)
        assert result == {
            "offers_expired": 1,
            "payments_paid": 0,
            "loans_defaulted": 1,
            "loans_repaid": 0,
        }
        stored = db.get(CompanyLoan, loan.id)
        expired = db.get(LoanApplication, expiring_application.id)
        db.refresh(company)
        assert stored is not None and stored.status == "defaulted"
        assert stored.default_reason == "installment_default"
        assert expired is not None and expired.status == "cancelled"
        assert company.reputation_bps == (
            reputation_before - get_settings().loan_default_reputation_penalty_bps
        )
        assert company.investigation_pressure_bps == (
            pressure_before + get_settings().loan_default_investigation_penalty_bps
        )
        payment = db.scalar(select(LoanPayment).where(LoanPayment.loan_id == loan.id))
        assert payment is not None and payment.status == "defaulted"
        assert payment.transaction_id is None
        counts = {
            "events": db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(RealtimeEvent.event_type == "loan.defaulted")
            ),
            "audits": db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action.in_(("loan.payment.defaulted", "loan.offer_expired")))
            ),
        }
        assert advance_loans(db, get_settings(), at=at) == {
            "offers_expired": 0,
            "payments_paid": 0,
            "loans_defaulted": 0,
            "loans_repaid": 0,
        }
        assert {
            "events": db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(RealtimeEvent.event_type == "loan.defaulted")
            ),
            "audits": db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action.in_(("loan.payment.defaulted", "loan.offer_expired")))
            ),
        } == counts
