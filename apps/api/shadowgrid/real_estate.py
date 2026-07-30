from __future__ import annotations

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
    ensure_system_account,
    post_balanced_transfer,
    transfer_account_to_profile_cash,
    transfer_profile_cash_between_profiles,
    transfer_profile_cash_to_account,
)
from shadowgrid.models import (
    Account,
    CartelDistrictInfluence,
    Company,
    CompanyOwnership,
    District,
    PlayerProfile,
    PropertyImprovement,
    PropertyLease,
    PropertyLeasePayment,
    PropertyTransfer,
    RealEstateDistrictIndex,
    RealEstateIndexSnapshot,
    RealEstateProperty,
    RealtimeEvent,
    User,
    as_utc,
)
from shadowgrid.world_events import market_event_modifiers

_LOCK = threading.RLock()
_PROPERTY_TEMPLATES: tuple[tuple[str, str, int, int], ...] = (
    ("land", "Development parcel", 100, 1_000_000),
    ("building", "Mixed-use building", 80, 2_500_000),
    ("commercial_space", "Commercial floor", 50, 2_000_000),
    ("headquarters", "Headquarters property", 60, 3_000_000),
)


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
        raise _error(
            403,
            "property.company_not_owned",
            "Active company ownership is required",
        )
    return company


def _cartel_control_points(db: Session, district_id: str) -> int:
    totals = [
        int(total)
        for (total,) in db.execute(
            select(func.sum(CartelDistrictInfluence.points))
            .where(CartelDistrictInfluence.district_id == district_id)
            .group_by(CartelDistrictInfluence.organization_id)
        )
    ]
    return max(totals, default=0)


def _index_values(
    db: Session,
    district: District,
    *,
    at: datetime,
) -> tuple[int, int, int, int, dict[str, int]]:
    if district.city_id is None:
        raise RuntimeError("real-estate district has no city")
    cartel_points = _cartel_control_points(db, district.id)
    event = market_event_modifiers(
        db,
        world_id=district.world_id,
        city_id=district.city_id,
        industry="real_estate",
        at=at,
    )
    base_price_index = (
        5_000
        + district.property_value * 35
        + district.safety * 12
        + district.digital_infrastructure * 15
        + district.economic_activity * 18
        + min(2_000, cartel_points * 5)
    )
    event_multiplier = event.real_estate_cost_multiplier_bps
    price_index = max(
        2_500,
        min(30_000, base_price_index * event_multiplier // 10_000),
    )
    demand_bps = max(
        0,
        min(
            20_000,
            5_000
            + district.prosperity * 25
            + district.employment * 15
            + district.economic_activity * 20,
        ),
    )
    rent_index = max(
        2_500,
        min(30_000, price_index * max(5_000, demand_bps) // 10_000),
    )
    inputs = {
        "property_value": district.property_value,
        "prosperity": district.prosperity,
        "employment": district.employment,
        "safety": district.safety,
        "digital_infrastructure": district.digital_infrastructure,
        "economic_activity": district.economic_activity,
        "cartel_control_points": cartel_points,
        "event_multiplier_bps": event_multiplier,
        "base_price_index_bps": base_price_index,
        "demand_bps": demand_bps,
    }
    return price_index, rent_index, demand_bps, cartel_points, inputs


def refresh_real_estate_indices(
    db: Session,
    *,
    world_id: str,
    at: datetime | None = None,
) -> int:
    now = as_utc(at or datetime.now(UTC))
    period_key = now.strftime("%Y-%m-%d")
    refreshed = 0
    districts = list(
        db.scalars(
            select(District)
            .where(District.world_id == world_id, District.city_id.is_not(None))
            .order_by(District.id)
        )
    )
    for district in districts:
        index = db.scalar(
            select(RealEstateDistrictIndex)
            .where(RealEstateDistrictIndex.district_id == district.id)
            .with_for_update()
        )
        if index is None:
            if district.city_id is None:
                continue
            index = RealEstateDistrictIndex(
                world_id=world_id,
                city_id=district.city_id,
                district_id=district.id,
                safety_score=district.safety,
                infrastructure_score=district.digital_infrastructure,
                economic_score=district.economic_activity,
                updated_at=now,
            )
            db.add(index)
            db.flush()
        existing = db.scalar(
            select(RealEstateIndexSnapshot).where(
                RealEstateIndexSnapshot.district_index_id == index.id,
                RealEstateIndexSnapshot.period_key == period_key,
            )
        )
        if existing is not None:
            continue
        price, rent, demand, cartel_points, inputs = _index_values(
            db,
            district,
            at=now,
        )
        index.price_index_bps = price
        index.rent_index_bps = rent
        index.demand_bps = demand
        index.safety_score = district.safety
        index.infrastructure_score = district.digital_infrastructure
        index.economic_score = district.economic_activity
        index.cartel_control_points = cartel_points
        index.event_multiplier_bps = inputs["event_multiplier_bps"]
        index.version += 1
        index.updated_at = now
        db.add(
            RealEstateIndexSnapshot(
                district_index_id=index.id,
                period_key=period_key,
                price_index_bps=price,
                rent_index_bps=rent,
                inputs_json=inputs,
                captured_at=now,
            )
        )
        refreshed += 1
    db.flush()
    return refreshed


def seed_real_estate(
    db: Session,
    world_id: str,
    *,
    at: datetime | None = None,
) -> int:
    now = as_utc(at or datetime.now(UTC))
    refresh_real_estate_indices(db, world_id=world_id, at=now)
    created = 0
    districts = list(
        db.scalars(
            select(District)
            .where(District.world_id == world_id, District.city_id.is_not(None))
            .order_by(District.slug)
        )
    )
    for district in districts:
        if district.city_id is None:
            continue
        for property_type, title, area_units, base_value_cents in _PROPERTY_TEMPLATES:
            code = f"{district.slug}-{property_type}-01"
            existing = db.scalar(
                select(RealEstateProperty).where(
                    RealEstateProperty.world_id == world_id,
                    RealEstateProperty.property_code == code,
                )
            )
            if existing is not None:
                continue
            db.add(
                RealEstateProperty(
                    world_id=world_id,
                    city_id=district.city_id,
                    district_id=district.id,
                    property_code=code,
                    property_type=property_type,
                    name=f"{district.name} {title}",
                    area_units=area_units,
                    base_value_cents=base_value_cents,
                    status="available",
                    listing_type="sale",
                    asking_price_cents=base_value_cents,
                    headquarters_level=0,
                    created_at=now,
                    updated_at=now,
                )
            )
            created += 1
    db.flush()
    return created


def _district_index(db: Session, district_id: str) -> RealEstateDistrictIndex:
    index = db.scalar(
        select(RealEstateDistrictIndex).where(RealEstateDistrictIndex.district_id == district_id)
    )
    if index is None:
        raise RuntimeError("real-estate district index is missing")
    return index


def effective_sale_price_cents(
    db: Session,
    property_: RealEstateProperty,
) -> int:
    index = _district_index(db, property_.district_id)
    return max(1, property_.asking_price_cents * index.price_index_bps // 10_000)


def effective_rent_cents(
    db: Session,
    property_: RealEstateProperty,
) -> int:
    index = _district_index(db, property_.district_id)
    return max(1, property_.rent_cents_per_period * index.rent_index_bps // 10_000)


def buy_property(
    db: Session,
    profile: PlayerProfile,
    *,
    property_id: str,
    idempotency_key: str,
    request_id: str,
    at: datetime | None = None,
) -> PropertyTransfer:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.purchase",
        )
        if previous is not None:
            existing = db.get(PropertyTransfer, previous.resource_id)
            if existing is not None:
                return existing
        property_ = db.scalar(
            select(RealEstateProperty).where(RealEstateProperty.id == property_id).with_for_update()
        )
        if property_ is None or property_.world_id != profile.world_id:
            raise _error(404, "property.not_found", "Property not found")
        if property_.listing_type != "sale" or property_.status not in (
            "available",
            "owned",
        ):
            raise _error(409, "property.not_for_sale", "Property is not for sale")
        if property_.owner_profile_id == profile.id:
            raise _error(409, "property.self_purchase", "Cannot purchase your own property")
        if property_.company_use_id is not None:
            raise _error(409, "property.in_use", "Property is assigned to a company")
        seller_id = property_.owner_profile_id
        price_cents = effective_sale_price_cents(db, property_)
        index = _district_index(db, property_.district_id)
        if seller_id is None:
            transaction = transfer_profile_cash_to_account(
                db,
                profile,
                ensure_system_account(db, profile.world_id),
                amount_cents=price_cents,
                transaction_type="property_system_purchase",
                idempotency_key=f"property-purchase:{profile.id}:{idempotency_key}",
                reference_type="real_estate_property",
                reference_id=property_.id,
            )
            transfer_type = "system_sale"
        else:
            seller = db.get(PlayerProfile, seller_id)
            if seller is None:
                raise RuntimeError("property seller profile is missing")
            transaction = transfer_profile_cash_between_profiles(
                db,
                profile,
                seller,
                amount_cents=price_cents,
                transaction_type="property_resale",
                idempotency_key=f"property-purchase:{profile.id}:{idempotency_key}",
                reference_type="real_estate_property",
                reference_id=property_.id,
            )
            transfer_type = "resale"
        now = as_utc(at or datetime.now(UTC))
        transfer = PropertyTransfer(
            property_id=property_.id,
            seller_profile_id=seller_id,
            buyer_profile_id=profile.id,
            price_cents=price_cents,
            price_index_bps=index.price_index_bps,
            transfer_type=transfer_type,
            transaction_id=transaction.id,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        db.add(transfer)
        db.flush()
        property_.owner_profile_id = profile.id
        property_.status = "owned"
        property_.listing_type = None
        property_.asking_price_cents = price_cents
        property_.version += 1
        property_.updated_at = now
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.purchase",
            transfer.id,
            {"transfer_id": transfer.id},
        )
        audit(
            db,
            profile.user_id,
            "property.purchased",
            "real_estate_property",
            property_.id,
            request_id,
            {
                "price_cents": price_cents,
                "price_index_bps": index.price_index_bps,
                "transaction_id": transaction.id,
            },
        )
        db.add(
            RealtimeEvent(
                world_id=property_.world_id,
                event_type="property.purchased",
                payload_json={"property_id": property_.id, "buyer_profile_id": profile.id},
                created_at=now,
                expires_at=now + timedelta(days=7),
            )
        )
        db.commit()
        db.refresh(transfer)
        return transfer


def list_owned_property(
    db: Session,
    profile: PlayerProfile,
    *,
    property_id: str,
    lock: bool = False,
) -> RealEstateProperty:
    statement = select(RealEstateProperty).where(
        RealEstateProperty.id == property_id,
        RealEstateProperty.world_id == profile.world_id,
        RealEstateProperty.owner_profile_id == profile.id,
        RealEstateProperty.status.in_(("owned", "leased")),
    )
    if lock:
        statement = statement.with_for_update()
    property_ = db.scalar(statement)
    if property_ is None:
        raise _error(403, "property.not_owned", "Property ownership is required")
    return property_


def list_property_for_sale(
    db: Session,
    profile: PlayerProfile,
    *,
    property_id: str,
    asking_price_cents: int,
    idempotency_key: str,
    request_id: str,
) -> RealEstateProperty:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.list_sale",
        )
        if previous is not None:
            existing = db.get(RealEstateProperty, previous.resource_id)
            if existing is not None:
                return existing
        property_ = list_owned_property(db, profile, property_id=property_id, lock=True)
        if property_.status != "owned" or property_.company_use_id is not None:
            raise _error(409, "property.in_use", "Property must be unused before sale")
        property_.listing_type = "sale"
        property_.asking_price_cents = asking_price_cents
        property_.version += 1
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.list_sale",
            property_.id,
            {"property_id": property_.id},
        )
        audit(
            db,
            profile.user_id,
            "property.listed_for_sale",
            "real_estate_property",
            property_.id,
            request_id,
            {"asking_price_cents": asking_price_cents},
        )
        db.commit()
        db.refresh(property_)
        return property_


def list_property_for_rent(
    db: Session,
    profile: PlayerProfile,
    *,
    property_id: str,
    rent_cents_per_period: int,
    idempotency_key: str,
    request_id: str,
) -> RealEstateProperty:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.list_rent",
        )
        if previous is not None:
            existing = db.get(RealEstateProperty, previous.resource_id)
            if existing is not None:
                return existing
        property_ = list_owned_property(db, profile, property_id=property_id, lock=True)
        if property_.status != "owned" or property_.company_use_id is not None:
            raise _error(409, "property.in_use", "Property must be unused before rent listing")
        property_.listing_type = "rent"
        property_.rent_cents_per_period = rent_cents_per_period
        property_.version += 1
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.list_rent",
            property_.id,
            {"property_id": property_.id},
        )
        audit(
            db,
            profile.user_id,
            "property.listed_for_rent",
            "real_estate_property",
            property_.id,
            request_id,
            {"rent_cents_per_period": rent_cents_per_period},
        )
        db.commit()
        db.refresh(property_)
        return property_


def lease_property(
    db: Session,
    profile: PlayerProfile,
    *,
    property_id: str,
    tenant_company_id: str,
    term_periods: int,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> PropertyLease:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.lease.create",
        )
        if previous is not None:
            existing = db.get(PropertyLease, previous.resource_id)
            if existing is not None:
                return existing
        if term_periods > settings.property_max_lease_periods:
            raise _error(422, "property.lease_too_long", "Lease term exceeds configured limit")
        property_ = db.scalar(
            select(RealEstateProperty).where(RealEstateProperty.id == property_id).with_for_update()
        )
        if property_ is None or property_.world_id != profile.world_id:
            raise _error(404, "property.not_found", "Property not found")
        if (
            property_.status != "owned"
            or property_.listing_type != "rent"
            or property_.owner_profile_id is None
        ):
            raise _error(409, "property.not_for_rent", "Property is not for rent")
        tenant = _owned_company(db, profile, tenant_company_id, lock=True)
        landlord = db.get(PlayerProfile, property_.owner_profile_id)
        if landlord is None:
            raise RuntimeError("property landlord is missing")
        rent_cents = effective_rent_cents(db, property_)
        now = as_utc(at or datetime.now(UTC))
        transaction = transfer_account_to_profile_cash(
            db,
            tenant.account,
            landlord,
            amount_cents=rent_cents,
            transaction_type="property_rent",
            idempotency_key=f"property-lease:{idempotency_key}:period:1",
            reference_type="real_estate_property",
            reference_id=property_.id,
        )
        lease = PropertyLease(
            world_id=profile.world_id,
            property_id=property_.id,
            landlord_profile_id=landlord.id,
            tenant_company_id=tenant.id,
            rent_cents_per_period=rent_cents,
            term_periods=term_periods,
            idempotency_key=idempotency_key,
            starts_at=now,
            ends_at=now
            + timedelta(minutes=settings.property_lease_interval_minutes * term_periods),
            next_payment_at=now + timedelta(minutes=settings.property_lease_interval_minutes),
            created_at=now,
        )
        db.add(lease)
        db.flush()
        db.add(
            PropertyLeasePayment(
                lease_id=lease.id,
                period_number=1,
                amount_cents=rent_cents,
                status="paid",
                transaction_id=transaction.id,
                input_snapshot_json={
                    "rent_index_bps": _district_index(db, property_.district_id).rent_index_bps
                },
                paid_at=now,
            )
        )
        property_.status = "leased"
        property_.listing_type = None
        property_.company_use_id = tenant.id
        property_.version += 1
        tenant.version += 1
        db.add(snapshot_company(tenant, reason="property_lease_started", reference_id=lease.id))
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.lease.create",
            lease.id,
            {"lease_id": lease.id},
        )
        audit(
            db,
            profile.user_id,
            "property.lease.started",
            "property_lease",
            lease.id,
            request_id,
            {"rent_cents_per_period": rent_cents, "transaction_id": transaction.id},
        )
        db.commit()
        db.refresh(lease)
        return lease


def assign_property_to_company(
    db: Session,
    profile: PlayerProfile,
    *,
    property_id: str,
    company_id: str,
    idempotency_key: str,
    request_id: str,
) -> RealEstateProperty:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.assign",
        )
        if previous is not None:
            existing = db.get(RealEstateProperty, previous.resource_id)
            if existing is not None:
                return existing
        property_ = list_owned_property(db, profile, property_id=property_id, lock=True)
        company = _owned_company(db, profile, company_id, lock=True)
        if property_.status != "owned" or property_.listing_type is not None:
            raise _error(409, "property.unavailable", "Property must be unlisted and unused")
        if property_.company_use_id is not None:
            raise _error(409, "property.in_use", "Property is already assigned")
        property_.company_use_id = company.id
        property_.version += 1
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.assign",
            property_.id,
            {"property_id": property_.id},
        )
        audit(
            db,
            profile.user_id,
            "property.assigned",
            "real_estate_property",
            property_.id,
            request_id,
            {"company_id": company.id},
        )
        db.commit()
        db.refresh(property_)
        return property_


def unassign_property(
    db: Session,
    profile: PlayerProfile,
    *,
    property_id: str,
    idempotency_key: str,
    request_id: str,
) -> RealEstateProperty:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.unassign",
        )
        if previous is not None:
            existing = db.get(RealEstateProperty, previous.resource_id)
            if existing is not None:
                return existing
        property_ = list_owned_property(db, profile, property_id=property_id, lock=True)
        if property_.status != "owned":
            raise _error(409, "property.leased", "Leased property cannot be unassigned")
        property_.company_use_id = None
        property_.version += 1
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.unassign",
            property_.id,
            {"property_id": property_.id},
        )
        audit(
            db,
            profile.user_id,
            "property.unassigned",
            "real_estate_property",
            property_.id,
            request_id,
        )
        db.commit()
        db.refresh(property_)
        return property_


def upgrade_headquarters(
    db: Session,
    profile: PlayerProfile,
    *,
    property_id: str,
    idempotency_key: str,
    request_id: str,
    settings: Settings,
    at: datetime | None = None,
) -> PropertyImprovement:
    with _LOCK:
        previous = get_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.headquarters.upgrade",
        )
        if previous is not None:
            existing = db.get(PropertyImprovement, previous.resource_id)
            if existing is not None:
                return existing
        property_ = list_owned_property(db, profile, property_id=property_id, lock=True)
        if property_.property_type != "headquarters" or property_.company_use_id is None:
            raise _error(
                409,
                "property.not_active_headquarters",
                "Assigned headquarters property is required",
            )
        if property_.headquarters_level >= 10:
            raise _error(409, "property.headquarters_max", "Headquarters is at maximum level")
        company = _owned_company(db, profile, property_.company_use_id, lock=True)
        index = _district_index(db, property_.district_id)
        level_after = property_.headquarters_level + 1
        cost_cents = max(
            1,
            settings.headquarters_upgrade_base_cost_cents
            * level_after
            * index.price_index_bps
            // 10_000,
        )
        transaction = post_balanced_transfer(
            db,
            world_id=profile.world_id,
            source_account=company.account,
            target_account=ensure_system_account(db, profile.world_id),
            amount_cents=cost_cents,
            transaction_type="headquarters_upgrade",
            idempotency_key=f"headquarters-upgrade:{property_.id}:{level_after}",
            reference_type="real_estate_property",
            reference_id=property_.id,
            actor_profile_id=profile.id,
        )
        now = as_utc(at or datetime.now(UTC))
        improvement = PropertyImprovement(
            property_id=property_.id,
            company_id=company.id,
            improvement_type="headquarters_upgrade",
            level_after=level_after,
            cost_cents=cost_cents,
            transaction_id=transaction.id,
            idempotency_key=idempotency_key,
            created_at=now,
        )
        db.add(improvement)
        db.flush()
        property_.headquarters_level = level_after
        property_.improvement_value_cents += cost_cents
        property_.version += 1
        company.version += 1
        db.add(
            snapshot_company(company, reason="headquarters_upgrade", reference_id=improvement.id)
        )
        remember_idempotent(
            db,
            profile.user_id,
            idempotency_key,
            "property.headquarters.upgrade",
            improvement.id,
            {"improvement_id": improvement.id},
        )
        audit(
            db,
            profile.user_id,
            "property.headquarters_upgraded",
            "real_estate_property",
            property_.id,
            request_id,
            {"level_after": level_after, "cost_cents": cost_cents},
        )
        db.commit()
        db.refresh(improvement)
        return improvement


def _settle_lease_period(
    db: Session,
    lease: PropertyLease,
    *,
    at: datetime,
    settings: Settings,
) -> PropertyLeasePayment:
    period_number = lease.periods_paid + 1
    existing = db.scalar(
        select(PropertyLeasePayment).where(
            PropertyLeasePayment.lease_id == lease.id,
            PropertyLeasePayment.period_number == period_number,
        )
    )
    if existing is not None:
        return existing
    property_ = db.scalar(
        select(RealEstateProperty)
        .where(RealEstateProperty.id == lease.property_id)
        .with_for_update()
    )
    company = db.scalar(
        select(Company).where(Company.id == lease.tenant_company_id).with_for_update()
    )
    landlord = db.get(PlayerProfile, lease.landlord_profile_id)
    if property_ is None or company is None or landlord is None:
        raise RuntimeError("property lease party is missing")
    account = db.scalar(
        select(Account)
        .where(Account.owner_type == "company", Account.owner_id == company.id)
        .with_for_update()
    )
    if account is None:
        raise RuntimeError("property tenant account is missing")
    input_snapshot = {
        "company_balance_cents": account.balance_cents,
        "company_reserved_cents": account.reserved_cents,
        "rent_cents_per_period": lease.rent_cents_per_period,
        "period_number": period_number,
    }
    if account.balance_cents - account.reserved_cents < lease.rent_cents_per_period:
        payment = PropertyLeasePayment(
            lease_id=lease.id,
            period_number=period_number,
            amount_cents=lease.rent_cents_per_period,
            status="defaulted",
            input_snapshot_json=input_snapshot,
            paid_at=at,
        )
        lease.status = "defaulted"
        lease.default_reason = "rent_default"
        lease.defaulted_at = at
        property_.status = "owned"
        property_.company_use_id = None
        company.risk_bps = min(10_000, company.risk_bps + 250)
    else:
        transaction = transfer_account_to_profile_cash(
            db,
            account,
            landlord,
            amount_cents=lease.rent_cents_per_period,
            transaction_type="property_rent",
            idempotency_key=f"property-lease:{lease.id}:period:{period_number}",
            reference_type="property_lease",
            reference_id=lease.id,
        )
        payment = PropertyLeasePayment(
            lease_id=lease.id,
            period_number=period_number,
            amount_cents=lease.rent_cents_per_period,
            status="paid",
            transaction_id=transaction.id,
            input_snapshot_json=input_snapshot,
            paid_at=at,
        )
        lease.periods_paid = period_number
        if period_number >= lease.term_periods:
            lease.status = "completed"
            lease.completed_at = at
            property_.status = "owned"
            property_.company_use_id = None
        else:
            lease.next_payment_at = lease.next_payment_at + timedelta(
                minutes=settings.property_lease_interval_minutes
            )
    property_.version += 1
    company.version += 1
    db.add(
        snapshot_company(company, reason=f"property_rent_{payment.status}", reference_id=lease.id)
    )
    db.add(payment)
    db.flush()
    audit(
        db,
        None,
        f"property.lease.payment_{payment.status}",
        "property_lease_payment",
        payment.id,
        f"property-lease-scheduler:{lease.id}:{period_number}",
        input_snapshot,
    )
    if lease.status == "defaulted":
        create_company_warning(
            db,
            company=company,
            warning_type="rent_default",
            title=f"Rent warning for {company.name}",
            body="A scheduled company rent payment entered abstract default.",
            dedupe_key=f"company-warning:lease:{lease.id}:{period_number}",
            metadata={"lease_id": lease.id, "period_number": period_number},
        )
    db.add(
        RealtimeEvent(
            world_id=lease.world_id,
            event_type=(
                "property.lease_defaulted"
                if lease.status == "defaulted"
                else (
                    "property.lease_completed"
                    if lease.status == "completed"
                    else "property.rent_paid"
                )
            ),
            payload_json={
                "lease_id": lease.id,
                "property_id": lease.property_id,
                "period_number": period_number,
                "status": lease.status,
            },
            created_at=at,
            expires_at=at + timedelta(days=7),
        )
    )
    return payment


def advance_real_estate(
    db: Session,
    settings: Settings,
    *,
    at: datetime | None = None,
) -> dict[str, int]:
    now = as_utc(at or datetime.now(UTC))
    with _LOCK:
        worlds = set(db.scalars(select(RealEstateDistrictIndex.world_id).distinct()))
        refreshed = sum(
            refresh_real_estate_indices(db, world_id=world_id, at=now)
            for world_id in sorted(worlds)
        )
        paid = 0
        defaulted = 0
        completed = 0
        leases = list(
            db.scalars(
                select(PropertyLease)
                .where(
                    PropertyLease.status == "active",
                    PropertyLease.next_payment_at <= now,
                )
                .order_by(PropertyLease.next_payment_at, PropertyLease.id)
                .with_for_update()
            )
        )
        for lease in leases:
            while lease.status == "active" and as_utc(lease.next_payment_at) <= now:
                payment = _settle_lease_period(
                    db,
                    lease,
                    at=as_utc(lease.next_payment_at),
                    settings=settings,
                )
                paid += int(payment.status == "paid")
                defaulted += int(payment.status == "defaulted")
                completed += int(lease.status == "completed")
        db.commit()
        return {
            "indices_refreshed": refreshed,
            "rent_payments_paid": paid,
            "leases_defaulted": defaulted,
            "leases_completed": completed,
        }


def archive_real_estate_company_use(
    db: Session,
    world_id: str,
    *,
    at: datetime,
) -> list[tuple[RealEstateProperty, dict[str, int | str | None]]]:
    archived_at = as_utc(at)
    snapshots: list[tuple[RealEstateProperty, dict[str, int | str | None]]] = []
    properties = list(
        db.scalars(
            select(RealEstateProperty)
            .where(
                RealEstateProperty.world_id == world_id,
                RealEstateProperty.owner_profile_id.is_not(None),
            )
            .order_by(RealEstateProperty.id)
            .with_for_update()
        )
    )
    for property_ in properties:
        snapshots.append(
            (
                property_,
                {
                    "property_code": property_.property_code,
                    "property_type": property_.property_type,
                    "owner_profile_id": property_.owner_profile_id,
                    "company_use_id": property_.company_use_id,
                    "headquarters_level": property_.headquarters_level,
                    "base_value_cents": property_.base_value_cents,
                    "improvement_value_cents": property_.improvement_value_cents,
                    "status": property_.status,
                },
            )
        )
        if property_.status == "leased":
            lease = db.scalar(
                select(PropertyLease)
                .where(
                    PropertyLease.property_id == property_.id,
                    PropertyLease.status == "active",
                )
                .with_for_update()
            )
            if lease is not None:
                lease.status = "cancelled"
                lease.cancelled_at = archived_at
            property_.status = "owned"
        property_.company_use_id = None
        property_.listing_type = None
        property_.version += 1
    return snapshots


def list_properties(
    db: Session,
    profile: PlayerProfile,
) -> list[RealEstateProperty]:
    return list(
        db.scalars(
            select(RealEstateProperty)
            .where(RealEstateProperty.world_id == profile.world_id)
            .order_by(
                RealEstateProperty.district_id,
                RealEstateProperty.property_type,
            )
        )
    )


def list_district_indices(
    db: Session,
    profile: PlayerProfile,
) -> list[RealEstateDistrictIndex]:
    return list(
        db.scalars(
            select(RealEstateDistrictIndex)
            .where(RealEstateDistrictIndex.world_id == profile.world_id)
            .order_by(RealEstateDistrictIndex.district_id)
        )
    )


def list_property_leases(
    db: Session,
    profile: PlayerProfile,
) -> list[PropertyLease]:
    owned_companies = select(CompanyOwnership.company_id).where(
        CompanyOwnership.owner_profile_id == profile.id,
        CompanyOwnership.ownership_bps > 0,
    )
    return list(
        db.scalars(
            select(PropertyLease)
            .where(
                PropertyLease.world_id == profile.world_id,
                (
                    (PropertyLease.landlord_profile_id == profile.id)
                    | (PropertyLease.tenant_company_id.in_(owned_companies))
                ),
            )
            .order_by(PropertyLease.created_at.desc())
        )
    )


def property_owner_name(db: Session, property_: RealEstateProperty) -> str | None:
    if property_.owner_profile_id is None:
        return None
    profile = db.get(PlayerProfile, property_.owner_profile_id)
    if profile is None:
        return "Archived owner"
    user = db.get(User, profile.user_id)
    return user.display_name if user else profile.codename
