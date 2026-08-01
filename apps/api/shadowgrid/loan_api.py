from __future__ import annotations

from fastapi import APIRouter, Request, status

from shadowgrid.config import get_settings
from shadowgrid.dependencies import CurrentProfile, Db, IdempotencyKey
from shadowgrid.loan_schemas import (
    CompanyLoanView,
    CreateLoanApplicationRequest,
    LoanApplicationView,
    LoanConfigView,
    LoanPaymentView,
)
from shadowgrid.loans import (
    accept_loan_offer,
    create_loan_application,
    list_company_loans,
    list_loan_applications,
    list_loan_payments,
)
from shadowgrid.models import Company, CompanyLoan, LoanApplication

router = APIRouter()


def _application_view(db: Db, application: LoanApplication) -> LoanApplicationView:
    company = db.get(Company, application.company_id)
    return LoanApplicationView.model_validate(
        {
            **{
                field: getattr(application, field)
                for field in LoanApplicationView.model_fields
                if field != "company_name"
            },
            "company_name": company.name if company else "Archived company",
        }
    )


def _loan_view(db: Db, loan: CompanyLoan) -> CompanyLoanView:
    company = db.get(Company, loan.company_id)
    return CompanyLoanView.model_validate(
        {
            **{
                field: getattr(loan, field)
                for field in CompanyLoanView.model_fields
                if field != "company_name"
            },
            "company_name": company.name if company else "Archived company",
        }
    )


@router.get("/loans/config", response_model=LoanConfigView, tags=["loans"])
def loan_config(_: CurrentProfile) -> LoanConfigView:
    settings = get_settings()
    return LoanConfigView(
        payment_interval_minutes=settings.loan_payment_interval_minutes,
        offer_valid_minutes=settings.loan_offer_valid_minutes,
        max_principal_cents=settings.loan_max_principal_cents,
        max_term_periods=settings.loan_max_term_periods,
        min_interest_rate_bps=settings.loan_min_interest_rate_bps,
        max_interest_rate_bps=settings.loan_max_interest_rate_bps,
        default_reputation_penalty_bps=(settings.loan_default_reputation_penalty_bps),
        default_investigation_penalty_bps=(settings.loan_default_investigation_penalty_bps),
    )


@router.post(
    "/loans/applications",
    response_model=LoanApplicationView,
    status_code=status.HTTP_201_CREATED,
    tags=["loans"],
)
def post_loan_application(
    payload: CreateLoanApplicationRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> LoanApplicationView:
    application = create_loan_application(
        db,
        profile,
        **payload.model_dump(),
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
        settings=get_settings(),
    )
    return _application_view(db, application)


@router.get(
    "/loans/applications/me",
    response_model=list[LoanApplicationView],
    tags=["loans"],
)
def my_loan_applications(
    db: Db,
    profile: CurrentProfile,
) -> list[LoanApplicationView]:
    return [
        _application_view(db, application) for application in list_loan_applications(db, profile)
    ]


@router.post(
    "/loans/applications/{application_id}/accept",
    response_model=CompanyLoanView,
    status_code=status.HTTP_201_CREATED,
    tags=["loans"],
)
def post_accept_loan_offer(
    application_id: str,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> CompanyLoanView:
    loan = accept_loan_offer(
        db,
        profile,
        application_id=application_id,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
        settings=get_settings(),
    )
    return _loan_view(db, loan)


@router.get("/loans/me", response_model=list[CompanyLoanView], tags=["loans"])
def my_loans(db: Db, profile: CurrentProfile) -> list[CompanyLoanView]:
    return [_loan_view(db, loan) for loan in list_company_loans(db, profile)]


@router.get(
    "/loans/{loan_id}/payments",
    response_model=list[LoanPaymentView],
    tags=["loans"],
)
def loan_payments(
    loan_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[LoanPaymentView]:
    return [
        LoanPaymentView.model_validate(payment)
        for payment in list_loan_payments(db, profile, loan_id)
    ]
