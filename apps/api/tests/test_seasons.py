from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.economy import ensure_city_sector_markets
from shadowgrid.finance import ensure_system_account, post_balanced_transfer
from shadowgrid.models import (
    AccountReward,
    AuditLog,
    BondHolding,
    BondIssue,
    CartelDistrictInfluence,
    CommercialContract,
    Company,
    CompanyLoan,
    ContractTender,
    District,
    ExchangeListing,
    HallOfFameEntry,
    LedgerTransaction,
    Organization,
    OrganizationMembership,
    PlayerProfile,
    RealEstateProperty,
    RealtimeEvent,
    ResourceBalance,
    Season,
    SeasonArchiveSnapshot,
    SeasonScoreSnapshot,
    ShareClass,
    ShareHolding,
    User,
    World,
)
from shadowgrid.real_estate import seed_real_estate
from shadowgrid.seasons import (
    advance_due_seasons,
    close_season,
    create_season_from_template,
    season_financial_history_counts,
    seed_season_template,
    shorten_season,
)
from shadowgrid.security import hash_password
from sqlalchemy import func, select

PASSWORD = "StrongPassword123"


def _login(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _join_player(
    client: TestClient,
    *,
    email: str,
    codename: str,
    is_admin: bool = False,
) -> tuple[str, dict[str, str]]:
    with SessionLocal() as db:
        world = db.scalar(select(World))
        district = db.scalar(select(District))
        assert world is not None and district is not None
        district_id = district.id
        user = User(
            email=email,
            password_hash=hash_password(PASSWORD),
            display_name=codename,
            email_verified=True,
            is_admin=is_admin,
        )
        db.add(user)
        db.commit()
        world_id = world.id
    headers = _login(client, email)
    joined = client.post(
        f"/api/v1/worlds/{world_id}/join",
        headers={**headers, "Idempotency-Key": f"join-{email}"},
        json={
            "codename": codename,
            "archetype": "business_consortium",
            "home_district_id": district_id,
        },
    )
    assert joined.status_code == 200, joined.text
    return str(joined.json()["id"]), headers


def _seed_season() -> tuple[str, str]:
    with SessionLocal() as db:
        world = db.scalar(select(World))
        assert world is not None
        template = seed_season_template(db, get_settings())
        db.flush()
        season = create_season_from_template(
            db,
            world=world,
            template=template,
            starts_at=datetime.now(UTC),
            idempotency_key="test-season-0",
        )
        return world.id, season.id


def _create_company(
    client: TestClient,
    headers: dict[str, str],
) -> str:
    district = client.get("/api/v1/districts", headers=headers).json()[0]
    response = client.post(
        "/api/v1/companies",
        headers={**headers, "Idempotency-Key": "season-company-create"},
        json={
            "name": "Season Systems GmbH",
            "industry": "technology",
            "district_id": district["id"],
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def _create_seasonal_assets(profile_id: str, company_id: str) -> tuple[str, str]:
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        company = db.get(Company, company_id)
        assert profile is not None and company is not None
        company.status = "public"
        system = ensure_system_account(db, profile.world_id)
        fee_transaction = post_balanced_transfer(
            db,
            world_id=profile.world_id,
            source_account=company.account,
            target_account=system,
            amount_cents=1,
            transaction_type="season_test_ipo_fee",
            idempotency_key="season-test-ipo-fee",
            reference_type="company",
            reference_id=company.id,
            actor_profile_id=profile.id,
        )
        listing = ExchangeListing(
            world_id=profile.world_id,
            company_id=company.id,
            symbol="SEAS",
            status="active",
            total_shares=10_000,
            offered_shares=2_000,
            initial_price_cents=2_000,
            last_price_cents=2_500,
            ipo_fee_cents=1,
            fee_transaction_id=fee_transaction.id,
            idempotency_key="season-test-listing",
        )
        db.add(listing)
        db.flush()
        share_class = ShareClass(
            listing_id=listing.id,
            total_shares=10_000,
            tradable=True,
        )
        db.add(share_class)
        db.flush()
        db.add_all(
            (
                ShareHolding(
                    share_class_id=share_class.id,
                    owner_type="profile",
                    profile_id=profile.id,
                    quantity=2_000,
                    average_cost_cents=2_000,
                ),
                ShareHolding(
                    share_class_id=share_class.id,
                    owner_type="company",
                    company_id=company.id,
                    quantity=8_000,
                    average_cost_cents=0,
                ),
            )
        )
        organization = Organization(
            world_id=profile.world_id,
            city_id=profile.city_id,
            name="Season Alliance",
            tag="SEA",
            archetype="business_consortium",
            description="A seasonal test cartel.",
            governance_model="directorate",
        )
        db.add(organization)
        db.flush()
        db.add(
            OrganizationMembership(
                organization_id=organization.id,
                profile_id=profile.id,
                role="leader",
                status="active",
            )
        )
        district_id = str(profile.home_district_id)
        db.add(
            CartelDistrictInfluence(
                world_id=profile.world_id,
                organization_id=organization.id,
                district_id=district_id,
                kind="economic",
                points=250,
            )
        )
        ensure_city_sector_markets(db, profile.world_id)
        db.commit()
        return listing.id, organization.id


def test_season_state_admin_shortening_simulation_and_rbac(
    client: TestClient,
) -> None:
    _, player_headers = _join_player(
        client,
        email="season-player@example.com",
        codename="Season Player",
    )
    _, admin_headers = _join_player(
        client,
        email="season-admin@example.com",
        codename="Season Admin",
        is_admin=True,
    )
    _, season_id = _seed_season()

    state = client.get("/api/v1/seasons/current", headers=player_headers)
    assert state.status_code == 200, state.text
    assert state.json()["phase"] == "setup"
    assert len(state.json()["goals_json"]) == 3
    assert len(state.json()["scoring_categories_json"]) == 12
    assert state.json()["remaining_seconds"] > 0

    forbidden = client.post(
        f"/api/v1/admin/seasons/{season_id}/shorten",
        headers=player_headers,
        json={"duration_minutes": 60},
    )
    assert forbidden.status_code == 403
    shortened = client.post(
        f"/api/v1/admin/seasons/{season_id}/shorten",
        headers=admin_headers,
        json={"duration_minutes": 60},
    )
    assert shortened.status_code == 200, shortened.text
    schedule = shortened.json()["phase_schedule_json"]
    for boundary_index, expected_phase in (
        (0, "early"),
        (1, "mid"),
        (2, "late"),
        (3, "scoring"),
    ):
        simulated_at = datetime.fromisoformat(schedule[boundary_index]["ends_at"]) + timedelta(
            seconds=1
        )
        simulated = client.post(
            f"/api/v1/admin/seasons/{season_id}/simulate",
            headers=admin_headers,
            json={"at": simulated_at.isoformat()},
        )
        assert simulated.status_code == 200, simulated.text
        assert simulated.json()["phase"] == expected_phase


def test_final_scoring_ties_idempotency_archival_and_persistent_rewards(
    client: TestClient,
) -> None:
    first_id, first_headers = _join_player(
        client,
        email="season-first@example.com",
        codename="Alpha Network",
    )
    _, second_headers = _join_player(
        client,
        email="season-second@example.com",
        codename="Beta Network",
    )
    world_id, season_id = _seed_season()
    company_id = _create_company(client, first_headers)
    listing_id, organization_id = _create_seasonal_assets(first_id, company_id)
    district = client.get("/api/v1/districts", headers=first_headers).json()[0]
    provider_response = client.post(
        "/api/v1/companies",
        headers={**first_headers, "Idempotency-Key": "season-provider-create"},
        json={
            "name": "Season Provider GmbH",
            "industry": "logistics",
            "district_id": district["id"],
        },
    )
    assert provider_response.status_code == 201, provider_response.text
    provider_id = str(provider_response.json()["id"])
    tender_response = client.post(
        "/api/v1/contracts/tenders",
        headers={**first_headers, "Idempotency-Key": "season-contract-tender"},
        json={
            "issuer_company_id": company_id,
            "contract_type": "service",
            "title": "Season transition service",
            "description": "A seasonal reset boundary test.",
            "max_price_cents": 100_000,
            "duration_periods": 2,
            "capacity_units": 1,
            "submission_minutes": 60,
        },
    )
    assert tender_response.status_code == 201, tender_response.text
    bid_response = client.post(
        f"/api/v1/contracts/tenders/{tender_response.json()['id']}/bids",
        headers={**first_headers, "Idempotency-Key": "season-contract-bid"},
        json={"bidder_company_id": provider_id, "price_cents": 90_000},
    )
    assert bid_response.status_code == 201, bid_response.text
    award_response = client.post(
        f"/api/v1/contracts/tenders/{tender_response.json()['id']}/award",
        headers={**first_headers, "Idempotency-Key": "season-contract-award"},
        json={"bid_id": bid_response.json()["id"]},
    )
    assert award_response.status_code == 201, award_response.text
    contract_id = str(award_response.json()["id"])
    loan_application_response = client.post(
        "/api/v1/loans/applications",
        headers={**first_headers, "Idempotency-Key": "season-loan-application"},
        json={
            "company_id": company_id,
            "requested_principal_cents": 100_000,
            "term_periods": 2,
            "collateral_score_bps": 5_000,
            "purpose": "Season transition finance boundary",
        },
    )
    assert loan_application_response.status_code == 201, loan_application_response.text
    assert loan_application_response.json()["status"] == "offered"
    loan_response = client.post(
        f"/api/v1/loans/applications/{loan_application_response.json()['id']}/accept",
        headers={**first_headers, "Idempotency-Key": "season-loan-accept"},
    )
    assert loan_response.status_code == 201, loan_response.text
    loan_id = str(loan_response.json()["id"])
    bond_issue_response = client.post(
        "/api/v1/bonds/issues",
        headers={**first_headers, "Idempotency-Key": "season-bond-issue"},
        json={
            "issuer_company_id": company_id,
            "symbol": "SEA1",
            "title": "Season boundary bond",
            "face_value_cents": 100_000,
            "total_units": 1,
            "coupon_rate_bps": 800,
            "term_periods": 2,
        },
    )
    assert bond_issue_response.status_code == 201, bond_issue_response.text
    bond_subscription_response = client.post(
        f"/api/v1/bonds/issues/{bond_issue_response.json()['id']}/subscribe",
        headers={**second_headers, "Idempotency-Key": "season-bond-subscription"},
        json={"quantity": 1},
    )
    assert bond_subscription_response.status_code == 201, bond_subscription_response.text
    bond_issue_id = str(bond_issue_response.json()["id"])
    with SessionLocal() as db:
        seed_real_estate(db, world_id)
        db.commit()
    property_market = client.get(
        "/api/v1/real-estate/properties",
        headers=first_headers,
    )
    assert property_market.status_code == 200, property_market.text
    property_id = str(
        next(
            item["id"]
            for item in property_market.json()
            if item["property_type"] == "land" and item["status"] == "available"
        )
    )
    property_purchase = client.post(
        f"/api/v1/real-estate/properties/{property_id}/buy",
        headers={**first_headers, "Idempotency-Key": "season-property-purchase"},
    )
    assert property_purchase.status_code == 201, property_purchase.text
    property_assignment = client.post(
        f"/api/v1/real-estate/properties/{property_id}/assign",
        headers={**first_headers, "Idempotency-Key": "season-property-assignment"},
        json={"company_id": company_id},
    )
    assert property_assignment.status_code == 200, property_assignment.text
    before_history = {}
    with SessionLocal() as db:
        before_history = season_financial_history_counts(db, world_id)
        admin = db.scalar(select(User).where(User.email == "season-first@example.com"))
        assert admin is not None
        first_result = close_season(
            db,
            season_id=season_id,
            at=datetime.now(UTC) + timedelta(days=30),
            admin=admin,
            request_id="season-close-first",
        )
        assert first_result.season.status == "archived"
        assert first_result.score_count > 0
        assert first_result.hall_of_fame_count > 0
        assert first_result.reward_count > 0
        assert first_result.archive_count > 0
        counts_after_first = {
            "scores": db.scalar(
                select(func.count())
                .select_from(SeasonScoreSnapshot)
                .where(SeasonScoreSnapshot.season_id == season_id)
            ),
            "hall": db.scalar(
                select(func.count())
                .select_from(HallOfFameEntry)
                .where(HallOfFameEntry.season_id == season_id)
            ),
            "rewards": db.scalar(
                select(func.count())
                .select_from(AccountReward)
                .where(AccountReward.season_id == season_id)
            ),
            "archives": db.scalar(
                select(func.count())
                .select_from(SeasonArchiveSnapshot)
                .where(SeasonArchiveSnapshot.season_id == season_id)
            ),
            "ledger": db.scalar(select(func.count()).select_from(LedgerTransaction)),
        }
        repeated = close_season(
            db,
            season_id=season_id,
            at=datetime.now(UTC) + timedelta(days=31),
            admin=admin,
            request_id="season-close-repeated",
        )
        assert repeated.score_count == counts_after_first["scores"]
        assert repeated.reward_count == counts_after_first["rewards"]
        assert {
            "scores": db.scalar(
                select(func.count())
                .select_from(SeasonScoreSnapshot)
                .where(SeasonScoreSnapshot.season_id == season_id)
            ),
            "hall": db.scalar(
                select(func.count())
                .select_from(HallOfFameEntry)
                .where(HallOfFameEntry.season_id == season_id)
            ),
            "rewards": db.scalar(
                select(func.count())
                .select_from(AccountReward)
                .where(AccountReward.season_id == season_id)
            ),
            "archives": db.scalar(
                select(func.count())
                .select_from(SeasonArchiveSnapshot)
                .where(SeasonArchiveSnapshot.season_id == season_id)
            ),
            "ledger": db.scalar(select(func.count()).select_from(LedgerTransaction)),
        } == counts_after_first

        tied_stability = list(
            db.scalars(
                select(SeasonScoreSnapshot)
                .where(
                    SeasonScoreSnapshot.season_id == season_id,
                    SeasonScoreSnapshot.category == "stability",
                )
                .order_by(SeasonScoreSnapshot.entity_name)
            )
        )
        assert len(tied_stability) == 2
        assert tied_stability[0].rank == tied_stability[1].rank == 1
        assert tied_stability[0].tied and tied_stability[1].tied
        assert tied_stability[0].tie_break_json["rule"] == "competition_rank_equal_score"
        categories = set(
            db.scalars(
                select(SeasonScoreSnapshot.category).where(
                    SeasonScoreSnapshot.season_id == season_id
                )
            )
        )
        assert len(categories) == 12

        company = db.get(Company, company_id)
        listing = db.get(ExchangeListing, listing_id)
        organization = db.get(Organization, organization_id)
        first_balance = db.get(ResourceBalance, first_id)
        contract = db.get(CommercialContract, contract_id)
        loan = db.get(CompanyLoan, loan_id)
        bond_issue = db.get(BondIssue, bond_issue_id)
        bond_holding = db.scalar(select(BondHolding).where(BondHolding.issue_id == bond_issue_id))
        real_estate_property = db.get(RealEstateProperty, property_id)
        tender = db.get(ContractTender, tender_response.json()["id"])
        assert company is not None and company.status == "archived"
        assert listing is not None and listing.status == "delisted"
        assert organization is not None and organization.status == "dissolved"
        assert first_balance is not None and first_balance.cash == 80_000
        assert contract is not None and contract.status == "cancelled"
        assert loan is not None and loan.status == "cancelled"
        assert bond_issue is not None and bond_issue.status == "cancelled"
        assert bond_holding is not None and bond_holding.quantity == 0
        assert real_estate_property is not None
        assert real_estate_property.owner_profile_id == first_id
        assert real_estate_property.company_use_id is None
        assert real_estate_property.status == "owned"
        assert tender is not None and tender.status == "awarded"
        archive_types = set(
            db.scalars(
                select(SeasonArchiveSnapshot.entity_type).where(
                    SeasonArchiveSnapshot.season_id == season_id
                )
            )
        )
        assert {
            "commercial_contract",
            "company_loan",
            "bond_issue",
            "real_estate_property",
            "company",
            "exchange_listing",
            "market",
            "cartel",
        } <= archive_types
        after_history = season_financial_history_counts(db, world_id)
        assert after_history["ledger_transactions"] >= before_history["ledger_transactions"]
        assert after_history["exchange_trades"] == before_history["exchange_trades"]

        immutable = db.scalar(select(HallOfFameEntry).where(HallOfFameEntry.season_id == season_id))
        assert immutable is not None
        immutable.score_value += 1
        with pytest.raises(ValueError, match="immutable"):
            db.flush()
        db.rollback()

    rewards = client.get("/api/v1/account/rewards/me", headers=second_headers)
    assert rewards.status_code == 200
    assert {item["reward_type"] for item in rewards.json()} == {
        "achievement",
        "title",
        "cosmetic",
    }


def test_new_season_from_template_is_idempotent_and_preserves_history(
    client: TestClient,
) -> None:
    profile_id, admin_headers = _join_player(
        client,
        email="season-reset-admin@example.com",
        codename="Reset Admin",
        is_admin=True,
    )
    world_id, season_id = _seed_season()
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.email == "season-reset-admin@example.com"))
        assert admin is not None
        close_season(
            db,
            season_id=season_id,
            at=datetime.now(UTC) + timedelta(days=30),
            admin=admin,
            request_id="season-reset-close",
        )
        old_score_count = int(
            db.scalar(
                select(func.count())
                .select_from(SeasonScoreSnapshot)
                .where(SeasonScoreSnapshot.season_id == season_id)
            )
            or 0
        )
        old_reward_count = int(
            db.scalar(
                select(func.count())
                .select_from(AccountReward)
                .where(AccountReward.user_id == admin.id)
            )
            or 0
        )
        history_before = season_financial_history_counts(db, world_id)

    payload = {
        "world_id": world_id,
        "template_key": "cologne_standard",
        "template_version": 1,
    }
    headers = {**admin_headers, "Idempotency-Key": "season-create-next"}
    created = client.post("/api/v1/admin/seasons", headers=headers, json=payload)
    duplicate = client.post("/api/v1/admin/seasons", headers=headers, json=payload)
    assert created.status_code == duplicate.status_code == 201
    assert created.json()["id"] == duplicate.json()["id"]
    assert created.json()["season_number"] == 1
    assert created.json()["phase"] == "setup"

    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count())
                .select_from(SeasonScoreSnapshot)
                .where(SeasonScoreSnapshot.season_id == season_id)
            )
            == old_score_count
        )
        admin = db.scalar(select(User).where(User.email == "season-reset-admin@example.com"))
        profile = db.get(PlayerProfile, profile_id)
        assert admin is not None and profile is not None
        assert (
            db.scalar(
                select(func.count())
                .select_from(AccountReward)
                .where(AccountReward.user_id == admin.id)
            )
            == old_reward_count
        )
        assert season_financial_history_counts(db, world_id) == history_before
        assert (
            db.scalar(select(func.count()).select_from(Season).where(Season.world_id == world_id))
            == 2
        )


def test_repeated_season_scheduler_changes_each_phase_only_once(
    client: TestClient,
) -> None:
    profile_id, _ = _join_player(
        client,
        email="season-scheduler@example.com",
        codename="Scheduler Admin",
        is_admin=True,
    )
    _, season_id = _seed_season()
    with SessionLocal() as db:
        profile = db.get(PlayerProfile, profile_id)
        season = db.get(Season, season_id)
        assert profile is not None and season is not None
        admin = db.get(User, profile.user_id)
        assert admin is not None
        shorten_season(
            db,
            season_id=season_id,
            duration_minutes=10,
            admin=admin,
            request_id="season-scheduler-shorten",
            at=season.starts_at,
        )
        season = db.get(Season, season_id)
        assert season is not None
        early_at = datetime.fromisoformat(season.phase_schedule_json[0]["ends_at"]) + timedelta(
            seconds=1
        )
        assert advance_due_seasons(db, at=early_at) == {
            "phase_changes": 1,
            "archived": 0,
        }
        event_count = int(
            db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(RealtimeEvent.event_type == "season.phase.changed")
            )
            or 0
        )
        audit_count = int(
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "season.simulated")
            )
            or 0
        )
        assert advance_due_seasons(db, at=early_at) == {
            "phase_changes": 0,
            "archived": 0,
        }
        assert (
            db.scalar(
                select(func.count())
                .select_from(RealtimeEvent)
                .where(RealtimeEvent.event_type == "season.phase.changed")
            )
            == event_count
        )
        assert (
            db.scalar(
                select(func.count())
                .select_from(AuditLog)
                .where(AuditLog.action == "season.simulated")
            )
            == audit_count
        )

        season = db.get(Season, season_id)
        assert season is not None
        after_end = season.ends_at + timedelta(seconds=1)
        assert advance_due_seasons(db, at=after_end) == {
            "phase_changes": 0,
            "archived": 1,
        }
        score_count = db.scalar(
            select(func.count())
            .select_from(SeasonScoreSnapshot)
            .where(SeasonScoreSnapshot.season_id == season_id)
        )
        assert advance_due_seasons(db, at=after_end) == {
            "phase_changes": 0,
            "archived": 0,
        }
        assert (
            db.scalar(
                select(func.count())
                .select_from(SeasonScoreSnapshot)
                .where(SeasonScoreSnapshot.season_id == season_id)
            )
            == score_count
        )
