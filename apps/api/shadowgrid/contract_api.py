from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request, status
from sqlalchemy import func, select

from shadowgrid.config import get_settings
from shadowgrid.contract_schemas import (
    AwardBidRequest,
    BidView,
    CommercialContractView,
    ContractConfigView,
    ContractSettlementView,
    CreateTenderRequest,
    SubmitBidRequest,
    TenderView,
)
from shadowgrid.contracts import (
    award_bid,
    create_tender,
    list_contract_settlements,
    list_profile_contracts,
    list_tenders,
    list_visible_bids,
    submit_bid,
)
from shadowgrid.dependencies import CurrentProfile, Db, IdempotencyKey
from shadowgrid.models import (
    CommercialContract,
    Company,
    ContractBid,
    ContractTender,
)

router = APIRouter()


def _tender_view(db: Db, tender: ContractTender) -> TenderView:
    issuer = db.get(Company, tender.issuer_company_id)
    return TenderView.model_validate(
        {
            **{
                field: getattr(tender, field)
                for field in TenderView.model_fields
                if field not in {"issuer_company_name", "bid_count"}
            },
            "issuer_company_name": issuer.name if issuer else "Archived company",
            "bid_count": int(
                db.scalar(
                    select(func.count())
                    .select_from(ContractBid)
                    .where(ContractBid.tender_id == tender.id)
                )
                or 0
            ),
        }
    )


def _bid_view(db: Db, bid: ContractBid) -> BidView:
    company = db.get(Company, bid.bidder_company_id)
    return BidView.model_validate(
        {
            **{
                field: getattr(bid, field)
                for field in BidView.model_fields
                if field != "bidder_company_name"
            },
            "bidder_company_name": company.name if company else "Archived company",
        }
    )


def _contract_view(db: Db, contract: CommercialContract) -> CommercialContractView:
    issuer = db.get(Company, contract.issuer_company_id)
    provider = db.get(Company, contract.provider_company_id)
    return CommercialContractView.model_validate(
        {
            **{
                field: getattr(contract, field)
                for field in CommercialContractView.model_fields
                if field not in {"issuer_company_name", "provider_company_name"}
            },
            "issuer_company_name": issuer.name if issuer else "Archived company",
            "provider_company_name": provider.name if provider else "Archived company",
        }
    )


@router.get(
    "/contracts/config",
    response_model=ContractConfigView,
    tags=["contracts"],
)
def contract_config(_: CurrentProfile) -> ContractConfigView:
    settings = get_settings()
    return ContractConfigView(
        settlement_interval_minutes=settings.contract_settlement_interval_minutes,
        max_duration_periods=settings.contract_tender_max_duration_periods,
        reputation_reward_bps=settings.contract_reputation_reward_bps,
        breach_reputation_penalty_bps=settings.contract_breach_reputation_penalty_bps,
        breach_investigation_penalty_bps=(settings.contract_breach_investigation_penalty_bps),
    )


@router.get(
    "/contracts/tenders",
    response_model=list[TenderView],
    tags=["contracts"],
)
def contract_tenders(db: Db, profile: CurrentProfile) -> list[TenderView]:
    return [_tender_view(db, tender) for tender in list_tenders(db, profile)]


@router.post(
    "/contracts/tenders",
    response_model=TenderView,
    status_code=status.HTTP_201_CREATED,
    tags=["contracts"],
)
def post_contract_tender(
    payload: CreateTenderRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> TenderView:
    tender = create_tender(
        db,
        profile,
        **payload.model_dump(),
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
        settings=get_settings(),
    )
    return _tender_view(db, tender)


@router.get(
    "/contracts/tenders/{tender_id}/bids",
    response_model=list[BidView],
    tags=["contracts"],
)
def contract_bids(
    tender_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[BidView]:
    return [_bid_view(db, bid) for bid in list_visible_bids(db, profile, tender_id)]


@router.post(
    "/contracts/tenders/{tender_id}/bids",
    response_model=BidView,
    status_code=status.HTTP_201_CREATED,
    tags=["contracts"],
)
def post_contract_bid(
    tender_id: str,
    payload: SubmitBidRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> BidView:
    bid = submit_bid(
        db,
        profile,
        tender_id=tender_id,
        **payload.model_dump(),
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
    )
    return _bid_view(db, bid)


@router.post(
    "/contracts/tenders/{tender_id}/award",
    response_model=CommercialContractView,
    status_code=status.HTTP_201_CREATED,
    tags=["contracts"],
)
def post_contract_award(
    tender_id: str,
    payload: AwardBidRequest,
    request: Request,
    db: Db,
    profile: CurrentProfile,
    idempotency_key: IdempotencyKey,
) -> CommercialContractView:
    contract = award_bid(
        db,
        profile,
        tender_id=tender_id,
        bid_id=payload.bid_id,
        idempotency_key=idempotency_key,
        request_id=request.state.request_id,
        settings=get_settings(),
    )
    return _contract_view(db, contract)


@router.get(
    "/contracts/me",
    response_model=list[CommercialContractView],
    tags=["contracts"],
)
def my_contracts(
    db: Db,
    profile: CurrentProfile,
) -> list[CommercialContractView]:
    return [_contract_view(db, contract) for contract in list_profile_contracts(db, profile)]


@router.get(
    "/contracts/{contract_id}/settlements",
    response_model=list[ContractSettlementView],
    tags=["contracts"],
)
def contract_settlements(
    contract_id: str,
    db: Db,
    profile: CurrentProfile,
) -> list[Any]:
    return list_contract_settlements(db, profile, contract_id)
