from __future__ import annotations

import re
import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
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
from shadowgrid.finance import (
    transfer_account_to_profile_cash,
    transfer_profile_cash_to_account,
)
from shadowgrid.models import (
    Account,
    BondHolding,
    BondIssue,
    BondLedgerEntry,
    BondSettlement,
    BondSubscription,
    Company,
    CompanyOwnership,
    PlayerProfile,
    RealtimeEvent,
    World,
    as_utc,
)

_LOCK = threading.RLock()
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,12}$")


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
        raise _error(403, "bond.company_not_owned", "Active company ownership is required")
    return company


def _lock_world(db: Session, world_id: str) -> None:
    if db.scalar(select(World).where(World.id == world_id).with_for_update()) is None:
        raise _error(404, "world.not_found", "World not found")


def create_bond_issue(
    db: Session,
    profile: PlayerProfile,
    *,
    issuer_company_id: str,
    symbol: str,
    title: str,
    face_value_cents: int,
    total_units: int,
    coupon_rate_bps: int,
    term_periods: int,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> BondIssue:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "bond.issue.create",
        )
        if previous is not None:
            existing = db.get(BondIssue, previous.resource_id)
            if existing is not None:
                return existing
        company = _owned_company(db, profile, issuer_company_id, lock=True)
        _lock_world(db, profile.world_id)
        normalized_symbol = symbol.strip().upper()
        if not _SYMBOL_PATTERN.fullmatch(normalized_symbol):
            raise _error(
                422,
                "bond.invalid_symbol",
                "Bond symbol must contain 2 to 12 uppercase letters or digits",
            )
        if term_periods > settings.bond_max_term_periods:
            raise _error(422, "bond.term_too_long", "Bond term exceeds configured limit")
        principal_cents = face_value_cents * total_units
        issue_limit = min(
            settings.bond_max_principal_cents,
            max(100_000, company.enterprise_value_cents),
        )
        if principal_cents > issue_limit:
            raise _error(
                422,
                "bond.issue_limit_exceeded",
                "Bond principal exceeds the company issuance limit",
            )
        now = as_utc(at or datetime.now(UTC))
        issue = BondIssue(
            world_id=profile.world_id,
            issuer_company_id=company.id,
            created_by_profile_id=profile.id,
            symbol=normalized_symbol,
            title=title.strip(),
            face_value_cents=face_value_cents,
            total_units=total_units,
            coupon_rate_bps=coupon_rate_bps,
            term_periods=term_periods,
            idempotency_key=idempotency_key,
            offering_ends_at=now + timedelta(minutes=settings.bond_offering_minutes),
            created_at=now,
        )
        db.add(issue)
        db.flush()
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "bond.issue.create",
            issue.id,
            {"issue_id": issue.id},
        )
        audit(
            db,
            profile.user_id,
            "bond.issue.created",
            "bond_issue",
            issue.id,
            request_id,
            {
                "principal_cents": principal_cents,
                "coupon_rate_bps": coupon_rate_bps,
                "term_periods": term_periods,
            },
        )
        db.commit()
        db.refresh(issue)
        return issue


def subscribe_bond(
    db: Session,
    profile: PlayerProfile,
    *,
    issue_id: str,
    quantity: int,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> BondSubscription:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "bond.subscription.create",
        )
        if previous is not None:
            existing = db.get(BondSubscription, previous.resource_id)
            if existing is not None:
                return existing
        issue = db.scalar(select(BondIssue).where(BondIssue.id == issue_id).with_for_update())
        if issue is None or issue.world_id != profile.world_id:
            raise _error(404, "bond.issue_not_found", "Bond issue not found")
        now = as_utc(at or datetime.now(UTC))
        if issue.status != "offering" or as_utc(issue.offering_ends_at) <= now:
            raise _error(409, "bond.offering_closed", "Bond offering is closed")
        remaining_units = issue.total_units - issue.sold_units
        if quantity > remaining_units:
            raise _error(409, "bond.quantity_unavailable", "Requested bond units unavailable")
        company = db.scalar(
            select(Company)
            .where(
                Company.id == issue.issuer_company_id,
                Company.status != "archived",
            )
            .with_for_update()
        )
        if company is None:
            raise _error(409, "bond.issuer_inactive", "Bond issuer is inactive")
        amount_cents = issue.face_value_cents * quantity
        transaction = transfer_profile_cash_to_account(
            db,
            profile,
            company.account,
            amount_cents=amount_cents,
            transaction_type="bond_subscription",
            idempotency_key=f"bond-subscription:{profile.id}:{idempotency_key}",
            reference_type="bond_issue",
            reference_id=issue.id,
        )
        company.account.reserved_cents += amount_cents
        company.account.version += 1
        holding = db.scalar(
            select(BondHolding)
            .where(
                BondHolding.issue_id == issue.id,
                BondHolding.profile_id == profile.id,
            )
            .with_for_update()
        )
        if holding is None:
            holding = BondHolding(
                issue_id=issue.id,
                profile_id=profile.id,
                quantity=0,
                acquired_at=now,
                updated_at=now,
            )
            db.add(holding)
            db.flush()
        holding.quantity += quantity
        holding.updated_at = now
        issue.sold_units += quantity
        subscription = BondSubscription(
            issue_id=issue.id,
            subscriber_profile_id=profile.id,
            quantity=quantity,
            amount_cents=amount_cents,
            transaction_id=transaction.id,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        db.add(subscription)
        db.add(
            BondLedgerEntry(
                issue_id=issue.id,
                profile_id=profile.id,
                quantity_delta=quantity,
                balance_after=holding.quantity,
                entry_type="subscription",
                transaction_id=transaction.id,
                created_at=now,
            )
        )
        db.flush()
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "bond.subscription.create",
            subscription.id,
            {"subscription_id": subscription.id},
        )
        audit(
            db,
            profile.user_id,
            "bond.subscribed",
            "bond_subscription",
            subscription.id,
            request_id,
            {
                "issue_id": issue.id,
                "quantity": quantity,
                "amount_cents": amount_cents,
                "transaction_id": transaction.id,
            },
        )
        if issue.sold_units == issue.total_units:
            _activate_locked(
                db,
                issue,
                company,
                at=now,
                settings=settings,
                actor_user_id=profile.user_id,
                request_id=f"{request_id}:auto-activate",
            )
        db.commit()
        db.refresh(subscription)
        return subscription


def _activate_locked(
    db: Session,
    issue: BondIssue,
    company: Company,
    *,
    at: datetime,
    settings: Settings,
    actor_user_id: str | None,
    request_id: str,
) -> BondIssue:
    if issue.status == "active":
        return issue
    if issue.status != "offering":
        raise _error(409, "bond.activation_unavailable", "Bond issue cannot be activated")
    if issue.sold_units <= 0:
        raise _error(409, "bond.no_subscriptions", "At least one subscription is required")
    principal_cents = issue.face_value_cents * issue.sold_units
    if company.account.reserved_cents < principal_cents:
        raise RuntimeError("bond subscription reservation is inconsistent")
    company.account.reserved_cents -= principal_cents
    company.account.version += 1
    company.debt_cents += principal_cents
    company.version += 1
    issue.status = "active"
    issue.starts_at = at
    issue.activated_at = at
    issue.next_coupon_at = at + timedelta(minutes=settings.bond_coupon_interval_minutes)
    issue.ends_at = at + timedelta(
        minutes=settings.bond_coupon_interval_minutes * issue.term_periods
    )
    db.add(snapshot_company(company, reason="bond_activated", reference_id=issue.id))
    audit(
        db,
        actor_user_id,
        "bond.issue.activated",
        "bond_issue",
        issue.id,
        request_id,
        {
            "sold_units": issue.sold_units,
            "principal_cents": principal_cents,
        },
    )
    db.add(
        RealtimeEvent(
            world_id=issue.world_id,
            event_type="bond.issue_activated",
            payload_json={"issue_id": issue.id, "company_id": company.id},
            created_at=at,
            expires_at=at + timedelta(days=7),
        )
    )
    return issue


def activate_bond_issue(
    db: Session,
    profile: PlayerProfile,
    *,
    issue_id: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> BondIssue:
    with _LOCK:
        issue = db.scalar(select(BondIssue).where(BondIssue.id == issue_id).with_for_update())
        if issue is None or issue.world_id != profile.world_id:
            raise _error(404, "bond.issue_not_found", "Bond issue not found")
        company = _owned_company(db, profile, issue.issuer_company_id, lock=True)
        _lock_world(db, issue.world_id)
        _activate_locked(
            db,
            issue,
            company,
            at=as_utc(at or datetime.now(UTC)),
            settings=settings,
            actor_user_id=profile.user_id,
            request_id=request_id,
        )
        db.commit()
        db.refresh(issue)
        return issue


def _coupon_per_unit(issue: BondIssue) -> int:
    return _ceil_div(issue.face_value_cents * issue.coupon_rate_bps, 10_000)


def _settle_issue_period(
    db: Session,
    issue: BondIssue,
    *,
    at: datetime,
    settings: Settings,
) -> list[BondSettlement]:
    period_number = issue.coupons_paid + 1
    existing = list(
        db.scalars(
            select(BondSettlement).where(
                BondSettlement.issue_id == issue.id,
                BondSettlement.period_number == period_number,
            )
        )
    )
    if existing:
        return existing
    company = db.scalar(
        select(Company).where(Company.id == issue.issuer_company_id).with_for_update()
    )
    if company is None:
        raise RuntimeError("bond issuer company is missing")
    account = db.scalar(
        select(Account)
        .where(
            Account.owner_type == "company",
            Account.owner_id == company.id,
        )
        .with_for_update()
    )
    if account is None:
        raise RuntimeError("bond issuer account is missing")
    holdings = list(
        db.scalars(
            select(BondHolding)
            .where(BondHolding.issue_id == issue.id, BondHolding.quantity > 0)
            .order_by(BondHolding.profile_id)
            .with_for_update()
        )
    )
    if not holdings:
        raise RuntimeError("active bond issue has no holdings")
    coupon_per_unit = _coupon_per_unit(issue)
    maturity = period_number >= issue.term_periods
    total_due = sum(
        holding.quantity * (coupon_per_unit + (issue.face_value_cents if maturity else 0))
        for holding in holdings
    )
    input_snapshot = {
        "company_balance_cents": account.balance_cents,
        "company_reserved_cents": account.reserved_cents,
        "coupon_per_unit_cents": coupon_per_unit,
        "sold_units": issue.sold_units,
        "period_number": period_number,
        "maturity": int(maturity),
        "total_due_cents": total_due,
    }
    settlements: list[BondSettlement] = []
    available_cents = account.balance_cents - account.reserved_cents
    if available_cents < total_due:
        for holding in holdings:
            payments = [("coupon", coupon_per_unit * holding.quantity)]
            if maturity:
                payments.append(("redemption", issue.face_value_cents * holding.quantity))
            for payment_type, amount in payments:
                settlements.append(
                    BondSettlement(
                        issue_id=issue.id,
                        period_number=period_number,
                        profile_id=holding.profile_id,
                        payment_type=payment_type,
                        quantity=holding.quantity,
                        amount_cents=amount,
                        status="defaulted",
                        input_snapshot_json=input_snapshot,
                        settled_at=at,
                    )
                )
        issue.status = "defaulted"
        issue.default_reason = "maturity_default" if maturity else "coupon_default"
        issue.defaulted_at = at
        company.reputation_bps = max(
            0,
            company.reputation_bps - settings.bond_default_reputation_penalty_bps,
        )
        company.investigation_pressure_bps = min(
            10_000,
            company.investigation_pressure_bps + settings.bond_default_investigation_penalty_bps,
        )
    else:
        for holding in holdings:
            profile = db.get(PlayerProfile, holding.profile_id)
            if profile is None:
                raise RuntimeError("bond holder profile is missing")
            coupon_amount = coupon_per_unit * holding.quantity
            coupon_transaction = transfer_account_to_profile_cash(
                db,
                account,
                profile,
                amount_cents=coupon_amount,
                transaction_type="bond_coupon",
                idempotency_key=(f"bond:{issue.id}:period:{period_number}:coupon:{profile.id}"),
                reference_type="bond_issue",
                reference_id=issue.id,
            )
            settlements.append(
                BondSettlement(
                    issue_id=issue.id,
                    period_number=period_number,
                    profile_id=profile.id,
                    payment_type="coupon",
                    quantity=holding.quantity,
                    amount_cents=coupon_amount,
                    status="paid",
                    transaction_id=coupon_transaction.id,
                    input_snapshot_json=input_snapshot,
                    settled_at=at,
                )
            )
            if maturity:
                redemption_amount = issue.face_value_cents * holding.quantity
                redemption_transaction = transfer_account_to_profile_cash(
                    db,
                    account,
                    profile,
                    amount_cents=redemption_amount,
                    transaction_type="bond_redemption",
                    idempotency_key=(f"bond:{issue.id}:redemption:{profile.id}"),
                    reference_type="bond_issue",
                    reference_id=issue.id,
                )
                db.add(
                    BondLedgerEntry(
                        issue_id=issue.id,
                        profile_id=profile.id,
                        quantity_delta=-holding.quantity,
                        balance_after=0,
                        entry_type="redemption",
                        transaction_id=redemption_transaction.id,
                        created_at=at,
                    )
                )
                settlements.append(
                    BondSettlement(
                        issue_id=issue.id,
                        period_number=period_number,
                        profile_id=profile.id,
                        payment_type="redemption",
                        quantity=holding.quantity,
                        amount_cents=redemption_amount,
                        status="paid",
                        transaction_id=redemption_transaction.id,
                        input_snapshot_json=input_snapshot,
                        settled_at=at,
                    )
                )
                holding.quantity = 0
                holding.updated_at = at
        issue.coupons_paid = period_number
        if maturity:
            issue.status = "repaid"
            issue.repaid_at = at
            company.debt_cents = max(
                0,
                company.debt_cents - issue.face_value_cents * issue.sold_units,
            )
        else:
            if issue.next_coupon_at is None:
                raise RuntimeError("active bond issue has no next coupon")
            issue.next_coupon_at = issue.next_coupon_at + timedelta(
                minutes=settings.bond_coupon_interval_minutes
            )
    company.version += 1
    db.add(
        snapshot_company(
            company,
            reason=("bond_defaulted" if issue.status == "defaulted" else "bond_settled"),
            reference_id=issue.id,
        )
    )
    db.add_all(settlements)
    db.flush()
    audit(
        db,
        None,
        (
            "bond.issue.defaulted"
            if issue.status == "defaulted"
            else ("bond.issue.repaid" if issue.status == "repaid" else "bond.coupon.paid")
        ),
        "bond_issue",
        issue.id,
        f"bond-scheduler:{issue.id}:{period_number}",
        input_snapshot,
    )
    if issue.status == "defaulted":
        create_company_warning(
            db,
            company=company,
            warning_type="bond_default",
            title=f"Bond payment warning for {company.name}",
            body="A scheduled bond obligation entered abstract default.",
            dedupe_key=f"company-warning:bond:{issue.id}:{period_number}",
            metadata={"issue_id": issue.id, "period_number": period_number},
        )
    db.add(
        RealtimeEvent(
            world_id=issue.world_id,
            event_type=(
                "bond.defaulted"
                if issue.status == "defaulted"
                else ("bond.repaid" if issue.status == "repaid" else "bond.coupon_paid")
            ),
            payload_json={
                "issue_id": issue.id,
                "period_number": period_number,
                "status": issue.status,
            },
            created_at=at,
            expires_at=at + timedelta(days=7),
        )
    )
    return settlements


def advance_bonds(
    db: Session,
    settings: Settings,
    *,
    at: datetime | None = None,
) -> dict[str, int]:
    now = as_utc(at or datetime.now(UTC))
    with _LOCK:
        activated = 0
        cancelled = 0
        offerings = list(
            db.scalars(
                select(BondIssue)
                .where(
                    BondIssue.status == "offering",
                    BondIssue.offering_ends_at <= now,
                )
                .order_by(BondIssue.offering_ends_at, BondIssue.id)
                .with_for_update()
            )
        )
        for issue in offerings:
            company = db.scalar(
                select(Company).where(Company.id == issue.issuer_company_id).with_for_update()
            )
            if company is None:
                raise RuntimeError("bond issuer company is missing")
            if issue.sold_units > 0:
                _activate_locked(
                    db,
                    issue,
                    company,
                    at=now,
                    settings=settings,
                    actor_user_id=None,
                    request_id=f"bond-offering-expiry:{issue.id}",
                )
                activated += 1
            else:
                issue.status = "cancelled"
                issue.cancelled_at = now
                audit(
                    db,
                    None,
                    "bond.issue.cancelled",
                    "bond_issue",
                    issue.id,
                    f"bond-offering-expiry:{issue.id}",
                )
                cancelled += 1
        coupons = 0
        defaulted = 0
        repaid = 0
        issues = list(
            db.scalars(
                select(BondIssue)
                .where(
                    BondIssue.status == "active",
                    BondIssue.next_coupon_at <= now,
                )
                .order_by(BondIssue.next_coupon_at, BondIssue.id)
                .with_for_update()
            )
        )
        for issue in issues:
            while (
                issue.status == "active"
                and issue.next_coupon_at is not None
                and as_utc(issue.next_coupon_at) <= now
            ):
                settlements = _settle_issue_period(
                    db,
                    issue,
                    at=as_utc(issue.next_coupon_at),
                    settings=settings,
                )
                coupons += int(
                    any(
                        item.payment_type == "coupon" and item.status == "paid"
                        for item in settlements
                    )
                )
                defaulted += int(issue.status == "defaulted")
                repaid += int(issue.status == "repaid")
        db.commit()
        return {
            "issues_activated": activated,
            "issues_cancelled": cancelled,
            "coupon_periods_paid": coupons,
            "issues_defaulted": defaulted,
            "issues_repaid": repaid,
        }


def archive_world_bonds(
    db: Session,
    world_id: str,
    *,
    at: datetime,
) -> list[tuple[BondIssue, dict[str, int | str]]]:
    archived_at = as_utc(at)
    archived: list[tuple[BondIssue, dict[str, int | str]]] = []
    issues = list(
        db.scalars(
            select(BondIssue)
            .where(
                BondIssue.world_id == world_id,
                BondIssue.status.in_(("offering", "active")),
            )
            .order_by(BondIssue.id)
            .with_for_update()
        )
    )
    for issue in issues:
        archived.append(
            (
                issue,
                {
                    "issuer_company_id": issue.issuer_company_id,
                    "symbol": issue.symbol,
                    "face_value_cents": issue.face_value_cents,
                    "sold_units": issue.sold_units,
                    "coupon_rate_bps": issue.coupon_rate_bps,
                    "term_periods": issue.term_periods,
                    "coupons_paid": issue.coupons_paid,
                    "status": issue.status,
                },
            )
        )
        company = db.scalar(
            select(Company).where(Company.id == issue.issuer_company_id).with_for_update()
        )
        if company is None:
            raise RuntimeError("bond issuer company is missing")
        account = db.scalar(
            select(Account)
            .where(
                Account.owner_type == "company",
                Account.owner_id == company.id,
            )
            .with_for_update()
        )
        if account is None:
            raise RuntimeError("bond issuer account is missing")
        holdings = list(
            db.scalars(
                select(BondHolding)
                .where(BondHolding.issue_id == issue.id, BondHolding.quantity > 0)
                .order_by(BondHolding.profile_id)
                .with_for_update()
            )
        )
        principal_cents = issue.face_value_cents * issue.sold_units
        if issue.status == "offering":
            if account.reserved_cents < principal_cents:
                raise RuntimeError("bond offering reservation is inconsistent")
            account.reserved_cents -= principal_cents
            account.version += 1
        available_cents = account.balance_cents - account.reserved_cents
        can_redeem = available_cents >= principal_cents
        period_number = issue.term_periods + 1
        for holding in holdings:
            quantity = holding.quantity
            amount_cents = issue.face_value_cents * quantity
            input_snapshot = {
                "season_close": 1,
                "company_balance_cents": account.balance_cents,
                "company_reserved_cents": account.reserved_cents,
                "principal_due_cents": principal_cents,
            }
            transaction_id: str | None = None
            status = "defaulted"
            if can_redeem:
                profile = db.get(PlayerProfile, holding.profile_id)
                if profile is None:
                    raise RuntimeError("bond holder profile is missing")
                transaction = transfer_account_to_profile_cash(
                    db,
                    account,
                    profile,
                    amount_cents=amount_cents,
                    transaction_type="bond_season_redemption",
                    idempotency_key=f"bond:{issue.id}:season-redemption:{profile.id}",
                    reference_type="bond_issue",
                    reference_id=issue.id,
                )
                transaction_id = transaction.id
                status = "paid"
                db.add(
                    BondLedgerEntry(
                        issue_id=issue.id,
                        profile_id=profile.id,
                        quantity_delta=-quantity,
                        balance_after=0,
                        entry_type="redemption",
                        transaction_id=transaction.id,
                        created_at=archived_at,
                    )
                )
                holding.quantity = 0
                holding.updated_at = archived_at
            db.add(
                BondSettlement(
                    issue_id=issue.id,
                    period_number=period_number,
                    profile_id=holding.profile_id,
                    payment_type="redemption",
                    quantity=quantity,
                    amount_cents=amount_cents,
                    status=status,
                    transaction_id=transaction_id,
                    input_snapshot_json=input_snapshot,
                    settled_at=archived_at,
                )
            )
        if can_redeem:
            if issue.status == "active":
                company.debt_cents = max(0, company.debt_cents - principal_cents)
            issue.status = "cancelled"
            issue.cancelled_at = archived_at
        else:
            issue.status = "defaulted"
            issue.default_reason = "season_close_default"
            issue.defaulted_at = archived_at
        company.version += 1
        db.add(
            snapshot_company(
                company,
                reason="bond_season_close",
                reference_id=issue.id,
            )
        )
        audit(
            db,
            None,
            ("bond.issue.season_redeemed" if can_redeem else "bond.issue.season_defaulted"),
            "bond_issue",
            issue.id,
            f"bond-season-close:{issue.id}",
            {"principal_cents": principal_cents},
        )
    return archived


def list_bond_issues(db: Session, profile: PlayerProfile) -> list[BondIssue]:
    return list(
        db.scalars(
            select(BondIssue)
            .where(BondIssue.world_id == profile.world_id)
            .order_by(BondIssue.created_at.desc())
            .limit(200)
        )
    )


def list_profile_bond_holdings(
    db: Session,
    profile: PlayerProfile,
) -> list[BondHolding]:
    return list(
        db.scalars(
            select(BondHolding)
            .join(BondIssue, BondIssue.id == BondHolding.issue_id)
            .where(
                BondIssue.world_id == profile.world_id,
                BondHolding.profile_id == profile.id,
                BondHolding.quantity > 0,
            )
            .order_by(BondHolding.updated_at.desc())
        )
    )


def list_bond_settlements(
    db: Session,
    profile: PlayerProfile,
    issue_id: str,
) -> list[BondSettlement]:
    issue = db.get(BondIssue, issue_id)
    if issue is None or issue.world_id != profile.world_id:
        raise _error(404, "bond.issue_not_found", "Bond issue not found")
    owns_issuer = db.scalar(
        select(func.count())
        .select_from(CompanyOwnership)
        .where(
            CompanyOwnership.company_id == issue.issuer_company_id,
            CompanyOwnership.owner_profile_id == profile.id,
            CompanyOwnership.ownership_bps > 0,
        )
    )
    if not owns_issuer:
        holding = db.scalar(
            select(BondHolding).where(
                BondHolding.issue_id == issue.id,
                BondHolding.profile_id == profile.id,
            )
        )
        if holding is None:
            raise _error(403, "bond.not_party", "Bond issuer or holding is required")
    statement = select(BondSettlement).where(BondSettlement.issue_id == issue.id)
    if not owns_issuer:
        statement = statement.where(BondSettlement.profile_id == profile.id)
    return list(
        db.scalars(
            statement.order_by(
                BondSettlement.period_number,
                BondSettlement.payment_type,
                BondSettlement.profile_id,
            )
        )
    )
