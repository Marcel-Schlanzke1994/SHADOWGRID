from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shadowgrid.companies import snapshot_company
from shadowgrid.config import Settings
from shadowgrid.domain import audit, create_notification, get_idempotent, remember_idempotent
from shadowgrid.errors import DomainError
from shadowgrid.finance import (
    ensure_profile_cash_account,
    ensure_system_account,
    money_to_cents,
    post_balanced_transfer,
    transfer_account_to_profile_cash,
    transfer_profile_cash_between_profiles,
    transfer_profile_cash_to_account,
)
from shadowgrid.models import (
    Account,
    Company,
    CompanyEconomyReport,
    CompanyOwnership,
    DividendDeclaration,
    DividendEntitlement,
    ExchangeListing,
    ExchangeOrder,
    ExchangeTrade,
    PlayerProfile,
    PriceSnapshot,
    ResourceBalance,
    ShareClass,
    ShareHolding,
    ShareLedgerEntry,
    World,
    uuid_str,
)
from shadowgrid.realtime import emit_realtime_event

_local_exchange_lock = Lock()
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{2,8}$")
_OPEN_ORDER_STATUSES = ("open", "partially_filled")


@dataclass(frozen=True)
class IpoEligibility:
    eligible: bool
    reasons: tuple[str, ...]
    metrics: dict[str, int]


@dataclass(frozen=True)
class PortfolioPosition:
    holding_id: str
    listing_id: str
    company_id: str
    company_name: str
    symbol: str
    share_class: str
    quantity: int
    reserved_quantity: int
    available_quantity: int
    average_cost_cents: int
    last_price_cents: int
    market_value_cents: int
    voting_rights: int


@dataclass(frozen=True)
class ShareholderPosition:
    holding_id: str
    profile_id: str
    codename: str
    quantity: int
    ownership_bps: int
    voting_rights: int


def exchange_configuration(settings: Settings) -> dict[str, int]:
    return {
        "min_enterprise_value_cents": settings.ipo_min_enterprise_value_cents,
        "profitable_periods": settings.ipo_profitable_periods,
        "min_compliance_bps": settings.ipo_min_compliance_bps,
        "min_employees": settings.ipo_min_employees,
        "max_investigation_pressure_bps": settings.ipo_max_investigation_pressure_bps,
        "ipo_fee_cents": settings.ipo_fee_cents,
        "order_rate_limit_per_minute": settings.exchange_order_rate_limit_per_minute,
        "max_price_deviation_bps": settings.exchange_max_price_deviation_bps,
    }


def _lock_exchange_world(db: Session, world_id: str) -> None:
    world = db.scalar(select(World).where(World.id == world_id).with_for_update())
    if world is None:
        raise DomainError(404, "world.not_found", "World not found")


def _controlled_company(
    db: Session,
    profile: PlayerProfile,
    company_id: str,
    *,
    lock: bool,
) -> Company:
    statement = select(Company).where(
        Company.id == company_id,
        Company.world_id == profile.world_id,
        Company.founder_profile_id == profile.id,
    )
    if lock:
        statement = statement.with_for_update()
    company = db.scalar(statement)
    if company is None:
        raise DomainError(
            403,
            "company.control_required",
            "Founder control is required for this company action",
        )
    return company


def ipo_eligibility(
    db: Session,
    profile: PlayerProfile,
    company_id: str,
    settings: Settings,
    *,
    lock: bool = False,
) -> IpoEligibility:
    company = _controlled_company(db, profile, company_id, lock=lock)
    reports = list(
        db.scalars(
            select(CompanyEconomyReport)
            .where(CompanyEconomyReport.company_id == company.id)
            .order_by(CompanyEconomyReport.created_at.desc())
            .limit(settings.ipo_profitable_periods)
        )
    )
    profitable_periods = sum(1 for report in reports if report.profit_cents > 0)
    account = db.scalar(
        select(Account).where(Account.id == company.account_id).with_for_update()
        if lock
        else select(Account).where(Account.id == company.account_id)
    )
    if account is None:
        raise DomainError(409, "ledger.account_missing", "Company account does not exist")
    already_listed = db.scalar(
        select(ExchangeListing.id).where(ExchangeListing.company_id == company.id)
    )
    reasons: list[str] = []
    if already_listed is not None or company.status != "private":
        reasons.append("already_listed")
    if company.enterprise_value_cents < settings.ipo_min_enterprise_value_cents:
        reasons.append("enterprise_value")
    if len(reports) < settings.ipo_profitable_periods:
        reasons.append("audited_reports")
    if profitable_periods < settings.ipo_profitable_periods:
        reasons.append("profitable_periods")
    if company.compliance_bps < settings.ipo_min_compliance_bps:
        reasons.append("compliance")
    if company.employees < settings.ipo_min_employees:
        reasons.append("employees")
    if company.investigation_pressure_bps > settings.ipo_max_investigation_pressure_bps:
        reasons.append("investigation_pressure")
    if account.balance_cents - account.reserved_cents < settings.ipo_fee_cents:
        reasons.append("ipo_fee")
    return IpoEligibility(
        eligible=not reasons,
        reasons=tuple(reasons),
        metrics={
            "enterprise_value_cents": company.enterprise_value_cents,
            "profitable_periods": profitable_periods,
            "audited_reports": len(reports),
            "compliance_bps": company.compliance_bps,
            "employees": company.employees,
            "investigation_pressure_bps": company.investigation_pressure_bps,
            "available_company_cash_cents": account.balance_cents - account.reserved_cents,
        },
    )


def _share_supply(db: Session, share_class_id: str) -> int:
    return int(
        db.scalar(
            select(func.coalesce(func.sum(ShareHolding.quantity), 0)).where(
                ShareHolding.share_class_id == share_class_id
            )
        )
        or 0
    )


def _assert_share_supply(db: Session, share_class: ShareClass) -> None:
    db.flush()
    if _share_supply(db, share_class.id) != share_class.total_shares:
        raise RuntimeError("share supply invariant violated")


def _rebuild_ownership(
    db: Session,
    company_id: str,
    share_class: ShareClass,
) -> None:
    holdings = list(
        db.scalars(
            select(ShareHolding)
            .where(
                ShareHolding.share_class_id == share_class.id,
                ShareHolding.owner_type == "profile",
                ShareHolding.profile_id.is_not(None),
                ShareHolding.quantity > 0,
            )
            .order_by(ShareHolding.profile_id)
        )
    )
    profile_total = sum(holding.quantity for holding in holdings)
    target_bps = profile_total * 10_000 // share_class.total_shares
    allocations: dict[str, int] = {}
    remainders: list[tuple[int, str]] = []
    for holding in holdings:
        if holding.profile_id is None:
            continue
        numerator = holding.quantity * 10_000
        allocations[holding.profile_id] = numerator // share_class.total_shares
        remainders.append((numerator % share_class.total_shares, holding.profile_id))
    remaining = target_bps - sum(allocations.values())
    for _, profile_id in sorted(remainders, key=lambda item: (-item[0], item[1]))[:remaining]:
        allocations[profile_id] += 1

    existing = {
        ownership.owner_profile_id: ownership
        for ownership in db.scalars(
            select(CompanyOwnership)
            .where(CompanyOwnership.company_id == company_id)
            .with_for_update()
        )
    }
    for profile_id, ownership in existing.items():
        bps = allocations.get(profile_id, 0)
        if bps <= 0:
            db.delete(ownership)
        else:
            ownership.ownership_bps = bps
    for profile_id, bps in allocations.items():
        if bps > 0 and profile_id not in existing:
            db.add(
                CompanyOwnership(
                    company_id=company_id,
                    owner_profile_id=profile_id,
                    ownership_bps=bps,
                )
            )


def create_ipo(
    db: Session,
    profile: PlayerProfile,
    *,
    company_id: str,
    symbol: str,
    total_shares: int,
    offered_shares: int,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
) -> ExchangeListing:
    previous = get_idempotent(db, profile.user_id, idempotency_key, "exchange.ipo")
    if previous is not None:
        existing = db.get(ExchangeListing, previous.resource_id)
        if existing is not None:
            return existing
    normalized_symbol = symbol.strip().upper()
    if not _SYMBOL_PATTERN.fullmatch(normalized_symbol):
        raise DomainError(
            422,
            "exchange.invalid_symbol",
            "Exchange symbol must contain 2 to 8 uppercase letters or digits",
        )
    if total_shares <= 1 or offered_shares <= 0 or offered_shares >= total_shares:
        raise DomainError(
            422,
            "exchange.invalid_share_allocation",
            "IPO shares must be positive and leave retained founder shares",
        )
    _lock_exchange_world(db, profile.world_id)
    eligibility = ipo_eligibility(
        db,
        profile,
        company_id,
        settings,
        lock=True,
    )
    if not eligibility.eligible:
        raise DomainError(
            409,
            "exchange.ipo_ineligible",
            "Company does not satisfy IPO requirements",
            fields={"requirements": ",".join(eligibility.reasons)},
        )
    company = _controlled_company(db, profile, company_id, lock=True)
    initial_price_cents = company.enterprise_value_cents // total_shares
    if initial_price_cents <= 0:
        raise DomainError(
            422,
            "exchange.share_price_too_small",
            "Total shares exceed the cent-denominated enterprise value",
        )
    retained_shares = total_shares - offered_shares
    if retained_shares * 10_000 // total_shares <= 0:
        raise DomainError(
            422,
            "exchange.founder_stake_too_small",
            "Retained founder stake must represent at least one ownership basis point",
        )
    listing_id = uuid_str()
    fee_transaction = post_balanced_transfer(
        db,
        world_id=company.world_id,
        source_account=company.account,
        target_account=ensure_system_account(db, company.world_id),
        amount_cents=settings.ipo_fee_cents,
        transaction_type="exchange_ipo_fee",
        idempotency_key=f"ipo-fee:{listing_id}",
        reference_type="exchange_listing",
        reference_id=listing_id,
        actor_profile_id=profile.id,
        metadata={"company_id": company.id},
    )
    listing = ExchangeListing(
        id=listing_id,
        world_id=company.world_id,
        company_id=company.id,
        symbol=normalized_symbol,
        total_shares=total_shares,
        offered_shares=offered_shares,
        initial_price_cents=initial_price_cents,
        last_price_cents=initial_price_cents,
        ipo_fee_cents=settings.ipo_fee_cents,
        fee_transaction_id=fee_transaction.id,
        idempotency_key=idempotency_key,
    )
    db.add(listing)
    db.flush()
    share_class = ShareClass(
        listing_id=listing.id,
        class_code="common",
        name="Common shares",
        total_shares=total_shares,
        voting_rights_per_share=1,
        dividend_priority=0,
        tradable=True,
    )
    db.add(share_class)
    db.flush()
    founder_holding = ShareHolding(
        share_class_id=share_class.id,
        owner_type="profile",
        profile_id=profile.id,
        quantity=retained_shares,
        reserved_quantity=0,
        average_cost_cents=initial_price_cents,
    )
    issuer_holding = ShareHolding(
        share_class_id=share_class.id,
        owner_type="company",
        company_id=company.id,
        quantity=offered_shares,
        reserved_quantity=offered_shares,
        average_cost_cents=initial_price_cents,
    )
    db.add_all((founder_holding, issuer_holding))
    db.flush()
    issuance_key = f"ipo-issuance:{listing.id}"
    db.add_all(
        (
            ShareLedgerEntry(
                share_class_id=share_class.id,
                holding_id=founder_holding.id,
                quantity_delta=retained_shares,
                balance_after=retained_shares,
                reason="ipo_issuance",
                reference_type="exchange_listing",
                reference_id=listing.id,
                event_key=issuance_key,
            ),
            ShareLedgerEntry(
                share_class_id=share_class.id,
                holding_id=issuer_holding.id,
                quantity_delta=offered_shares,
                balance_after=offered_shares,
                reason="ipo_issuance",
                reference_type="exchange_listing",
                reference_id=listing.id,
                event_key=issuance_key,
            ),
        )
    )
    db.add(
        ExchangeOrder(
            listing_id=listing.id,
            share_class_id=share_class.id,
            issuer_company_id=company.id,
            owner_key=company.id,
            side="sell",
            order_type="ipo",
            limit_price_cents=initial_price_cents,
            original_quantity=offered_shares,
            remaining_quantity=offered_shares,
            reserved_cash_cents=0,
            reserved_shares=offered_shares,
            status="open",
            idempotency_key=f"ipo-offering:{listing.id}",
        )
    )
    company.status = "public"
    company.version += 1
    db.add(snapshot_company(company, reason="exchange_ipo", reference_id=listing.id))
    _assert_share_supply(db, share_class)
    _rebuild_ownership(db, company.id, share_class)
    remember_idempotent(
        db,
        profile.user_id,
        idempotency_key,
        "exchange.ipo",
        listing.id,
        {"listing_id": listing.id},
    )
    audit(
        db,
        profile.user_id,
        "exchange.ipo",
        "exchange_listing",
        listing.id,
        request_id,
        {
            "company_id": company.id,
            "total_shares": total_shares,
            "offered_shares": offered_shares,
            "initial_price_cents": initial_price_cents,
            "ipo_fee_cents": settings.ipo_fee_cents,
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "exchange.ipo_conflict", "IPO conflicts with current state") from exc
    db.refresh(listing)
    return listing


def list_exchange_listings(
    db: Session,
    profile: PlayerProfile,
) -> list[ExchangeListing]:
    return list(
        db.scalars(
            select(ExchangeListing)
            .where(
                ExchangeListing.world_id == profile.world_id,
                ExchangeListing.status.in_(("active", "suspended")),
            )
            .order_by(ExchangeListing.symbol)
        )
    )


def get_exchange_listing(
    db: Session,
    profile: PlayerProfile,
    listing_id: str,
    *,
    lock: bool = False,
) -> ExchangeListing:
    statement = select(ExchangeListing).where(
        ExchangeListing.id == listing_id,
        ExchangeListing.world_id == profile.world_id,
    )
    if lock:
        statement = statement.with_for_update()
    listing = db.scalar(statement)
    if listing is None:
        raise DomainError(404, "exchange.listing_not_found", "Exchange listing not found")
    return listing


def get_company_exchange_listing(
    db: Session,
    profile: PlayerProfile,
    company_id: str,
) -> ExchangeListing:
    listing = db.scalar(
        select(ExchangeListing).where(
            ExchangeListing.company_id == company_id,
            ExchangeListing.world_id == profile.world_id,
        )
    )
    if listing is None:
        raise DomainError(404, "exchange.listing_not_found", "Exchange listing not found")
    return listing


def _share_class_for_listing(
    db: Session,
    listing_id: str,
    *,
    lock: bool,
) -> ShareClass:
    statement = select(ShareClass).where(
        ShareClass.listing_id == listing_id,
        ShareClass.class_code == "common",
    )
    if lock:
        statement = statement.with_for_update()
    share_class = db.scalar(statement)
    if share_class is None:
        raise DomainError(409, "exchange.share_class_missing", "Share class is missing")
    return share_class


def _profile_cash_state(
    db: Session,
    profile: PlayerProfile,
) -> tuple[ResourceBalance, Account]:
    balance = db.scalar(
        select(ResourceBalance).where(ResourceBalance.profile_id == profile.id).with_for_update()
    )
    if balance is None:
        raise DomainError(409, "resource.missing", "Player cash balance does not exist")
    account = ensure_profile_cash_account(db, profile, money_to_cents(balance.cash))
    return balance, account


def _profile_holding(
    db: Session,
    share_class_id: str,
    profile_id: str,
    *,
    create: bool,
) -> ShareHolding | None:
    holding = db.scalar(
        select(ShareHolding)
        .where(
            ShareHolding.share_class_id == share_class_id,
            ShareHolding.profile_id == profile_id,
        )
        .with_for_update()
    )
    if holding is None and create:
        holding = ShareHolding(
            share_class_id=share_class_id,
            owner_type="profile",
            profile_id=profile_id,
            quantity=0,
            reserved_quantity=0,
            average_cost_cents=0,
        )
        db.add(holding)
        db.flush()
    return holding


def _issuer_holding(
    db: Session,
    share_class_id: str,
    company_id: str,
) -> ShareHolding:
    holding = db.scalar(
        select(ShareHolding)
        .where(
            ShareHolding.share_class_id == share_class_id,
            ShareHolding.company_id == company_id,
        )
        .with_for_update()
    )
    if holding is None:
        raise DomainError(409, "exchange.issuer_holding_missing", "Issuer holding is missing")
    return holding


def _market_buy_reservation(
    db: Session,
    listing_id: str,
    profile_id: str,
    quantity: int,
) -> int:
    asks = list(
        db.scalars(
            select(ExchangeOrder)
            .where(
                ExchangeOrder.listing_id == listing_id,
                ExchangeOrder.side == "sell",
                ExchangeOrder.status.in_(_OPEN_ORDER_STATUSES),
                ExchangeOrder.remaining_quantity > 0,
                or_(
                    ExchangeOrder.profile_id.is_(None),
                    ExchangeOrder.profile_id != profile_id,
                ),
                or_(
                    ExchangeOrder.expires_at.is_(None),
                    ExchangeOrder.expires_at > datetime.now(UTC),
                ),
            )
            .order_by(
                ExchangeOrder.limit_price_cents.asc(),
                ExchangeOrder.created_at.asc(),
                ExchangeOrder.id.asc(),
            )
            .with_for_update()
        )
    )
    remaining = quantity
    required_cents = 0
    for ask in asks:
        if ask.limit_price_cents is None:
            continue
        fill = min(remaining, ask.remaining_quantity)
        required_cents += fill * ask.limit_price_cents
        remaining -= fill
        if remaining == 0:
            break
    if required_cents <= 0:
        raise DomainError(409, "exchange.no_liquidity", "No executable sell order is available")
    return required_cents


def _release_order_reservation(db: Session, order: ExchangeOrder) -> None:
    if order.reserved_cash_cents > 0:
        if order.profile_id is None:
            raise RuntimeError("buy reservation has no profile")
        profile = db.get(PlayerProfile, order.profile_id)
        if profile is None:
            raise RuntimeError("order profile is missing")
        _, account = _profile_cash_state(db, profile)
        if account.reserved_cents < order.reserved_cash_cents:
            raise RuntimeError("cash reservation invariant violated")
        account.reserved_cents -= order.reserved_cash_cents
        account.version += 1
        order.reserved_cash_cents = 0
    if order.reserved_shares > 0:
        holding = (
            _profile_holding(
                db,
                order.share_class_id,
                order.profile_id,
                create=False,
            )
            if order.profile_id is not None
            else _issuer_holding(
                db,
                order.share_class_id,
                str(order.issuer_company_id),
            )
        )
        if holding is None or holding.reserved_quantity < order.reserved_shares:
            raise RuntimeError("share reservation invariant violated")
        holding.reserved_quantity -= order.reserved_shares
        holding.version += 1
        order.reserved_shares = 0


def _counter_order(
    db: Session,
    incoming: ExchangeOrder,
) -> ExchangeOrder | None:
    if incoming.side == "buy":
        statement = select(ExchangeOrder).where(
            ExchangeOrder.listing_id == incoming.listing_id,
            ExchangeOrder.side == "sell",
            ExchangeOrder.status.in_(_OPEN_ORDER_STATUSES),
            ExchangeOrder.remaining_quantity > 0,
            or_(
                ExchangeOrder.profile_id.is_(None),
                ExchangeOrder.profile_id != incoming.profile_id,
            ),
            or_(
                ExchangeOrder.expires_at.is_(None),
                ExchangeOrder.expires_at > datetime.now(UTC),
            ),
        )
        if incoming.order_type == "limit":
            statement = statement.where(
                ExchangeOrder.limit_price_cents <= incoming.limit_price_cents
            )
        statement = statement.order_by(
            ExchangeOrder.limit_price_cents.asc(),
            ExchangeOrder.created_at.asc(),
            ExchangeOrder.id.asc(),
        )
    else:
        statement = select(ExchangeOrder).where(
            ExchangeOrder.listing_id == incoming.listing_id,
            ExchangeOrder.side == "buy",
            ExchangeOrder.status.in_(_OPEN_ORDER_STATUSES),
            ExchangeOrder.remaining_quantity > 0,
            ExchangeOrder.profile_id != incoming.profile_id,
            or_(
                ExchangeOrder.expires_at.is_(None),
                ExchangeOrder.expires_at > datetime.now(UTC),
            ),
        )
        if incoming.order_type == "limit":
            statement = statement.where(
                ExchangeOrder.limit_price_cents >= incoming.limit_price_cents
            )
        statement = statement.order_by(
            ExchangeOrder.limit_price_cents.desc(),
            ExchangeOrder.created_at.asc(),
            ExchangeOrder.id.asc(),
        )
    return db.scalar(statement.limit(1).with_for_update())


def _update_order_status(order: ExchangeOrder) -> None:
    if order.remaining_quantity == 0:
        order.status = "filled"
    elif order.remaining_quantity < order.original_quantity:
        order.status = "partially_filled"
    else:
        order.status = "open"


def _assert_price_deviation(
    listing: ExchangeListing,
    price_cents: int,
    settings: Settings,
) -> None:
    deviation_cents = abs(price_cents - listing.last_price_cents)
    if (
        deviation_cents * 10_000
        > listing.last_price_cents * settings.exchange_max_price_deviation_bps
    ):
        raise DomainError(
            422,
            "exchange.price_deviation",
            "Order price exceeds the configured market deviation",
        )


def _execute_trade(
    db: Session,
    listing: ExchangeListing,
    share_class: ShareClass,
    incoming: ExchangeOrder,
    counterpart: ExchangeOrder,
    settings: Settings,
) -> ExchangeTrade:
    buy_order, sell_order = (
        (incoming, counterpart) if incoming.side == "buy" else (counterpart, incoming)
    )
    if buy_order.profile_id is None:
        raise RuntimeError("buy order profile is missing")
    if sell_order.profile_id == buy_order.profile_id:
        raise DomainError(409, "exchange.self_trade", "Self trades are not allowed")
    price_cents = counterpart.limit_price_cents
    if price_cents is None:
        raise RuntimeError("resting exchange order has no price")
    _assert_price_deviation(listing, price_cents, settings)
    quantity = min(buy_order.remaining_quantity, sell_order.remaining_quantity)
    gross_cents = quantity * price_cents
    buyer = db.get(PlayerProfile, buy_order.profile_id)
    if buyer is None:
        raise RuntimeError("buyer profile is missing")
    _, buyer_account = _profile_cash_state(db, buyer)
    buy_reservation_release = (
        gross_cents
        if buy_order.order_type == "market"
        else quantity * int(buy_order.limit_price_cents or 0)
    )
    if (
        buy_reservation_release <= 0
        or buy_order.reserved_cash_cents < buy_reservation_release
        or buyer_account.reserved_cents < buy_reservation_release
    ):
        raise RuntimeError("buy reservation invariant violated")
    buy_order.reserved_cash_cents -= buy_reservation_release
    buyer_account.reserved_cents -= buy_reservation_release
    buyer_account.version += 1

    seller_holding = (
        _profile_holding(
            db,
            share_class.id,
            sell_order.profile_id,
            create=False,
        )
        if sell_order.profile_id is not None
        else _issuer_holding(
            db,
            share_class.id,
            str(sell_order.issuer_company_id),
        )
    )
    if (
        seller_holding is None
        or sell_order.reserved_shares < quantity
        or seller_holding.reserved_quantity < quantity
        or seller_holding.quantity < quantity
    ):
        raise RuntimeError("sell reservation invariant violated")
    sell_order.reserved_shares -= quantity
    seller_holding.reserved_quantity -= quantity
    seller_holding.quantity -= quantity
    seller_holding.version += 1

    buyer_holding = _profile_holding(
        db,
        share_class.id,
        buyer.id,
        create=True,
    )
    if buyer_holding is None:
        raise RuntimeError("buyer holding was not created")
    buyer_old_quantity = buyer_holding.quantity
    buyer_holding.quantity += quantity
    buyer_holding.average_cost_cents = (
        buyer_old_quantity * buyer_holding.average_cost_cents + gross_cents
    ) // buyer_holding.quantity
    buyer_holding.version += 1

    trade_id = uuid_str()
    if sell_order.profile_id is not None:
        seller = db.get(PlayerProfile, sell_order.profile_id)
        if seller is None:
            raise RuntimeError("seller profile is missing")
        money_transaction = transfer_profile_cash_between_profiles(
            db,
            buyer,
            seller,
            amount_cents=gross_cents,
            transaction_type="exchange_trade",
            idempotency_key=f"exchange-trade:{trade_id}",
            reference_type="exchange_trade",
            reference_id=trade_id,
        )
        seller_company_id = None
        seller_owner_key = seller.id
    else:
        seller_company_id = sell_order.issuer_company_id
        company = db.get(Company, seller_company_id)
        if company is None:
            raise RuntimeError("issuer company is missing")
        money_transaction = transfer_profile_cash_to_account(
            db,
            buyer,
            company.account,
            amount_cents=gross_cents,
            transaction_type="exchange_primary_trade",
            idempotency_key=f"exchange-trade:{trade_id}",
            reference_type="exchange_trade",
            reference_id=trade_id,
        )
        seller_owner_key = company.id
    trade = ExchangeTrade(
        id=trade_id,
        listing_id=listing.id,
        share_class_id=share_class.id,
        buy_order_id=buy_order.id,
        sell_order_id=sell_order.id,
        buyer_profile_id=buyer.id,
        seller_profile_id=sell_order.profile_id,
        seller_company_id=seller_company_id,
        seller_owner_key=seller_owner_key,
        quantity=quantity,
        price_cents=price_cents,
        gross_cents=gross_cents,
        transaction_id=money_transaction.id,
    )
    db.add(trade)
    db.flush()
    event_key = f"exchange-trade:{trade.id}"
    db.add_all(
        (
            ShareLedgerEntry(
                share_class_id=share_class.id,
                holding_id=seller_holding.id,
                quantity_delta=-quantity,
                balance_after=seller_holding.quantity,
                reason="exchange_trade",
                reference_type="exchange_trade",
                reference_id=trade.id,
                event_key=event_key,
            ),
            ShareLedgerEntry(
                share_class_id=share_class.id,
                holding_id=buyer_holding.id,
                quantity_delta=quantity,
                balance_after=buyer_holding.quantity,
                reason="exchange_trade",
                reference_type="exchange_trade",
                reference_id=trade.id,
                event_key=event_key,
            ),
            PriceSnapshot(
                listing_id=listing.id,
                trade_id=trade.id,
                price_cents=price_cents,
                volume=quantity,
            ),
        )
    )
    listing.last_price_cents = price_cents
    buy_order.remaining_quantity -= quantity
    sell_order.remaining_quantity -= quantity
    _update_order_status(buy_order)
    _update_order_status(sell_order)
    _assert_share_supply(db, share_class)
    _rebuild_ownership(db, listing.company_id, share_class)
    create_notification(
        db,
        buyer.user_id,
        "exchange.trade.executed",
        f"{listing.symbol} purchase executed",
        f"{quantity} shares bought at {price_cents} cents.",
        {"trade_id": trade.id, "listing_id": listing.id, "side": "buy"},
    )
    if sell_order.profile_id is not None:
        seller = db.get(PlayerProfile, sell_order.profile_id)
        if seller is None:
            raise RuntimeError("seller profile is missing")
        create_notification(
            db,
            seller.user_id,
            "exchange.trade.executed",
            f"{listing.symbol} sale executed",
            f"{quantity} shares sold at {price_cents} cents.",
            {"trade_id": trade.id, "listing_id": listing.id, "side": "sell"},
        )
    else:
        issuer = db.get(Company, sell_order.issuer_company_id)
        founder = db.get(PlayerProfile, issuer.founder_profile_id) if issuer is not None else None
        if founder is not None:
            create_notification(
                db,
                founder.user_id,
                "exchange.trade.executed",
                f"{listing.symbol} IPO allocation executed",
                f"{quantity} offered shares sold at {price_cents} cents.",
                {"trade_id": trade.id, "listing_id": listing.id, "side": "issuer_sell"},
            )
    emit_realtime_event(
        db,
        world_id=listing.world_id,
        event_type="exchange.trade.executed",
        payload={
            "trade_id": trade.id,
            "listing_id": listing.id,
            "symbol": listing.symbol,
            "quantity": quantity,
            "price_cents": price_cents,
        },
        dedupe_key=f"exchange-trade:{trade.id}",
    )
    for changed_order in (buy_order, sell_order):
        emit_realtime_event(
            db,
            world_id=listing.world_id,
            event_type="exchange.order.updated",
            payload={
                "order_id": changed_order.id,
                "listing_id": listing.id,
                "status": changed_order.status,
                "remaining_quantity": changed_order.remaining_quantity,
            },
            audience_type=("player" if changed_order.profile_id is not None else "world"),
            audience_id=changed_order.profile_id,
            dedupe_key=f"exchange-order:{changed_order.id}:trade:{trade.id}",
        )
    return trade


def _match_order(
    db: Session,
    listing: ExchangeListing,
    share_class: ShareClass,
    order: ExchangeOrder,
    settings: Settings,
) -> list[ExchangeTrade]:
    trades: list[ExchangeTrade] = []
    while order.remaining_quantity > 0:
        counterpart = _counter_order(db, order)
        if counterpart is None:
            break
        trades.append(
            _execute_trade(
                db,
                listing,
                share_class,
                order,
                counterpart,
                settings,
            )
        )
    if order.order_type == "market" and order.remaining_quantity > 0:
        _release_order_reservation(db, order)
        order.status = "cancelled"
    return trades


def place_order(
    db: Session,
    profile: PlayerProfile,
    *,
    listing_id: str,
    side: str,
    order_type: str,
    quantity: int,
    limit_price_cents: int | None,
    expires_at: datetime | None,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
) -> ExchangeOrder:
    with _local_exchange_lock:
        return _place_order_locked(
            db,
            profile,
            listing_id=listing_id,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price_cents=limit_price_cents,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
            request_id=request_id,
            settings=settings,
        )


def _place_order_locked(
    db: Session,
    profile: PlayerProfile,
    *,
    listing_id: str,
    side: str,
    order_type: str,
    quantity: int,
    limit_price_cents: int | None,
    expires_at: datetime | None,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
) -> ExchangeOrder:
    existing = db.scalar(
        select(ExchangeOrder).where(
            ExchangeOrder.owner_key == profile.id,
            ExchangeOrder.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        return existing
    if side not in {"buy", "sell"} or order_type not in {"market", "limit"}:
        raise DomainError(422, "exchange.invalid_order", "Unknown order side or type")
    if quantity <= 0:
        raise DomainError(422, "exchange.invalid_quantity", "Order quantity must be positive")
    if order_type == "limit" and (limit_price_cents is None or limit_price_cents <= 0):
        raise DomainError(422, "exchange.limit_price_required", "Limit price must be positive")
    if order_type == "market" and limit_price_cents is not None:
        raise DomainError(422, "exchange.market_price_forbidden", "Market order has no limit")
    now = datetime.now(UTC)
    if expires_at is not None and expires_at <= now:
        raise DomainError(422, "exchange.invalid_expiry", "Order expiry must be in the future")
    listing = get_exchange_listing(db, profile, listing_id, lock=True)
    _lock_exchange_world(db, listing.world_id)
    if listing.status != "active":
        raise DomainError(409, "exchange.listing_inactive", "Exchange listing is not active")
    share_class = _share_class_for_listing(db, listing.id, lock=True)
    if limit_price_cents is not None:
        _assert_price_deviation(listing, limit_price_cents, settings)
    order = ExchangeOrder(
        listing_id=listing.id,
        share_class_id=share_class.id,
        profile_id=profile.id,
        owner_key=profile.id,
        side=side,
        order_type=order_type,
        limit_price_cents=limit_price_cents,
        original_quantity=quantity,
        remaining_quantity=quantity,
        reserved_cash_cents=0,
        reserved_shares=0,
        status="open",
        idempotency_key=idempotency_key,
        expires_at=expires_at,
    )
    if side == "buy":
        _, account = _profile_cash_state(db, profile)
        reservation_cents = (
            quantity * int(limit_price_cents or 0)
            if order_type == "limit"
            else _market_buy_reservation(db, listing.id, profile.id, quantity)
        )
        if account.balance_cents - account.reserved_cents < reservation_cents:
            raise DomainError(409, "resource.insufficient", "Insufficient available cash")
        account.reserved_cents += reservation_cents
        account.version += 1
        order.reserved_cash_cents = reservation_cents
    else:
        holding = _profile_holding(db, share_class.id, profile.id, create=False)
        if holding is None or holding.quantity - holding.reserved_quantity < quantity:
            raise DomainError(409, "exchange.insufficient_shares", "Insufficient available shares")
        holding.reserved_quantity += quantity
        holding.version += 1
        order.reserved_shares = quantity
    db.add(order)
    db.flush()
    trades = _match_order(db, listing, share_class, order, settings)
    emit_realtime_event(
        db,
        world_id=listing.world_id,
        event_type="exchange.order.updated",
        payload={
            "order_id": order.id,
            "listing_id": listing.id,
            "status": order.status,
            "remaining_quantity": order.remaining_quantity,
        },
        audience_type="player",
        audience_id=profile.id,
        dedupe_key=f"exchange-order-created:{order.id}",
    )
    audit(
        db,
        profile.user_id,
        "exchange.order.create",
        "exchange_order",
        order.id,
        request_id,
        {
            "listing_id": listing.id,
            "side": side,
            "order_type": order_type,
            "quantity": quantity,
            "limit_price_cents": limit_price_cents,
            "trade_ids": [trade.id for trade in trades],
        },
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = db.scalar(
            select(ExchangeOrder).where(
                ExchangeOrder.owner_key == profile.id,
                ExchangeOrder.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        raise DomainError(
            409,
            "exchange.order_conflict",
            "Order conflicts with current market state",
        ) from exc
    db.refresh(order)
    return order


def cancel_order(
    db: Session,
    profile: PlayerProfile,
    order_id: str,
    *,
    idempotency_key: str,
    request_id: str,
) -> ExchangeOrder:
    with _local_exchange_lock:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "exchange.order.cancel",
        )
        if previous is not None:
            existing = db.get(ExchangeOrder, previous.resource_id)
            if existing is not None:
                return existing
        initial_order = db.scalar(
            select(ExchangeOrder).where(
                ExchangeOrder.id == order_id,
                ExchangeOrder.profile_id == profile.id,
            )
        )
        if initial_order is None:
            raise DomainError(404, "exchange.order_not_found", "Exchange order not found")
        listing = get_exchange_listing(db, profile, initial_order.listing_id, lock=True)
        _lock_exchange_world(db, listing.world_id)
        order = db.scalar(
            select(ExchangeOrder)
            .where(
                ExchangeOrder.id == order_id,
                ExchangeOrder.profile_id == profile.id,
            )
            .with_for_update()
        )
        if order is None:
            raise DomainError(404, "exchange.order_not_found", "Exchange order not found")
        if order.status in _OPEN_ORDER_STATUSES:
            _release_order_reservation(db, order)
            order.status = "cancelled"
        elif order.status not in {"cancelled", "expired"}:
            raise DomainError(409, "exchange.order_closed", "Filled order cannot be cancelled")
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "exchange.order.cancel",
            order.id,
            {"order_id": order.id},
        )
        audit(
            db,
            profile.user_id,
            "exchange.order.cancel",
            "exchange_order",
            order.id,
            request_id,
            {},
        )
        emit_realtime_event(
            db,
            world_id=listing.world_id,
            event_type="exchange.order.updated",
            payload={
                "order_id": order.id,
                "listing_id": listing.id,
                "status": order.status,
                "remaining_quantity": order.remaining_quantity,
            },
            audience_type="player",
            audience_id=profile.id,
            dedupe_key=f"exchange-order-cancelled:{order.id}",
        )
        db.commit()
        db.refresh(order)
        return order


def expire_due_orders(
    db: Session,
    *,
    at: datetime | None = None,
) -> int:
    now = at or datetime.now(UTC)
    with _local_exchange_lock:
        order_rows = list(
            db.execute(
                select(ExchangeOrder.id, ExchangeOrder.listing_id)
                .where(
                    ExchangeOrder.status.in_(_OPEN_ORDER_STATUSES),
                    ExchangeOrder.expires_at.is_not(None),
                    ExchangeOrder.expires_at <= now,
                )
                .order_by(ExchangeOrder.expires_at, ExchangeOrder.id)
            )
        )
        for order_id, listing_id in order_rows:
            listing = db.scalar(
                select(ExchangeListing).where(ExchangeListing.id == listing_id).with_for_update()
            )
            if listing is None:
                continue
            _lock_exchange_world(db, listing.world_id)
            order = db.scalar(
                select(ExchangeOrder).where(ExchangeOrder.id == order_id).with_for_update()
            )
            if order is None or order.status not in _OPEN_ORDER_STATUSES:
                continue
            _release_order_reservation(db, order)
            order.status = "expired"
            emit_realtime_event(
                db,
                world_id=listing.world_id,
                event_type="exchange.order.updated",
                payload={
                    "order_id": order.id,
                    "listing_id": listing.id,
                    "status": order.status,
                    "remaining_quantity": order.remaining_quantity,
                },
                audience_type=("player" if order.profile_id is not None else "world"),
                audience_id=order.profile_id,
                dedupe_key=f"exchange-order-expired:{order.id}",
                at=now,
            )
        db.commit()
        return len(order_rows)


def archive_world_exchange(db: Session, world_id: str) -> dict[str, int]:
    """Close a season's exchange without deleting holdings or trade history."""
    with _local_exchange_lock:
        _lock_exchange_world(db, world_id)
        listings = list(
            db.scalars(
                select(ExchangeListing)
                .where(ExchangeListing.world_id == world_id)
                .order_by(ExchangeListing.id)
                .with_for_update()
            )
        )
        listing_ids = [listing.id for listing in listings]
        orders = (
            list(
                db.scalars(
                    select(ExchangeOrder)
                    .where(
                        ExchangeOrder.listing_id.in_(listing_ids),
                        ExchangeOrder.status.in_(_OPEN_ORDER_STATUSES),
                    )
                    .order_by(ExchangeOrder.id)
                    .with_for_update()
                )
            )
            if listing_ids
            else []
        )
        for order in orders:
            _release_order_reservation(db, order)
            order.status = "cancelled"
        share_classes = (
            list(
                db.scalars(
                    select(ShareClass)
                    .where(ShareClass.listing_id.in_(listing_ids))
                    .order_by(ShareClass.id)
                    .with_for_update()
                )
            )
            if listing_ids
            else []
        )
        for share_class in share_classes:
            share_class.tradable = False
        for listing in listings:
            listing.status = "delisted"
        db.flush()
        return {
            "listings": len(listings),
            "orders_cancelled": len(orders),
            "share_classes": len(share_classes),
        }


def list_profile_orders(
    db: Session,
    profile: PlayerProfile,
    *,
    limit: int = 100,
) -> list[ExchangeOrder]:
    return list(
        db.scalars(
            select(ExchangeOrder)
            .where(ExchangeOrder.profile_id == profile.id)
            .order_by(ExchangeOrder.created_at.desc())
            .limit(limit)
        )
    )


def listing_order_book(
    db: Session,
    profile: PlayerProfile,
    listing_id: str,
    *,
    limit: int = 50,
) -> tuple[list[ExchangeOrder], list[ExchangeOrder]]:
    listing = get_exchange_listing(db, profile, listing_id)
    active_expiry = or_(
        ExchangeOrder.expires_at.is_(None),
        ExchangeOrder.expires_at > datetime.now(UTC),
    )
    base = select(ExchangeOrder).where(
        ExchangeOrder.listing_id == listing.id,
        ExchangeOrder.status.in_(_OPEN_ORDER_STATUSES),
        ExchangeOrder.remaining_quantity > 0,
        active_expiry,
    )
    buys = list(
        db.scalars(
            base.where(ExchangeOrder.side == "buy")
            .order_by(
                ExchangeOrder.limit_price_cents.desc(),
                ExchangeOrder.created_at,
                ExchangeOrder.id,
            )
            .limit(limit)
        )
    )
    sells = list(
        db.scalars(
            base.where(ExchangeOrder.side == "sell")
            .order_by(
                ExchangeOrder.limit_price_cents.asc(),
                ExchangeOrder.created_at,
                ExchangeOrder.id,
            )
            .limit(limit)
        )
    )
    return buys, sells


def listing_trades(
    db: Session,
    profile: PlayerProfile,
    listing_id: str,
    *,
    limit: int = 100,
) -> list[ExchangeTrade]:
    listing = get_exchange_listing(db, profile, listing_id)
    return list(
        db.scalars(
            select(ExchangeTrade)
            .where(ExchangeTrade.listing_id == listing.id)
            .order_by(ExchangeTrade.executed_at.desc())
            .limit(limit)
        )
    )


def listing_price_history(
    db: Session,
    profile: PlayerProfile,
    listing_id: str,
    *,
    limit: int = 200,
) -> list[PriceSnapshot]:
    listing = get_exchange_listing(db, profile, listing_id)
    return list(
        db.scalars(
            select(PriceSnapshot)
            .where(PriceSnapshot.listing_id == listing.id)
            .order_by(PriceSnapshot.captured_at.desc())
            .limit(limit)
        )
    )


def profile_portfolio(
    db: Session,
    profile: PlayerProfile,
) -> list[PortfolioPosition]:
    return [
        PortfolioPosition(
            holding_id=holding.id,
            listing_id=listing.id,
            company_id=company.id,
            company_name=company.name,
            symbol=listing.symbol,
            share_class=share_class.class_code,
            quantity=holding.quantity,
            reserved_quantity=holding.reserved_quantity,
            available_quantity=holding.quantity - holding.reserved_quantity,
            average_cost_cents=holding.average_cost_cents,
            last_price_cents=listing.last_price_cents,
            market_value_cents=holding.quantity * listing.last_price_cents,
            voting_rights=holding.quantity * share_class.voting_rights_per_share,
        )
        for holding, share_class, listing, company in db.execute(
            select(ShareHolding, ShareClass, ExchangeListing, Company)
            .join(ShareClass, ShareClass.id == ShareHolding.share_class_id)
            .join(ExchangeListing, ExchangeListing.id == ShareClass.listing_id)
            .join(Company, Company.id == ExchangeListing.company_id)
            .where(
                ShareHolding.profile_id == profile.id,
                ShareHolding.quantity > 0,
            )
            .order_by(ExchangeListing.symbol)
        )
    ]


def listing_shareholders(
    db: Session,
    profile: PlayerProfile,
    listing_id: str,
    *,
    limit: int = 50,
) -> list[ShareholderPosition]:
    listing = get_exchange_listing(db, profile, listing_id)
    share_class = _share_class_for_listing(db, listing.id, lock=False)
    return [
        ShareholderPosition(
            holding_id=holding.id,
            profile_id=shareholder.id,
            codename=shareholder.codename,
            quantity=holding.quantity,
            ownership_bps=holding.quantity * 10_000 // share_class.total_shares,
            voting_rights=holding.quantity * share_class.voting_rights_per_share,
        )
        for holding, shareholder in db.execute(
            select(ShareHolding, PlayerProfile)
            .join(PlayerProfile, PlayerProfile.id == ShareHolding.profile_id)
            .where(
                ShareHolding.share_class_id == share_class.id,
                ShareHolding.quantity > 0,
            )
            .order_by(ShareHolding.quantity.desc(), ShareHolding.profile_id)
            .limit(limit)
        )
    ]


def declare_dividend(
    db: Session,
    profile: PlayerProfile,
    *,
    listing_id: str,
    per_share_cents: int,
    idempotency_key: str,
    request_id: str,
) -> DividendDeclaration:
    with _local_exchange_lock:
        existing = db.scalar(
            select(DividendDeclaration).where(
                DividendDeclaration.declared_by_profile_id == profile.id,
                DividendDeclaration.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return existing
        if per_share_cents <= 0:
            raise DomainError(
                422,
                "exchange.invalid_dividend",
                "Dividend per share must be positive",
            )
        listing = get_exchange_listing(db, profile, listing_id, lock=True)
        _lock_exchange_world(db, listing.world_id)
        company = _controlled_company(db, profile, listing.company_id, lock=True)
        share_class = _share_class_for_listing(db, listing.id, lock=True)
        holdings = list(
            db.scalars(
                select(ShareHolding)
                .where(
                    ShareHolding.share_class_id == share_class.id,
                    ShareHolding.profile_id.is_not(None),
                    ShareHolding.quantity > 0,
                )
                .order_by(ShareHolding.profile_id)
                .with_for_update()
            )
        )
        eligible_shares = sum(holding.quantity for holding in holdings)
        total_paid_cents = eligible_shares * per_share_cents
        if eligible_shares <= 0 or total_paid_cents <= 0:
            raise DomainError(
                409,
                "exchange.no_dividend_holders",
                "No profile holding is eligible for a dividend",
            )
        if company.account.balance_cents - company.account.reserved_cents < total_paid_cents:
            raise DomainError(
                409,
                "resource.insufficient",
                "Company cannot fund the complete dividend",
            )
        now = datetime.now(UTC)
        declaration = DividendDeclaration(
            listing_id=listing.id,
            share_class_id=share_class.id,
            declared_by_profile_id=profile.id,
            per_share_cents=per_share_cents,
            total_paid_cents=total_paid_cents,
            eligible_shares=eligible_shares,
            status="paid",
            idempotency_key=idempotency_key,
            snapshot_at=now,
            paid_at=now,
        )
        db.add(declaration)
        db.flush()
        for holding in holdings:
            if holding.profile_id is None:
                continue
            recipient = db.get(PlayerProfile, holding.profile_id)
            if recipient is None:
                raise RuntimeError("dividend recipient is missing")
            entitlement_id = uuid_str()
            amount_cents = holding.quantity * per_share_cents
            transaction = transfer_account_to_profile_cash(
                db,
                company.account,
                recipient,
                amount_cents=amount_cents,
                transaction_type="exchange_dividend",
                idempotency_key=f"dividend:{declaration.id}:{holding.id}",
                reference_type="dividend_entitlement",
                reference_id=entitlement_id,
            )
            db.add(
                DividendEntitlement(
                    id=entitlement_id,
                    declaration_id=declaration.id,
                    holding_id=holding.id,
                    recipient_profile_id=recipient.id,
                    quantity=holding.quantity,
                    amount_cents=amount_cents,
                    transaction_id=transaction.id,
                )
            )
        audit(
            db,
            profile.user_id,
            "exchange.dividend.declare",
            "dividend_declaration",
            declaration.id,
            request_id,
            {
                "listing_id": listing.id,
                "per_share_cents": per_share_cents,
                "eligible_shares": eligible_shares,
                "total_paid_cents": total_paid_cents,
            },
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            existing = db.scalar(
                select(DividendDeclaration).where(
                    DividendDeclaration.declared_by_profile_id == profile.id,
                    DividendDeclaration.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return existing
            raise DomainError(
                409,
                "exchange.dividend_conflict",
                "Dividend conflicts with current state",
            ) from exc
        db.refresh(declaration)
        return declaration


def list_dividends(
    db: Session,
    profile: PlayerProfile,
    listing_id: str,
    *,
    limit: int = 50,
) -> list[DividendDeclaration]:
    listing = get_exchange_listing(db, profile, listing_id)
    return list(
        db.scalars(
            select(DividendDeclaration)
            .where(DividendDeclaration.listing_id == listing.id)
            .order_by(DividendDeclaration.created_at.desc())
            .limit(limit)
        )
    )


def listing_company_reports(
    db: Session,
    profile: PlayerProfile,
    listing_id: str,
    *,
    limit: int = 24,
) -> list[CompanyEconomyReport]:
    listing = get_exchange_listing(db, profile, listing_id)
    return list(
        db.scalars(
            select(CompanyEconomyReport)
            .where(CompanyEconomyReport.company_id == listing.company_id)
            .order_by(CompanyEconomyReport.created_at.desc())
            .limit(limit)
        )
    )
