from __future__ import annotations

import hashlib
import unicodedata
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shadowgrid.config import Settings
from shadowgrid.domain import audit, get_idempotent, remember_idempotent
from shadowgrid.errors import DomainError
from shadowgrid.finance import (
    create_company_cash_account,
    transfer_profile_cash_to_account,
)
from shadowgrid.game_config import COMPANY_INDUSTRIES, COMPANY_INVESTMENTS
from shadowgrid.models import (
    Account,
    Company,
    CompanyInvestment,
    CompanyMetric,
    CompanyOwnership,
    District,
    PlayerProfile,
    uuid_str,
)


def normalize_company_name(name: str) -> tuple[str, str]:
    display_name = " ".join(unicodedata.normalize("NFKC", name).split())
    normalized_name = display_name.casefold()
    if not 2 <= len(display_name) <= 100:
        raise DomainError(
            422,
            "company.invalid_name",
            "Company name must contain between 2 and 100 characters",
            fields={"body.name": "Use between 2 and 100 characters"},
        )
    return display_name, normalized_name


def _financial_key(scope: str, profile_id: str, key: str) -> str:
    digest = hashlib.sha256(f"{scope}:{profile_id}:{key}".encode()).hexdigest()
    return f"{scope}:{digest}"


def snapshot_company(
    company: Company,
    *,
    reason: str,
    reference_id: str,
) -> CompanyMetric:
    return CompanyMetric(
        company_id=company.id,
        version=company.version,
        reason=reason,
        reference_id=reference_id,
        enterprise_value_cents=company.enterprise_value_cents,
        account_balance_cents=company.account.balance_cents,
        revenue_cents=company.revenue_cents,
        cost_cents=company.cost_cents,
        profit_cents=company.profit_cents,
        capacity=company.capacity,
        quality=company.quality,
        compliance_bps=company.compliance_bps,
        innovation_bps=company.innovation_bps,
    )


def company_configuration(settings: Settings) -> dict[str, Any]:
    return {
        "founding_cost_cents": settings.company_founding_cost_cents,
        "industries": COMPANY_INDUSTRIES,
        "investments": COMPANY_INVESTMENTS,
    }


def list_owned_companies(db: Session, profile: PlayerProfile) -> list[Company]:
    return list(
        db.scalars(
            select(Company)
            .join(CompanyOwnership, CompanyOwnership.company_id == Company.id)
            .where(
                Company.world_id == profile.world_id,
                CompanyOwnership.owner_profile_id == profile.id,
                CompanyOwnership.ownership_bps > 0,
            )
            .order_by(Company.created_at.desc())
        )
    )


def get_company(db: Session, profile: PlayerProfile, company_id: str) -> Company:
    company = db.scalar(
        select(Company).where(
            Company.id == company_id,
            Company.world_id == profile.world_id,
        )
    )
    if company is None:
        raise DomainError(404, "company.not_found", "Company not found")
    return company


def company_history(
    db: Session,
    company_id: str,
) -> tuple[list[CompanyMetric], list[CompanyInvestment], list[CompanyOwnership]]:
    metrics = list(
        db.scalars(
            select(CompanyMetric)
            .where(CompanyMetric.company_id == company_id)
            .order_by(CompanyMetric.version.desc())
        )
    )
    investments = list(
        db.scalars(
            select(CompanyInvestment)
            .where(CompanyInvestment.company_id == company_id)
            .order_by(CompanyInvestment.created_at.desc())
        )
    )
    ownership = list(
        db.scalars(
            select(CompanyOwnership)
            .where(CompanyOwnership.company_id == company_id)
            .order_by(CompanyOwnership.created_at)
        )
    )
    return metrics, investments, ownership


def create_company(
    db: Session,
    profile: PlayerProfile,
    *,
    name: str,
    industry: str,
    district_id: str,
    idempotency_key: str,
    settings: Settings,
    request_id: str,
) -> Company:
    locked_profile = db.scalar(
        select(PlayerProfile).where(PlayerProfile.id == profile.id).with_for_update()
    )
    if locked_profile is None:
        raise DomainError(409, "profile.missing", "Player profile does not exist")
    previous = get_idempotent(db, locked_profile.user_id, idempotency_key, "company.create")
    if previous is not None:
        existing = db.get(Company, previous.resource_id)
        if existing is not None:
            return existing

    industry_config = COMPANY_INDUSTRIES.get(industry)
    if industry_config is None:
        raise DomainError(422, "company.invalid_industry", "Unknown company industry")
    district = db.scalar(
        select(District).where(
            District.id == district_id,
            District.world_id == locked_profile.world_id,
            District.city_id == locked_profile.city_id,
        )
    )
    if district is None:
        raise DomainError(404, "district.not_found", "Starting district not found")
    display_name, normalized_name = normalize_company_name(name)
    duplicate = db.scalar(
        select(Company.id).where(
            Company.world_id == locked_profile.world_id,
            Company.normalized_name == normalized_name,
        )
    )
    if duplicate is not None:
        raise DomainError(409, "company.name_taken", "Company name is already in use")

    company_id = uuid_str()
    account = create_company_cash_account(db, locked_profile.world_id, company_id)
    company = Company(
        id=company_id,
        world_id=locked_profile.world_id,
        founder_profile_id=locked_profile.id,
        district_id=district.id,
        account_id=account.id,
        account=account,
        industry=industry,
        name=display_name,
        normalized_name=normalized_name,
        enterprise_value_cents=industry_config["enterprise_value_cents"],
        revenue_cents=industry_config["revenue_cents"],
        cost_cents=industry_config["cost_cents"],
        profit_cents=industry_config["revenue_cents"] - industry_config["cost_cents"],
        debt_cents=0,
        employees=industry_config["employees"],
        capacity=industry_config["capacity"],
        quality=industry_config["quality"],
        market_share_bps=industry_config["market_share_bps"],
        reputation_bps=industry_config["reputation_bps"],
        compliance_bps=industry_config["compliance_bps"],
        innovation_bps=industry_config["innovation_bps"],
        risk_bps=industry_config["risk_bps"],
        investigation_pressure_bps=0,
    )
    db.add(company)
    db.flush()
    transaction = transfer_profile_cash_to_account(
        db,
        locked_profile,
        account,
        amount_cents=settings.company_founding_cost_cents,
        transaction_type="company_founding",
        idempotency_key=_financial_key("company-founding", locked_profile.id, idempotency_key),
        reference_type="company",
        reference_id=company.id,
    )
    company.founding_transaction_id = transaction.id
    db.add(
        CompanyOwnership(
            company_id=company.id,
            owner_profile_id=locked_profile.id,
            ownership_bps=10_000,
        )
    )
    db.add(snapshot_company(company, reason="company_founding", reference_id=transaction.id))
    remember_idempotent(
        db,
        locked_profile.user_id,
        idempotency_key,
        "company.create",
        company.id,
        {"company_id": company.id},
    )
    audit(
        db,
        locked_profile.user_id,
        "company.create",
        "company",
        company.id,
        request_id,
        {"industry": industry, "founding_cost_cents": settings.company_founding_cost_cents},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "company.conflict", "Company creation conflicts with state") from exc
    db.refresh(company)
    return company


def invest_in_company(
    db: Session,
    profile: PlayerProfile,
    *,
    company_id: str,
    investment_type: str,
    idempotency_key: str,
    request_id: str,
) -> Company:
    locked_profile = db.scalar(
        select(PlayerProfile).where(PlayerProfile.id == profile.id).with_for_update()
    )
    if locked_profile is None:
        raise DomainError(409, "profile.missing", "Player profile does not exist")
    previous = get_idempotent(db, locked_profile.user_id, idempotency_key, "company.invest")
    if previous is not None:
        existing = db.get(Company, previous.resource_id)
        if existing is not None:
            return existing

    investment_config = COMPANY_INVESTMENTS.get(investment_type)
    if investment_config is None:
        raise DomainError(422, "company.invalid_investment", "Unknown investment type")
    company = db.scalar(
        select(Company)
        .where(Company.id == company_id, Company.world_id == locked_profile.world_id)
        .with_for_update()
    )
    if company is None:
        raise DomainError(404, "company.not_found", "Company not found")
    ownership = db.scalar(
        select(CompanyOwnership)
        .where(
            CompanyOwnership.company_id == company.id,
            CompanyOwnership.owner_profile_id == locked_profile.id,
            CompanyOwnership.ownership_bps > 0,
        )
        .with_for_update()
    )
    if ownership is None:
        raise DomainError(403, "company.not_owner", "Company ownership is required")
    account = db.scalar(select(Account).where(Account.id == company.account_id).with_for_update())
    if account is None:
        raise DomainError(409, "ledger.account_missing", "Company account does not exist")

    investment_id = uuid_str()
    transaction = transfer_profile_cash_to_account(
        db,
        locked_profile,
        account,
        amount_cents=investment_config["cost_cents"],
        transaction_type="company_investment",
        idempotency_key=_financial_key("company-investment", locked_profile.id, idempotency_key),
        reference_type="company",
        reference_id=company.id,
    )
    metric = investment_config["metric"]
    before = int(getattr(company, metric))
    after = min(10_000, before + investment_config["increase"])
    setattr(company, metric, after)
    company.version += 1
    investment = CompanyInvestment(
        id=investment_id,
        company_id=company.id,
        investor_profile_id=locked_profile.id,
        transaction_id=transaction.id,
        investment_type=investment_type,
        amount_cents=investment_config["cost_cents"],
        metric_before=before,
        metric_after=after,
        idempotency_key=idempotency_key,
    )
    db.add(investment)
    db.add(snapshot_company(company, reason="company_investment", reference_id=investment.id))
    remember_idempotent(
        db,
        locked_profile.user_id,
        idempotency_key,
        "company.invest",
        company.id,
        {"company_id": company.id, "investment_id": investment.id},
    )
    audit(
        db,
        locked_profile.user_id,
        "company.invest",
        "company",
        company.id,
        request_id,
        {
            "investment_type": investment_type,
            "amount_cents": investment_config["cost_cents"],
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "company.conflict", "Investment conflicts with state") from exc
    db.refresh(company)
    return company
