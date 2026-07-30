from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from shadowgrid.errors import DomainError
from shadowgrid.models import (
    Account,
    AccountLedgerEntry,
    LedgerEntry,
    LedgerTransaction,
    PlayerProfile,
    ResourceBalance,
)
from shadowgrid.realtime import emit_realtime_event

CENT = Decimal("0.01")


@dataclass(frozen=True)
class CompanySettlement:
    transaction: LedgerTransaction | None
    cash_delta_cents: int
    debt_delta_cents: int


def money_to_cents(value: Decimal) -> int:
    normalized = value.quantize(CENT)
    cents = normalized * Decimal(100)
    if cents != cents.to_integral_value():
        raise ValueError("money must resolve to whole cents")
    return int(cents)


def cents_to_money(value: int) -> Decimal:
    return (Decimal(value) / Decimal(100)).quantize(CENT)


def ensure_system_account(db: Session, world_id: str) -> Account:
    account = db.scalar(
        select(Account)
        .where(
            Account.world_id == world_id,
            Account.owner_type == "system",
            Account.owner_id == world_id,
            Account.currency == "EUR",
        )
        .with_for_update()
    )
    if account is None:
        account = Account(
            world_id=world_id,
            owner_type="system",
            owner_id=world_id,
            currency="EUR",
            balance_cents=0,
        )
        db.add(account)
        db.flush()
    return account


def find_transaction(db: Session, world_id: str, idempotency_key: str) -> LedgerTransaction | None:
    return db.scalar(
        select(LedgerTransaction).where(
            LedgerTransaction.world_id == world_id,
            LedgerTransaction.idempotency_key == idempotency_key,
        )
    )


def post_balanced_transfer(
    db: Session,
    *,
    world_id: str,
    source_account: Account,
    target_account: Account,
    amount_cents: int,
    transaction_type: str,
    idempotency_key: str,
    reference_type: str,
    reference_id: str,
    actor_profile_id: str | None,
    metadata: dict[str, object] | None = None,
) -> LedgerTransaction:
    if amount_cents <= 0:
        raise ValueError("transfer amount must be positive")
    existing = find_transaction(db, world_id, idempotency_key)
    if existing is not None:
        return existing

    db.flush()
    account_ids = sorted((source_account.id, target_account.id))
    locked = list(
        db.scalars(
            select(Account)
            .where(Account.id.in_(account_ids))
            .order_by(Account.id)
            .with_for_update()
        )
    )
    accounts = {account.id: account for account in locked}
    source = accounts.get(source_account.id)
    target = accounts.get(target_account.id)
    if source is None or target is None:
        raise DomainError(409, "ledger.account_missing", "A financial account is missing")
    if (
        source.owner_type != "system"
        and source.balance_cents - source.reserved_cents < amount_cents
    ):
        raise DomainError(409, "resource.insufficient", "Insufficient cash")

    source.balance_cents -= amount_cents
    source.version += 1
    target.balance_cents += amount_cents
    target.version += 1
    transaction = LedgerTransaction(
        world_id=world_id,
        actor_profile_id=actor_profile_id,
        transaction_type=transaction_type,
        idempotency_key=idempotency_key,
        reference_type=reference_type,
        reference_id=reference_id,
        metadata_json=metadata or {},
    )
    db.add(transaction)
    db.flush()
    db.add_all(
        (
            AccountLedgerEntry(
                transaction_id=transaction.id,
                account_id=source.id,
                amount_cents=-amount_cents,
                balance_after_cents=source.balance_cents,
            ),
            AccountLedgerEntry(
                transaction_id=transaction.id,
                account_id=target.id,
                amount_cents=amount_cents,
                balance_after_cents=target.balance_cents,
            ),
        )
    )
    db.flush()
    if transaction_balance_cents(db, transaction.id) != 0:
        raise RuntimeError("financial transaction is not balanced")
    return transaction


def ensure_profile_cash_account(
    db: Session,
    profile: PlayerProfile,
    opening_balance_cents: int,
) -> Account:
    account = db.scalar(
        select(Account)
        .where(
            Account.world_id == profile.world_id,
            Account.owner_type == "profile",
            Account.owner_id == profile.id,
            Account.currency == "EUR",
        )
        .with_for_update()
    )
    if account is None:
        account = Account(
            world_id=profile.world_id,
            owner_type="profile",
            owner_id=profile.id,
            currency="EUR",
            balance_cents=0,
        )
        db.add(account)
        db.flush()
        if opening_balance_cents > 0:
            post_balanced_transfer(
                db,
                world_id=profile.world_id,
                source_account=ensure_system_account(db, profile.world_id),
                target_account=account,
                amount_cents=opening_balance_cents,
                transaction_type="profile_opening_balance",
                idempotency_key=f"profile-opening:{profile.id}",
                reference_type="profile",
                reference_id=profile.id,
                actor_profile_id=profile.id,
            )
    if account.balance_cents != opening_balance_cents:
        raise DomainError(
            409,
            "ledger.balance_mismatch",
            "Player cash and financial account are not synchronized",
        )
    return account


def create_company_cash_account(db: Session, world_id: str, company_id: str) -> Account:
    account = Account(
        world_id=world_id,
        owner_type="company",
        owner_id=company_id,
        currency="EUR",
        balance_cents=0,
    )
    db.add(account)
    db.flush()
    return account


def sync_profile_cash_delta(
    db: Session,
    profile: PlayerProfile,
    *,
    current_balance_cents: int,
    delta_cents: int,
    reason: str,
    reference_type: str,
    reference_id: str,
    idempotency_key: str,
) -> LedgerTransaction | None:
    if delta_cents == 0:
        return None
    profile_account = ensure_profile_cash_account(db, profile, current_balance_cents)
    system_account = ensure_system_account(db, profile.world_id)
    source, target = (
        (system_account, profile_account) if delta_cents > 0 else (profile_account, system_account)
    )
    transaction = post_balanced_transfer(
        db,
        world_id=profile.world_id,
        source_account=source,
        target_account=target,
        amount_cents=abs(delta_cents),
        transaction_type=f"profile_resource_{reason}",
        idempotency_key=f"resource:{profile.id}:{idempotency_key}",
        reference_type=reference_type,
        reference_id=reference_id,
        actor_profile_id=profile.id,
        metadata={"resource_type": "cash"},
    )
    emit_realtime_event(
        db,
        world_id=profile.world_id,
        event_type="player.resources.updated",
        payload={
            "profile_id": profile.id,
            "resource_type": "cash",
            "balance_cents": current_balance_cents + delta_cents,
        },
        audience_type="player",
        audience_id=profile.id,
        dedupe_key=f"player-resource:{transaction.id}:{profile.id}",
    )
    return transaction


def transfer_profile_cash_to_account(
    db: Session,
    profile: PlayerProfile,
    target_account: Account,
    *,
    amount_cents: int,
    transaction_type: str,
    idempotency_key: str,
    reference_type: str,
    reference_id: str,
) -> LedgerTransaction:
    existing = find_transaction(db, profile.world_id, idempotency_key)
    if existing is not None:
        return existing
    balance = db.scalar(
        select(ResourceBalance).where(ResourceBalance.profile_id == profile.id).with_for_update()
    )
    if balance is None:
        raise DomainError(409, "resource.missing", "Player cash balance does not exist")
    current_cents = money_to_cents(balance.cash)
    if current_cents < amount_cents:
        raise DomainError(409, "resource.insufficient", "Insufficient cash")
    profile_account = ensure_profile_cash_account(db, profile, current_cents)
    transaction = post_balanced_transfer(
        db,
        world_id=profile.world_id,
        source_account=profile_account,
        target_account=target_account,
        amount_cents=amount_cents,
        transaction_type=transaction_type,
        idempotency_key=idempotency_key,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_profile_id=profile.id,
    )
    new_balance_cents = current_cents - amount_cents
    balance.cash = cents_to_money(new_balance_cents)
    balance.version += 1
    db.add(
        LedgerEntry(
            owner_type="profile",
            owner_id=profile.id,
            resource_type="cash",
            amount=-cents_to_money(amount_cents),
            balance_after=cents_to_money(new_balance_cents),
            reason=transaction_type,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata_json={"financial_transaction_id": transaction.id},
        )
    )
    db.flush()
    emit_realtime_event(
        db,
        world_id=profile.world_id,
        event_type="player.resources.updated",
        payload={
            "profile_id": profile.id,
            "resource_type": "cash",
            "balance_cents": new_balance_cents,
        },
        audience_type="player",
        audience_id=profile.id,
        dedupe_key=f"player-resource:{transaction.id}:{profile.id}",
    )
    return transaction


def transfer_profile_cash_between_profiles(
    db: Session,
    source_profile: PlayerProfile,
    target_profile: PlayerProfile,
    *,
    amount_cents: int,
    transaction_type: str,
    idempotency_key: str,
    reference_type: str,
    reference_id: str,
) -> LedgerTransaction:
    if source_profile.world_id != target_profile.world_id:
        raise DomainError(422, "exchange.world_mismatch", "Profiles belong to different worlds")
    existing = find_transaction(db, source_profile.world_id, idempotency_key)
    if existing is not None:
        return existing
    profile_ids = sorted((source_profile.id, target_profile.id))
    balances = list(
        db.scalars(
            select(ResourceBalance)
            .where(ResourceBalance.profile_id.in_(profile_ids))
            .order_by(ResourceBalance.profile_id)
            .with_for_update()
        )
    )
    balances_by_profile = {balance.profile_id: balance for balance in balances}
    source_balance = balances_by_profile.get(source_profile.id)
    target_balance = balances_by_profile.get(target_profile.id)
    if source_balance is None or target_balance is None:
        raise DomainError(409, "resource.missing", "Player cash balance does not exist")
    source_cents = money_to_cents(source_balance.cash)
    target_cents = money_to_cents(target_balance.cash)
    accounts: dict[str, Account] = {}
    profiles = {
        source_profile.id: source_profile,
        target_profile.id: target_profile,
    }
    for profile_id in profile_ids:
        opening_cents = source_cents if profile_id == source_profile.id else target_cents
        accounts[profile_id] = ensure_profile_cash_account(
            db,
            profiles[profile_id],
            opening_cents,
        )
    transaction = post_balanced_transfer(
        db,
        world_id=source_profile.world_id,
        source_account=accounts[source_profile.id],
        target_account=accounts[target_profile.id],
        amount_cents=amount_cents,
        transaction_type=transaction_type,
        idempotency_key=idempotency_key,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_profile_id=source_profile.id,
    )
    source_balance.cash = cents_to_money(source_cents - amount_cents)
    source_balance.version += 1
    target_balance.cash = cents_to_money(target_cents + amount_cents)
    target_balance.version += 1
    db.add_all(
        (
            LedgerEntry(
                owner_type="profile",
                owner_id=source_profile.id,
                resource_type="cash",
                amount=-cents_to_money(amount_cents),
                balance_after=source_balance.cash,
                reason=transaction_type,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                metadata_json={"financial_transaction_id": transaction.id},
            ),
            LedgerEntry(
                owner_type="profile",
                owner_id=target_profile.id,
                resource_type="cash",
                amount=cents_to_money(amount_cents),
                balance_after=target_balance.cash,
                reason=transaction_type,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                metadata_json={"financial_transaction_id": transaction.id},
            ),
        )
    )
    db.flush()
    for updated_profile, updated_cents in (
        (source_profile, source_cents - amount_cents),
        (target_profile, target_cents + amount_cents),
    ):
        emit_realtime_event(
            db,
            world_id=updated_profile.world_id,
            event_type="player.resources.updated",
            payload={
                "profile_id": updated_profile.id,
                "resource_type": "cash",
                "balance_cents": updated_cents,
            },
            audience_type="player",
            audience_id=updated_profile.id,
            dedupe_key=f"player-resource:{transaction.id}:{updated_profile.id}",
        )
    return transaction


def transfer_account_to_profile_cash(
    db: Session,
    source_account: Account,
    target_profile: PlayerProfile,
    *,
    amount_cents: int,
    transaction_type: str,
    idempotency_key: str,
    reference_type: str,
    reference_id: str,
) -> LedgerTransaction:
    existing = find_transaction(db, target_profile.world_id, idempotency_key)
    if existing is not None:
        return existing
    balance = db.scalar(
        select(ResourceBalance)
        .where(ResourceBalance.profile_id == target_profile.id)
        .with_for_update()
    )
    if balance is None:
        raise DomainError(409, "resource.missing", "Player cash balance does not exist")
    current_cents = money_to_cents(balance.cash)
    target_account = ensure_profile_cash_account(db, target_profile, current_cents)
    transaction = post_balanced_transfer(
        db,
        world_id=target_profile.world_id,
        source_account=source_account,
        target_account=target_account,
        amount_cents=amount_cents,
        transaction_type=transaction_type,
        idempotency_key=idempotency_key,
        reference_type=reference_type,
        reference_id=reference_id,
        actor_profile_id=target_profile.id,
    )
    balance.cash = cents_to_money(current_cents + amount_cents)
    balance.version += 1
    db.add(
        LedgerEntry(
            owner_type="profile",
            owner_id=target_profile.id,
            resource_type="cash",
            amount=cents_to_money(amount_cents),
            balance_after=balance.cash,
            reason=transaction_type,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata_json={"financial_transaction_id": transaction.id},
        )
    )
    db.flush()
    emit_realtime_event(
        db,
        world_id=target_profile.world_id,
        event_type="player.resources.updated",
        payload={
            "profile_id": target_profile.id,
            "resource_type": "cash",
            "balance_cents": current_cents + amount_cents,
        },
        audience_type="player",
        audience_id=target_profile.id,
        dedupe_key=f"player-resource:{transaction.id}:{target_profile.id}",
    )
    return transaction


def settle_company_operating_result(
    db: Session,
    *,
    world_id: str,
    company_id: str,
    company_account: Account,
    profit_cents: int,
    idempotency_key: str,
    reference_id: str,
) -> CompanySettlement:
    if profit_cents == 0:
        return CompanySettlement(transaction=None, cash_delta_cents=0, debt_delta_cents=0)

    system_account = ensure_system_account(db, world_id)
    if profit_cents > 0:
        profit_transaction = post_balanced_transfer(
            db,
            world_id=world_id,
            source_account=system_account,
            target_account=company_account,
            amount_cents=profit_cents,
            transaction_type="company_economy_profit",
            idempotency_key=idempotency_key,
            reference_type="economy_report",
            reference_id=reference_id,
            actor_profile_id=None,
            metadata={"company_id": company_id},
        )
        return CompanySettlement(
            transaction=profit_transaction,
            cash_delta_cents=profit_cents,
            debt_delta_cents=0,
        )

    return pay_company_expense(
        db,
        world_id=world_id,
        company_id=company_id,
        company_account=company_account,
        expense_cents=abs(profit_cents),
        transaction_type="company_economy_loss",
        idempotency_key=idempotency_key,
        reference_type="economy_report",
        reference_id=reference_id,
    )


def pay_company_expense(
    db: Session,
    *,
    world_id: str,
    company_id: str,
    company_account: Account,
    expense_cents: int,
    transaction_type: str,
    idempotency_key: str,
    reference_type: str,
    reference_id: str,
) -> CompanySettlement:
    if expense_cents <= 0:
        raise ValueError("company expense must be positive")
    existing = find_transaction(db, world_id, idempotency_key)
    if existing is not None:
        entries = list(
            db.scalars(
                select(AccountLedgerEntry).where(
                    AccountLedgerEntry.transaction_id == existing.id,
                    AccountLedgerEntry.account_id == company_account.id,
                )
            )
        )
        paid_cents = abs(entries[0].amount_cents) if entries else 0
        return CompanySettlement(
            transaction=existing,
            cash_delta_cents=-paid_cents,
            debt_delta_cents=expense_cents - paid_cents,
        )

    system_account = ensure_system_account(db, world_id)
    locked_account = db.scalar(
        select(Account).where(Account.id == company_account.id).with_for_update()
    )
    if locked_account is None:
        raise DomainError(409, "ledger.account_missing", "Company account does not exist")
    payable_cents = min(expense_cents, locked_account.balance_cents)
    expense_transaction = (
        post_balanced_transfer(
            db,
            world_id=world_id,
            source_account=locked_account,
            target_account=system_account,
            amount_cents=payable_cents,
            transaction_type=transaction_type,
            idempotency_key=idempotency_key,
            reference_type=reference_type,
            reference_id=reference_id,
            actor_profile_id=None,
            metadata={"company_id": company_id},
        )
        if payable_cents > 0
        else None
    )
    return CompanySettlement(
        transaction=expense_transaction,
        cash_delta_cents=-payable_cents,
        debt_delta_cents=expense_cents - payable_cents,
    )


def transaction_balance_cents(db: Session, transaction_id: str) -> int:
    total = db.scalar(
        select(func.coalesce(func.sum(AccountLedgerEntry.amount_cents), 0)).where(
            AccountLedgerEntry.transaction_id == transaction_id
        )
    )
    return int(total or 0)
