from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from shadowgrid.companies import snapshot_company
from shadowgrid.config import Settings
from shadowgrid.domain import (
    audit,
    create_company_warning,
    get_idempotent,
    remember_idempotent,
)
from shadowgrid.errors import DomainError
from shadowgrid.finance import ensure_system_account, post_balanced_transfer
from shadowgrid.models import (
    Account,
    Company,
    CompanyLoan,
    CompanyOwnership,
    LoanApplication,
    LoanPayment,
    PlayerProfile,
    RealtimeEvent,
    World,
    as_utc,
)

_LOCK = threading.RLock()


def _error(status: int, code: str, message: str) -> DomainError:
    return DomainError(status, code, message)


def _ceil_div(numerator: int, denominator: int) -> int:
    return (numerator + denominator - 1) // denominator


def _owned_company(
    db: Session,
    profile: PlayerProfile,
    company_id: str,
    *,
    lock: bool = False,
) -> Company:
    statement = (
        select(Company)
        .join(CompanyOwnership, CompanyOwnership.company_id == Company.id)
        .where(
            Company.id == company_id,
            Company.world_id == profile.world_id,
            Company.status != "archived",
            CompanyOwnership.owner_profile_id == profile.id,
            CompanyOwnership.ownership_bps > 0,
        )
    )
    if lock:
        statement = statement.with_for_update()
    company = db.scalar(statement)
    if company is None:
        raise _error(403, "loan.company_not_owned", "Active company ownership is required")
    return company


def _lock_world(db: Session, world_id: str) -> None:
    if db.scalar(select(World).where(World.id == world_id).with_for_update()) is None:
        raise _error(404, "world.not_found", "World not found")


def _active_outstanding_principal(db: Session, company_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(CompanyLoan.outstanding_principal_cents), 0)).where(
                CompanyLoan.company_id == company_id,
                CompanyLoan.status == "active",
            )
        )
        or 0
    )


def _underwrite(
    db: Session,
    company: Company,
    *,
    requested_principal_cents: int,
    collateral_score_bps: int,
    settings: Settings,
) -> tuple[str, int | None, str | None, dict[str, int]]:
    active_outstanding = _active_outstanding_principal(db, company.id)
    lending_limit = min(
        settings.loan_max_principal_cents,
        max(100_000, company.enterprise_value_cents // 2),
    )
    available_limit = max(0, lending_limit - active_outstanding)
    risk_points = (
        company.risk_bps
        + company.investigation_pressure_bps
        + max(0, 5_000 - company.compliance_bps) // 2
    )
    raw_rate = (
        settings.loan_base_interest_rate_bps
        + risk_points // 4
        + max(0, 10_000 - company.reputation_bps) // 5
        + company.investigation_pressure_bps // 2
        - collateral_score_bps // 10
    )
    interest_rate_bps = max(
        settings.loan_min_interest_rate_bps,
        min(settings.loan_max_interest_rate_bps, raw_rate),
    )
    snapshot = {
        "enterprise_value_cents": company.enterprise_value_cents,
        "active_outstanding_principal_cents": active_outstanding,
        "lending_limit_cents": lending_limit,
        "available_limit_cents": available_limit,
        "reputation_bps": company.reputation_bps,
        "compliance_bps": company.compliance_bps,
        "risk_bps": company.risk_bps,
        "investigation_pressure_bps": company.investigation_pressure_bps,
        "collateral_score_bps": collateral_score_bps,
        "calculated_interest_rate_bps": interest_rate_bps,
    }
    if requested_principal_cents > available_limit:
        return "rejected", None, "lending_limit_exceeded", snapshot
    if company.compliance_bps < 1_000:
        return "rejected", None, "compliance_below_minimum", snapshot
    return "offered", interest_rate_bps, None, snapshot


def create_loan_application(
    db: Session,
    profile: PlayerProfile,
    *,
    company_id: str,
    requested_principal_cents: int,
    term_periods: int,
    collateral_score_bps: int,
    purpose: str,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> LoanApplication:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "loan.application.create",
        )
        if previous is not None:
            existing = db.get(LoanApplication, previous.resource_id)
            if existing is not None:
                return existing
        if term_periods > settings.loan_max_term_periods:
            raise _error(422, "loan.term_too_long", "Loan term exceeds the configured limit")
        company = _owned_company(db, profile, company_id, lock=True)
        _lock_world(db, profile.world_id)
        now = as_utc(at or datetime.now(UTC))
        status, rate, rejection_reason, risk_snapshot = _underwrite(
            db,
            company,
            requested_principal_cents=requested_principal_cents,
            collateral_score_bps=collateral_score_bps,
            settings=settings,
        )
        interest_cents = (
            _ceil_div(requested_principal_cents * rate, 10_000) if rate is not None else None
        )
        total_repayment_cents = (
            requested_principal_cents + interest_cents if interest_cents is not None else None
        )
        installment_cents = (
            _ceil_div(total_repayment_cents, term_periods)
            if total_repayment_cents is not None
            else None
        )
        application = LoanApplication(
            world_id=profile.world_id,
            company_id=company.id,
            applicant_profile_id=profile.id,
            requested_principal_cents=requested_principal_cents,
            term_periods=term_periods,
            collateral_score_bps=collateral_score_bps,
            purpose=purpose.strip(),
            offered_interest_rate_bps=rate,
            offered_installment_cents=installment_cents,
            offered_total_repayment_cents=total_repayment_cents,
            status=status,
            rejection_reason=rejection_reason,
            risk_snapshot_json=risk_snapshot,
            idempotency_key=idempotency_key,
            offer_expires_at=(
                now + timedelta(minutes=settings.loan_offer_valid_minutes)
                if status == "offered"
                else None
            ),
            created_at=now,
        )
        db.add(application)
        db.flush()
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "loan.application.create",
            application.id,
            {"application_id": application.id},
        )
        audit(
            db,
            profile.user_id,
            f"loan.application.{status}",
            "loan_application",
            application.id,
            request_id,
            risk_snapshot,
        )
        db.commit()
        db.refresh(application)
        return application


def accept_loan_offer(
    db: Session,
    profile: PlayerProfile,
    *,
    application_id: str,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> CompanyLoan:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "loan.offer.accept",
        )
        if previous is not None:
            existing = db.get(CompanyLoan, previous.resource_id)
            if existing is not None:
                return existing
        application = db.scalar(
            select(LoanApplication).where(LoanApplication.id == application_id).with_for_update()
        )
        if application is None or application.world_id != profile.world_id:
            raise _error(404, "loan.application_not_found", "Loan application not found")
        existing_loan = db.scalar(
            select(CompanyLoan).where(CompanyLoan.application_id == application.id)
        )
        if existing_loan is not None:
            return existing_loan
        company = _owned_company(db, profile, application.company_id, lock=True)
        now = as_utc(at or datetime.now(UTC))
        if application.status != "offered":
            raise _error(409, "loan.offer_unavailable", "Loan offer is not available")
        if application.offer_expires_at is None or as_utc(application.offer_expires_at) <= now:
            application.status = "cancelled"
            application.cancelled_at = now
            db.commit()
            raise _error(409, "loan.offer_expired", "Loan offer has expired")
        _lock_world(db, profile.world_id)
        status, current_rate, rejection_reason, current_risk = _underwrite(
            db,
            company,
            requested_principal_cents=application.requested_principal_cents,
            collateral_score_bps=application.collateral_score_bps,
            settings=settings,
        )
        if status != "offered" or current_rate is None:
            raise _error(
                409,
                "loan.eligibility_changed",
                rejection_reason or "Loan eligibility changed",
            )
        if application.offered_interest_rate_bps is None:
            raise RuntimeError("loan offer is missing an interest rate")
        total_interest = _ceil_div(
            application.requested_principal_cents * application.offered_interest_rate_bps,
            10_000,
        )
        total_repayment = application.requested_principal_cents + total_interest
        installment = _ceil_div(total_repayment, application.term_periods)
        system_account = ensure_system_account(db, profile.world_id)
        transaction = post_balanced_transfer(
            db,
            world_id=profile.world_id,
            source_account=system_account,
            target_account=company.account,
            amount_cents=application.requested_principal_cents,
            transaction_type="loan_disbursement",
            idempotency_key=f"loan-disbursement:{application.id}",
            reference_type="loan_application",
            reference_id=application.id,
            actor_profile_id=profile.id,
            metadata={
                "interest_rate_bps": application.offered_interest_rate_bps,
                "term_periods": application.term_periods,
            },
        )
        first_payment_at = now + timedelta(minutes=settings.loan_payment_interval_minutes)
        loan = CompanyLoan(
            world_id=profile.world_id,
            application_id=application.id,
            company_id=company.id,
            borrower_profile_id=profile.id,
            principal_cents=application.requested_principal_cents,
            interest_rate_bps=application.offered_interest_rate_bps,
            total_interest_cents=total_interest,
            total_repayment_cents=total_repayment,
            scheduled_installment_cents=installment,
            term_periods=application.term_periods,
            outstanding_principal_cents=application.requested_principal_cents,
            outstanding_interest_cents=total_interest,
            collateral_score_bps=application.collateral_score_bps,
            idempotency_key=idempotency_key,
            disbursement_transaction_id=transaction.id,
            starts_at=now,
            ends_at=now
            + timedelta(minutes=settings.loan_payment_interval_minutes * application.term_periods),
            next_payment_at=first_payment_at,
            created_at=now,
        )
        db.add(loan)
        db.flush()
        application.status = "accepted"
        application.accepted_at = now
        company.debt_cents += application.requested_principal_cents
        company.version += 1
        db.add(snapshot_company(company, reason="loan_disbursed", reference_id=loan.id))
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "loan.offer.accept",
            loan.id,
            {"loan_id": loan.id},
        )
        audit(
            db,
            profile.user_id,
            "loan.disbursed",
            "company_loan",
            loan.id,
            request_id,
            {
                "application_id": application.id,
                "principal_cents": loan.principal_cents,
                "interest_rate_bps": loan.interest_rate_bps,
                "current_underwriting_rate_bps": current_rate,
                "current_available_limit_cents": current_risk["available_limit_cents"],
                "transaction_id": transaction.id,
            },
        )
        db.add(
            RealtimeEvent(
                world_id=loan.world_id,
                event_type="loan.disbursed",
                payload_json={"loan_id": loan.id, "company_id": company.id},
                created_at=now,
                expires_at=now + timedelta(days=7),
            )
        )
        db.commit()
        db.refresh(loan)
        return loan


def _component_for_period(total: int, periods: int, period_number: int) -> int:
    base, remainder = divmod(total, periods)
    return base + int(period_number <= remainder)


def _settle_payment(
    db: Session,
    loan: CompanyLoan,
    *,
    at: datetime,
    settings: Settings,
) -> LoanPayment:
    period_number = loan.payments_made + 1
    existing = db.scalar(
        select(LoanPayment).where(
            LoanPayment.loan_id == loan.id,
            LoanPayment.period_number == period_number,
        )
    )
    if existing is not None:
        return existing
    company = db.scalar(select(Company).where(Company.id == loan.company_id).with_for_update())
    if company is None:
        raise RuntimeError("loan company is missing")
    company_account = db.scalar(
        select(Account)
        .where(
            Account.owner_type == "company",
            Account.owner_id == company.id,
        )
        .with_for_update()
    )
    if company_account is None:
        raise RuntimeError("loan company account is missing")
    principal = _component_for_period(
        loan.principal_cents,
        loan.term_periods,
        period_number,
    )
    interest = _component_for_period(
        loan.total_interest_cents,
        loan.term_periods,
        period_number,
    )
    amount = principal + interest
    input_snapshot = {
        "company_balance_cents": company_account.balance_cents,
        "company_reserved_cents": company_account.reserved_cents,
        "outstanding_principal_cents": loan.outstanding_principal_cents,
        "outstanding_interest_cents": loan.outstanding_interest_cents,
        "collateral_score_bps": loan.collateral_score_bps,
        "period_number": period_number,
    }
    available_cents = company_account.balance_cents - company_account.reserved_cents
    if available_cents < amount:
        payment = LoanPayment(
            loan_id=loan.id,
            period_number=period_number,
            amount_cents=amount,
            principal_cents=principal,
            interest_cents=interest,
            status="defaulted",
            input_snapshot_json=input_snapshot,
            paid_at=at,
        )
        loan.status = "defaulted"
        loan.default_reason = "installment_default"
        loan.defaulted_at = at
        company.reputation_bps = max(
            0,
            company.reputation_bps - settings.loan_default_reputation_penalty_bps,
        )
        company.investigation_pressure_bps = min(
            10_000,
            company.investigation_pressure_bps + settings.loan_default_investigation_penalty_bps,
        )
    else:
        transaction = post_balanced_transfer(
            db,
            world_id=loan.world_id,
            source_account=company_account,
            target_account=ensure_system_account(db, loan.world_id),
            amount_cents=amount,
            transaction_type="loan_installment",
            idempotency_key=f"loan:{loan.id}:period:{period_number}",
            reference_type="company_loan",
            reference_id=loan.id,
            actor_profile_id=None,
            metadata={
                "period_number": period_number,
                "principal_cents": principal,
                "interest_cents": interest,
            },
        )
        payment = LoanPayment(
            loan_id=loan.id,
            period_number=period_number,
            amount_cents=amount,
            principal_cents=principal,
            interest_cents=interest,
            status="paid",
            transaction_id=transaction.id,
            input_snapshot_json=input_snapshot,
            paid_at=at,
        )
        loan.payments_made = period_number
        loan.outstanding_principal_cents -= principal
        loan.outstanding_interest_cents -= interest
        company.debt_cents = max(0, company.debt_cents - principal)
        if period_number >= loan.term_periods:
            loan.status = "repaid"
            loan.repaid_at = at
        else:
            loan.next_payment_at = loan.next_payment_at + timedelta(
                minutes=settings.loan_payment_interval_minutes
            )
    company.version += 1
    db.add(snapshot_company(company, reason=f"loan_payment_{payment.status}", reference_id=loan.id))
    db.add(payment)
    db.flush()
    audit(
        db,
        None,
        f"loan.payment.{payment.status}",
        "loan_payment",
        payment.id,
        f"loan-scheduler:{loan.id}:{period_number}",
        input_snapshot,
    )
    event_type = (
        "loan.repaid"
        if loan.status == "repaid"
        else ("loan.defaulted" if loan.status == "defaulted" else "loan.payment_paid")
    )
    if loan.status == "defaulted":
        create_company_warning(
            db,
            company=company,
            warning_type="loan_default",
            title=f"Loan payment warning for {company.name}",
            body="A scheduled company installment entered abstract default.",
            dedupe_key=f"company-warning:loan:{loan.id}:{period_number}",
            metadata={"loan_id": loan.id, "period_number": period_number},
        )
    db.add(
        RealtimeEvent(
            world_id=loan.world_id,
            event_type=event_type,
            payload_json={
                "loan_id": loan.id,
                "company_id": loan.company_id,
                "period_number": period_number,
                "payment_status": payment.status,
            },
            created_at=at,
            expires_at=at + timedelta(days=7),
        )
    )
    return payment


def advance_loans(
    db: Session,
    settings: Settings,
    *,
    at: datetime | None = None,
) -> dict[str, int]:
    now = as_utc(at or datetime.now(UTC))
    with _LOCK:
        expired_offers = 0
        for application in db.scalars(
            select(LoanApplication)
            .where(
                LoanApplication.status == "offered",
                LoanApplication.offer_expires_at <= now,
            )
            .order_by(LoanApplication.offer_expires_at, LoanApplication.id)
            .with_for_update()
        ):
            application.status = "cancelled"
            application.cancelled_at = now
            audit(
                db,
                None,
                "loan.offer_expired",
                "loan_application",
                application.id,
                f"loan-offer-expiry:{application.id}",
            )
            expired_offers += 1
        paid = 0
        defaulted = 0
        repaid = 0
        loans = list(
            db.scalars(
                select(CompanyLoan)
                .where(
                    CompanyLoan.status == "active",
                    CompanyLoan.next_payment_at <= now,
                )
                .order_by(CompanyLoan.next_payment_at, CompanyLoan.id)
                .with_for_update()
            )
        )
        for loan in loans:
            while loan.status == "active" and as_utc(loan.next_payment_at) <= now:
                payment = _settle_payment(
                    db,
                    loan,
                    at=as_utc(loan.next_payment_at),
                    settings=settings,
                )
                paid += int(payment.status == "paid")
                defaulted += int(payment.status == "defaulted")
                repaid += int(loan.status == "repaid")
        db.commit()
        return {
            "offers_expired": expired_offers,
            "payments_paid": paid,
            "loans_defaulted": defaulted,
            "loans_repaid": repaid,
        }


def list_loan_applications(
    db: Session,
    profile: PlayerProfile,
) -> list[LoanApplication]:
    owned_ids = select(CompanyOwnership.company_id).where(
        CompanyOwnership.owner_profile_id == profile.id,
        CompanyOwnership.ownership_bps > 0,
    )
    return list(
        db.scalars(
            select(LoanApplication)
            .where(
                LoanApplication.world_id == profile.world_id,
                LoanApplication.company_id.in_(owned_ids),
            )
            .order_by(LoanApplication.created_at.desc())
        )
    )


def list_company_loans(db: Session, profile: PlayerProfile) -> list[CompanyLoan]:
    owned_ids = select(CompanyOwnership.company_id).where(
        CompanyOwnership.owner_profile_id == profile.id,
        CompanyOwnership.ownership_bps > 0,
    )
    return list(
        db.scalars(
            select(CompanyLoan)
            .where(
                CompanyLoan.world_id == profile.world_id,
                or_(
                    CompanyLoan.company_id.in_(owned_ids),
                    CompanyLoan.borrower_profile_id == profile.id,
                ),
            )
            .order_by(CompanyLoan.created_at.desc())
        )
    )


def list_loan_payments(
    db: Session,
    profile: PlayerProfile,
    loan_id: str,
) -> list[LoanPayment]:
    loan = db.get(CompanyLoan, loan_id)
    if loan is None or loan.world_id != profile.world_id:
        raise _error(404, "loan.not_found", "Loan not found")
    _owned_company(db, profile, loan.company_id)
    return list(
        db.scalars(
            select(LoanPayment)
            .where(LoanPayment.loan_id == loan.id)
            .order_by(LoanPayment.period_number)
        )
    )
