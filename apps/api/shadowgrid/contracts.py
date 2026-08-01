from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
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
from shadowgrid.finance import post_balanced_transfer
from shadowgrid.models import (
    Account,
    CommercialContract,
    Company,
    CompanyOwnership,
    ContractBid,
    ContractSettlement,
    ContractTender,
    District,
    PlayerProfile,
    RealtimeEvent,
    as_utc,
)
from shadowgrid.world_events import company_event_modifiers

_LOCK = threading.RLock()
_OPEN_CONTRACT_STATUSES = ("active",)


def _error(status: int, code: str, message: str) -> DomainError:
    return DomainError(status, code, message)


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
        raise _error(403, "contract.company_not_owned", "Active company ownership is required")
    return company


def _lock_world(db: Session, world_id: str) -> None:
    from shadowgrid.models import World

    if db.scalar(select(World).where(World.id == world_id).with_for_update()) is None:
        raise _error(404, "world.not_found", "World not found")


def reserved_capacity_units(
    db: Session,
    company_id: str,
    *,
    exclude_contract_id: str | None = None,
) -> int:
    statement = select(
        func.coalesce(func.sum(CommercialContract.reserved_capacity_units), 0)
    ).where(
        CommercialContract.provider_company_id == company_id,
        CommercialContract.status.in_(_OPEN_CONTRACT_STATUSES),
    )
    if exclude_contract_id is not None:
        statement = statement.where(CommercialContract.id != exclude_contract_id)
    return int(db.scalar(statement) or 0)


def available_capacity_units(db: Session, company: Company) -> int:
    return max(0, company.capacity - reserved_capacity_units(db, company.id))


def create_tender(
    db: Session,
    profile: PlayerProfile,
    *,
    issuer_company_id: str,
    contract_type: str,
    title: str,
    description: str,
    max_price_cents: int,
    duration_periods: int,
    capacity_units: int,
    min_reputation_bps: int,
    min_compliance_bps: int,
    submission_minutes: int,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> ContractTender:
    if contract_type not in {"supply", "service"}:
        raise _error(422, "contract.type_invalid", "Unknown contract type")
    if not 3 <= len(title.strip()) <= 140 or len(description.strip()) > 500:
        raise _error(422, "contract.terms_invalid", "Tender title or description is invalid")
    if max_price_cents <= 0 or capacity_units <= 0:
        raise _error(422, "contract.terms_invalid", "Price and capacity must be positive")
    if not 1 <= duration_periods <= settings.contract_tender_max_duration_periods:
        raise _error(422, "contract.duration_invalid", "Contract duration is outside its bounds")
    if not 5 <= submission_minutes <= 10_080:
        raise _error(422, "contract.deadline_invalid", "Submission window is outside its bounds")
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "contract.tender.create",
        )
        if previous is not None:
            existing = db.get(ContractTender, previous.resource_id)
            if existing is not None:
                return existing
        company = _owned_company(db, profile, issuer_company_id, lock=True)
        _lock_world(db, profile.world_id)
        now = as_utc(at or datetime.now(UTC))
        tender = ContractTender(
            world_id=profile.world_id,
            issuer_company_id=company.id,
            created_by_profile_id=profile.id,
            contract_type=contract_type,
            title=title.strip(),
            description=description.strip(),
            max_price_cents=max_price_cents,
            duration_periods=duration_periods,
            capacity_units=capacity_units,
            min_reputation_bps=min_reputation_bps,
            min_compliance_bps=min_compliance_bps,
            idempotency_key=idempotency_key,
            submission_ends_at=now + timedelta(minutes=submission_minutes),
            created_at=now,
        )
        db.add(tender)
        db.flush()
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "contract.tender.create",
            tender.id,
            {"tender_id": tender.id},
        )
        audit(
            db,
            profile.user_id,
            "contract.tender.created",
            "contract_tender",
            tender.id,
            request_id,
            {"issuer_company_id": company.id},
        )
        db.commit()
        db.refresh(tender)
        return tender


def _bid_score(
    db: Session,
    tender: ContractTender,
    bidder: Company,
    price_cents: int,
    at: datetime,
) -> tuple[int, dict[str, int]]:
    district = db.get(District, bidder.district_id)
    if district is None:
        raise RuntimeError("bidder district is missing")
    event_bonus = company_event_modifiers(
        db,
        bidder,
        district,
        at,
    ).contract_probability_delta_bps
    price_advantage_bps = (
        max(0, tender.max_price_cents - price_cents) * 10_000 // tender.max_price_cents
    )
    breakdown = {
        "price_advantage_bps": price_advantage_bps,
        "reputation_component": bidder.reputation_bps // 2,
        "compliance_component": bidder.compliance_bps // 4,
        "quality_component": bidder.quality // 4,
        "event_contract_delta_bps": event_bonus,
    }
    return max(0, min(30_000, sum(breakdown.values()))), breakdown


def submit_bid(
    db: Session,
    profile: PlayerProfile,
    *,
    tender_id: str,
    bidder_company_id: str,
    price_cents: int,
    idempotency_key: str,
    request_id: str,
    at: datetime | None = None,
) -> ContractBid:
    if price_cents <= 0:
        raise _error(422, "contract.price_invalid", "Bid price must be positive")
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "contract.bid.submit",
        )
        if previous is not None:
            existing = db.get(ContractBid, previous.resource_id)
            if existing is not None:
                return existing
        tender = db.scalar(
            select(ContractTender).where(ContractTender.id == tender_id).with_for_update()
        )
        if tender is None or tender.world_id != profile.world_id:
            raise _error(404, "contract.tender_not_found", "Tender not found")
        now = as_utc(at or datetime.now(UTC))
        if tender.status != "open" or as_utc(tender.submission_ends_at) <= now:
            raise _error(409, "contract.tender_closed", "Tender is no longer open")
        bidder = _owned_company(db, profile, bidder_company_id, lock=True)
        if bidder.id == tender.issuer_company_id:
            raise _error(409, "contract.same_company", "Issuer cannot bid on its own tender")
        if price_cents > tender.max_price_cents:
            raise _error(422, "contract.price_above_limit", "Bid exceeds the tender price limit")
        if bidder.reputation_bps < tender.min_reputation_bps:
            raise _error(409, "contract.reputation_too_low", "Company reputation is too low")
        if bidder.compliance_bps < tender.min_compliance_bps:
            raise _error(409, "contract.compliance_too_low", "Company compliance is too low")
        if available_capacity_units(db, bidder) < tender.capacity_units:
            raise _error(409, "contract.capacity_unavailable", "Company capacity is unavailable")
        score, breakdown = _bid_score(db, tender, bidder, price_cents, now)
        bid = ContractBid(
            tender_id=tender.id,
            bidder_company_id=bidder.id,
            submitted_by_profile_id=profile.id,
            price_cents=price_cents,
            capacity_units=tender.capacity_units,
            score_points=score,
            score_breakdown_json=breakdown,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        db.add(bid)
        db.flush()
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "contract.bid.submit",
            bid.id,
            {"bid_id": bid.id},
        )
        audit(
            db,
            profile.user_id,
            "contract.bid.submitted",
            "contract_bid",
            bid.id,
            request_id,
            {"tender_id": tender.id, "score_points": score},
        )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise _error(409, "contract.bid_exists", "Company already submitted a bid") from exc
        db.refresh(bid)
        return bid


def award_bid(
    db: Session,
    profile: PlayerProfile,
    *,
    tender_id: str,
    bid_id: str,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> CommercialContract:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "contract.tender.award",
        )
        if previous is not None:
            existing = db.get(CommercialContract, previous.resource_id)
            if existing is not None:
                return existing
        tender = db.scalar(
            select(ContractTender).where(ContractTender.id == tender_id).with_for_update()
        )
        if tender is None or tender.world_id != profile.world_id:
            raise _error(404, "contract.tender_not_found", "Tender not found")
        issuer = _owned_company(db, profile, tender.issuer_company_id, lock=True)
        now = as_utc(at or datetime.now(UTC))
        if tender.status != "open" or as_utc(tender.submission_ends_at) <= now:
            existing = db.scalar(
                select(CommercialContract).where(CommercialContract.tender_id == tender.id)
            )
            if existing is not None:
                return existing
            raise _error(409, "contract.tender_closed", "Tender is no longer open")
        bid = db.scalar(
            select(ContractBid)
            .where(ContractBid.id == bid_id, ContractBid.tender_id == tender.id)
            .with_for_update()
        )
        if bid is None or bid.status != "submitted":
            raise _error(404, "contract.bid_not_found", "Submitted bid not found")
        provider = db.scalar(
            select(Company)
            .where(
                Company.id == bid.bidder_company_id,
                Company.world_id == profile.world_id,
                Company.status != "archived",
            )
            .with_for_update()
        )
        if provider is None:
            raise _error(409, "contract.provider_unavailable", "Provider is unavailable")
        if available_capacity_units(db, provider) < bid.capacity_units:
            raise _error(409, "contract.capacity_unavailable", "Provider capacity is unavailable")
        _lock_world(db, profile.world_id)
        interval = timedelta(minutes=settings.contract_settlement_interval_minutes)
        contract = CommercialContract(
            world_id=profile.world_id,
            tender_id=tender.id,
            bid_id=bid.id,
            issuer_company_id=issuer.id,
            provider_company_id=provider.id,
            contract_type=tender.contract_type,
            title=tender.title,
            price_cents_per_period=bid.price_cents,
            duration_periods=tender.duration_periods,
            reserved_capacity_units=bid.capacity_units,
            reputation_reward_bps=settings.contract_reputation_reward_bps,
            idempotency_key=idempotency_key,
            starts_at=now,
            ends_at=now + interval * tender.duration_periods,
            next_settlement_at=now + interval,
            created_at=now,
        )
        db.add(contract)
        db.flush()
        tender.status = "awarded"
        tender.awarded_at = now
        for candidate in db.scalars(
            select(ContractBid).where(ContractBid.tender_id == tender.id).with_for_update()
        ):
            candidate.status = "won" if candidate.id == bid.id else "lost"
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "contract.tender.award",
            contract.id,
            {"contract_id": contract.id},
        )
        audit(
            db,
            profile.user_id,
            "contract.tender.awarded",
            "commercial_contract",
            contract.id,
            request_id,
            {
                "tender_id": tender.id,
                "bid_id": bid.id,
                "provider_company_id": provider.id,
            },
        )
        db.add(
            RealtimeEvent(
                world_id=contract.world_id,
                event_type="contract.awarded",
                payload_json={
                    "contract_id": contract.id,
                    "issuer_company_id": issuer.id,
                    "provider_company_id": provider.id,
                    "status": contract.status,
                },
                created_at=now,
                expires_at=now + timedelta(days=7),
            )
        )
        db.commit()
        db.refresh(contract)
        return contract


def _settle_period(
    db: Session,
    contract: CommercialContract,
    *,
    at: datetime,
    settings: Settings,
) -> ContractSettlement:
    period_number = contract.periods_settled + 1
    existing = db.scalar(
        select(ContractSettlement).where(
            ContractSettlement.contract_id == contract.id,
            ContractSettlement.period_number == period_number,
        )
    )
    if existing is not None:
        return existing
    accounts = list(
        db.scalars(
            select(Account)
            .where(
                Account.owner_type == "company",
                Account.owner_id.in_((contract.issuer_company_id, contract.provider_company_id)),
            )
            .order_by(Account.id)
            .with_for_update()
        )
    )
    by_owner = {account.owner_id: account for account in accounts}
    issuer_account = by_owner.get(contract.issuer_company_id)
    provider_account = by_owner.get(contract.provider_company_id)
    if issuer_account is None or provider_account is None:
        raise RuntimeError("contract company account is missing")
    input_snapshot = {
        "issuer_balance_cents": issuer_account.balance_cents,
        "issuer_reserved_cents": issuer_account.reserved_cents,
        "price_cents_per_period": contract.price_cents_per_period,
        "period_number": period_number,
    }
    available_cents = issuer_account.balance_cents - issuer_account.reserved_cents
    if available_cents < contract.price_cents_per_period:
        settlement = ContractSettlement(
            contract_id=contract.id,
            period_number=period_number,
            amount_cents=contract.price_cents_per_period,
            status="defaulted",
            input_snapshot_json=input_snapshot,
            settled_at=at,
        )
        contract.status = "breached"
        contract.breached_at = at
        contract.breach_reason = "payment_default"
        issuer = db.get(Company, contract.issuer_company_id)
        if issuer is None:
            raise RuntimeError("contract issuer company is missing")
        issuer.reputation_bps = max(
            0,
            issuer.reputation_bps - settings.contract_breach_reputation_penalty_bps,
        )
        issuer.investigation_pressure_bps = min(
            10_000,
            issuer.investigation_pressure_bps + settings.contract_breach_investigation_penalty_bps,
        )
        issuer.version += 1
        db.add(snapshot_company(issuer, reason="contract_breach", reference_id=contract.id))
    else:
        transaction = post_balanced_transfer(
            db,
            world_id=contract.world_id,
            source_account=issuer_account,
            target_account=provider_account,
            amount_cents=contract.price_cents_per_period,
            transaction_type="contract_settlement",
            idempotency_key=f"contract:{contract.id}:period:{period_number}",
            reference_type="commercial_contract",
            reference_id=contract.id,
            actor_profile_id=None,
            metadata={"period_number": period_number},
        )
        settlement = ContractSettlement(
            contract_id=contract.id,
            period_number=period_number,
            amount_cents=contract.price_cents_per_period,
            status="paid",
            transaction_id=transaction.id,
            input_snapshot_json=input_snapshot,
            settled_at=at,
        )
        contract.periods_settled = period_number
        if period_number >= contract.duration_periods:
            contract.status = "completed"
            contract.completed_at = at
            for company_id in (
                contract.issuer_company_id,
                contract.provider_company_id,
            ):
                company = db.get(Company, company_id)
                if company is None:
                    raise RuntimeError("contract party company is missing")
                company.reputation_bps = min(
                    10_000,
                    company.reputation_bps + contract.reputation_reward_bps,
                )
                company.version += 1
                db.add(
                    snapshot_company(
                        company,
                        reason="contract_completed",
                        reference_id=contract.id,
                    )
                )
        else:
            contract.next_settlement_at = contract.next_settlement_at + timedelta(
                minutes=settings.contract_settlement_interval_minutes
            )
    db.add(settlement)
    db.flush()
    audit(
        db,
        None,
        f"contract.settlement.{settlement.status}",
        "contract_settlement",
        settlement.id,
        f"contract-scheduler:{contract.id}:{period_number}",
        input_snapshot,
    )
    if contract.status == "breached":
        warning_company = db.get(Company, contract.issuer_company_id)
        if warning_company is None:
            raise RuntimeError("contract issuer company is missing")
        create_company_warning(
            db,
            company=warning_company,
            warning_type="contract_payment_default",
            title=f"Contract warning for {warning_company.name}",
            body="A scheduled commercial settlement entered abstract breach.",
            dedupe_key=f"company-warning:contract:{contract.id}:{period_number}",
            metadata={
                "contract_id": contract.id,
                "period_number": period_number,
            },
        )
    db.add(
        RealtimeEvent(
            world_id=contract.world_id,
            event_type=(
                "contract.completed"
                if contract.status == "completed"
                else ("contract.breached" if contract.status == "breached" else "contract.settled")
            ),
            payload_json={
                "contract_id": contract.id,
                "status": contract.status,
                "period_number": period_number,
                "settlement_status": settlement.status,
            },
            created_at=at,
            expires_at=at + timedelta(days=7),
        )
    )
    return settlement


def advance_contracts(
    db: Session,
    settings: Settings,
    *,
    at: datetime | None = None,
) -> dict[str, int]:
    now = as_utc(at or datetime.now(UTC))
    with _LOCK:
        expired = 0
        for tender in db.scalars(
            select(ContractTender)
            .where(
                ContractTender.status == "open",
                ContractTender.submission_ends_at <= now,
            )
            .order_by(ContractTender.submission_ends_at, ContractTender.id)
            .with_for_update()
        ):
            tender.status = "expired"
            audit(
                db,
                None,
                "contract.tender_expired",
                "contract_tender",
                tender.id,
                f"contract-tender-expiry:{tender.id}",
                {
                    "world_id": tender.world_id,
                    "issuer_company_id": tender.issuer_company_id,
                    "submission_ends_at": tender.submission_ends_at.isoformat(),
                },
            )
            db.add(
                RealtimeEvent(
                    world_id=tender.world_id,
                    event_type="contract.tender_expired",
                    payload_json={"tender_id": tender.id},
                    created_at=now,
                    expires_at=now + timedelta(days=7),
                )
            )
            expired += 1
        settled = 0
        breached = 0
        completed = 0
        contracts = list(
            db.scalars(
                select(CommercialContract)
                .where(
                    CommercialContract.status == "active",
                    CommercialContract.next_settlement_at <= now,
                )
                .order_by(
                    CommercialContract.next_settlement_at,
                    CommercialContract.id,
                )
                .with_for_update()
            )
        )
        for contract in contracts:
            while contract.status == "active" and as_utc(contract.next_settlement_at) <= now:
                settlement = _settle_period(
                    db,
                    contract,
                    at=as_utc(contract.next_settlement_at),
                    settings=settings,
                )
                settled += int(settlement.status == "paid")
                breached += int(settlement.status == "defaulted")
                completed += int(contract.status == "completed")
        db.commit()
        return {
            "tenders_expired": expired,
            "periods_settled": settled,
            "contracts_breached": breached,
            "contracts_completed": completed,
        }


def list_tenders(db: Session, profile: PlayerProfile) -> list[ContractTender]:
    return list(
        db.scalars(
            select(ContractTender)
            .where(ContractTender.world_id == profile.world_id)
            .order_by(ContractTender.created_at.desc())
            .limit(200)
        )
    )


def list_visible_bids(
    db: Session,
    profile: PlayerProfile,
    tender_id: str,
) -> list[ContractBid]:
    tender = db.get(ContractTender, tender_id)
    if tender is None or tender.world_id != profile.world_id:
        raise _error(404, "contract.tender_not_found", "Tender not found")
    issuer_owned = (
        db.scalar(
            select(CompanyOwnership.id).where(
                CompanyOwnership.company_id == tender.issuer_company_id,
                CompanyOwnership.owner_profile_id == profile.id,
                CompanyOwnership.ownership_bps > 0,
            )
        )
        is not None
    )
    statement = select(ContractBid).where(ContractBid.tender_id == tender.id)
    if not issuer_owned:
        statement = statement.where(ContractBid.submitted_by_profile_id == profile.id)
    return list(db.scalars(statement.order_by(ContractBid.score_points.desc(), ContractBid.id)))


def list_profile_contracts(
    db: Session,
    profile: PlayerProfile,
) -> list[CommercialContract]:
    owned_ids = select(CompanyOwnership.company_id).where(
        CompanyOwnership.owner_profile_id == profile.id,
        CompanyOwnership.ownership_bps > 0,
    )
    return list(
        db.scalars(
            select(CommercialContract)
            .where(
                CommercialContract.world_id == profile.world_id,
                or_(
                    CommercialContract.issuer_company_id.in_(owned_ids),
                    CommercialContract.provider_company_id.in_(owned_ids),
                ),
            )
            .order_by(CommercialContract.created_at.desc())
        )
    )


def list_contract_settlements(
    db: Session,
    profile: PlayerProfile,
    contract_id: str,
) -> list[ContractSettlement]:
    visible_ids = {item.id for item in list_profile_contracts(db, profile)}
    if contract_id not in visible_ids:
        raise _error(404, "contract.not_found", "Contract not found")
    return list(
        db.scalars(
            select(ContractSettlement)
            .where(ContractSettlement.contract_id == contract_id)
            .order_by(ContractSettlement.period_number)
        )
    )
