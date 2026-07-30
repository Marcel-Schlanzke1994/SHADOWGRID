from __future__ import annotations

from fastapi import APIRouter, Request, status
from sqlalchemy import select

from shadowgrid.config import get_settings
from shadowgrid.dependencies import CurrentProfile, Db, IdempotencyKey
from shadowgrid.models import (
    City,
    Company,
    District,
    PlayerProfile,
    PropertyImprovement,
    PropertyLease,
    PropertyLeasePayment,
    RealEstateDistrictIndex,
    RealEstateProperty,
    User,
)
from shadowgrid.real_estate import (
    assign_property_to_company,
    buy_property,
    effective_rent_cents,
    effective_sale_price_cents,
    lease_property,
    list_district_indices,
    list_properties,
    list_property_for_rent,
    list_property_for_sale,
    list_property_leases,
    property_owner_name,
    unassign_property,
    upgrade_headquarters,
)
from shadowgrid.real_estate_schemas import (
    PropertyCompanyAssignmentRequest,
    PropertyImprovementView,
    PropertyLeasePaymentView,
    PropertyLeaseRequest,
    PropertyLeaseView,
    PropertyRentListingRequest,
    PropertySaleListingRequest,
    PropertyTransferView,
    RealEstateConfigView,
    RealEstateIndexView,
    RealEstatePropertyView,
)

router = APIRouter()


def _company_name(db: Db, company_id: str | None) -> str | None:
    if company_id is None:
        return None
    company = db.get(Company, company_id)
    return company.name if company else "Archived company"


def _profile_name(db: Db, profile_id: str) -> str:
    profile = db.get(PlayerProfile, profile_id)
    if profile is None:
        return "Archived owner"
    user = db.get(User, profile.user_id)
    return user.display_name if user else profile.codename


def _property_view(
    db: Db,
    profile: CurrentProfile,
    property_: RealEstateProperty,
) -> RealEstatePropertyView:
    city = db.get(City, property_.city_id)
    district = db.get(District, property_.district_id)
    return RealEstatePropertyView.model_validate(
        {
            **{
                field: getattr(property_, field)
                for field in RealEstatePropertyView.model_fields
                if field
                not in {
                    "city_name",
                    "district_name",
                    "owner_name",
                    "is_owned_by_me",
                    "company_use_name",
                    "effective_sale_price_cents",
                    "effective_rent_cents_per_period",
                }
            },
            "city_name": city.name if city else "Archived city",
            "district_name": district.name if district else "Archived district",
            "owner_name": property_owner_name(db, property_),
            "is_owned_by_me": property_.owner_profile_id == profile.id,
            "company_use_name": _company_name(db, property_.company_use_id),
            "effective_sale_price_cents": effective_sale_price_cents(db, property_),
            "effective_rent_cents_per_period": (
                effective_rent_cents(db, property_) if property_.rent_cents_per_period > 0 else 0
            ),
        }
    )


def _index_view(db: Db, index: RealEstateDistrictIndex) -> RealEstateIndexView:
    city = db.get(City, index.city_id)
    district = db.get(District, index.district_id)
    return RealEstateIndexView.model_validate(
        {
            **{
                field: getattr(index, field)
                for field in RealEstateIndexView.model_fields
                if field not in {"city_name", "district_name"}
            },
            "city_name": city.name if city else "Archived city",
            "district_name": district.name if district else "Archived district",
        }
    )


def _lease_view(db: Db, lease: PropertyLease) -> PropertyLeaseView:
    property_ = db.get(RealEstateProperty, lease.property_id)
    payments = list(
        db.scalars(
            select(PropertyLeasePayment)
            .where(PropertyLeasePayment.lease_id == lease.id)
            .order_by(PropertyLeasePayment.period_number)
        )
    )
    return PropertyLeaseView.model_validate(
        {
            **{
                field: getattr(lease, field)
                for field in PropertyLeaseView.model_fields
                if field
                not in {
                    "property_name",
                    "landlord_name",
                    "tenant_company_name",
                    "payments",
                }
            },
            "property_name": property_.name if property_ else "Archived property",
            "landlord_name": _profile_name(db, lease.landlord_profile_id),
            "tenant_company_name": (
                _company_name(db, lease.tenant_company_id) or "Archived company"
            ),
            "payments": [PropertyLeasePaymentView.model_validate(payment) for payment in payments],
        }
    )


@router.get(
    "/real-estate/config",
    response_model=RealEstateConfigView,
    tags=["real-estate"],
)
def real_estate_config(_: CurrentProfile) -> RealEstateConfigView:
    settings = get_settings()
    return RealEstateConfigView(
        index_interval_minutes=settings.real_estate_index_interval_minutes,
        lease_interval_minutes=settings.property_lease_interval_minutes,
        max_lease_periods=settings.property_max_lease_periods,
        headquarters_upgrade_base_cost_cents=(settings.headquarters_upgrade_base_cost_cents),
    )


@router.get(
    "/real-estate/indices",
    response_model=list[RealEstateIndexView],
    tags=["real-estate"],
)
def real_estate_indices(
    db: Db,
    profile: CurrentProfile,
) -> list[RealEstateIndexView]:
    return [_index_view(db, index) for index in list_district_indices(db, profile)]


@router.get(
    "/real-estate/properties",
    response_model=list[RealEstatePropertyView],
    tags=["real-estate"],
)
def real_estate_properties(
    db: Db,
    profile: CurrentProfile,
) -> list[RealEstatePropertyView]:
    return [_property_view(db, profile, property_) for property_ in list_properties(db, profile)]


@router.post(
    "/real-estate/properties/{property_id}/buy",
    response_model=PropertyTransferView,
    status_code=status.HTTP_201_CREATED,
    tags=["real-estate"],
)
def post_property_purchase(
    property_id: str,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> PropertyTransferView:
    return PropertyTransferView.model_validate(
        buy_property(
            db,
            profile,
            property_id=property_id,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        )
    )


@router.post(
    "/real-estate/properties/{property_id}/list-sale",
    response_model=RealEstatePropertyView,
    tags=["real-estate"],
)
def post_property_sale_listing(
    property_id: str,
    payload: PropertySaleListingRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> RealEstatePropertyView:
    return _property_view(
        db,
        profile,
        list_property_for_sale(
            db,
            profile,
            property_id=property_id,
            asking_price_cents=payload.asking_price_cents,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        ),
    )


@router.post(
    "/real-estate/properties/{property_id}/list-rent",
    response_model=RealEstatePropertyView,
    tags=["real-estate"],
)
def post_property_rent_listing(
    property_id: str,
    payload: PropertyRentListingRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> RealEstatePropertyView:
    return _property_view(
        db,
        profile,
        list_property_for_rent(
            db,
            profile,
            property_id=property_id,
            rent_cents_per_period=payload.rent_cents_per_period,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        ),
    )


@router.post(
    "/real-estate/properties/{property_id}/lease",
    response_model=PropertyLeaseView,
    status_code=status.HTTP_201_CREATED,
    tags=["real-estate"],
)
def post_property_lease(
    property_id: str,
    payload: PropertyLeaseRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> PropertyLeaseView:
    return _lease_view(
        db,
        lease_property(
            db,
            profile,
            property_id=property_id,
            tenant_company_id=payload.tenant_company_id,
            term_periods=payload.term_periods,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
            settings=get_settings(),
        ),
    )


@router.post(
    "/real-estate/properties/{property_id}/assign",
    response_model=RealEstatePropertyView,
    tags=["real-estate"],
)
def post_property_assignment(
    property_id: str,
    payload: PropertyCompanyAssignmentRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> RealEstatePropertyView:
    return _property_view(
        db,
        profile,
        assign_property_to_company(
            db,
            profile,
            property_id=property_id,
            company_id=payload.company_id,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        ),
    )


@router.post(
    "/real-estate/properties/{property_id}/unassign",
    response_model=RealEstatePropertyView,
    tags=["real-estate"],
)
def post_property_unassignment(
    property_id: str,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> RealEstatePropertyView:
    return _property_view(
        db,
        profile,
        unassign_property(
            db,
            profile,
            property_id=property_id,
            idempotency_key=idempotency_key,
            request_id=request.state.request_id,
        ),
    )


@router.post(
    "/real-estate/properties/{property_id}/headquarters/upgrade",
    response_model=PropertyImprovementView,
    status_code=status.HTTP_201_CREATED,
    tags=["real-estate"],
)
def post_headquarters_upgrade(
    property_id: str,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> PropertyImprovementView:
    improvement: PropertyImprovement = upgrade_headquarters(
        db,
        profile,
        property_id=property_id,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
        settings=get_settings(),
    )
    return PropertyImprovementView.model_validate(improvement)


@router.get(
    "/real-estate/leases/me",
    response_model=list[PropertyLeaseView],
    tags=["real-estate"],
)
def my_property_leases(
    db: Db,
    profile: CurrentProfile,
) -> list[PropertyLeaseView]:
    return [_lease_view(db, lease) for lease in list_property_leases(db, profile)]
