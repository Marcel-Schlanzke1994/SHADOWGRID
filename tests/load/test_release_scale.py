from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from time import perf_counter

from sqlalchemy import func, insert, select
from sqlalchemy.orm import Session

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "apps" / "api"))
LOAD_DATABASE = PROJECT_ROOT / ".local" / "release-load-test.db"
os.environ["APP_ENV"] = "test"
os.environ["DATABASE_URL"] = f"sqlite:///{LOAD_DATABASE.as_posix()}"
os.environ["SECRET_KEY"] = "load-secret-key-with-at-least-thirty-two-characters"  # noqa: S105
os.environ["REFRESH_PEPPER"] = "load-refresh-pepper-with-at-least-thirty-two-characters"
os.environ["SEED_SECRET"] = "load-seed-secret-with-at-least-thirty-two-characters"  # noqa: S105

from shadowgrid.config import Settings  # noqa: E402
from shadowgrid.database import Base, SessionLocal, engine  # noqa: E402
from shadowgrid.economy import run_economy_tick  # noqa: E402
from shadowgrid.exchange import listing_order_book, place_order  # noqa: E402
from shadowgrid.models import (  # noqa: E402
    Account,
    City,
    Company,
    District,
    ExchangeListing,
    ExchangeOrder,
    ExchangeTrade,
    LedgerTransaction,
    PlayerProfile,
    ResourceBalance,
    ShareClass,
    ShareHolding,
    User,
    World,
    uuid_str,
)

PLAYER_COUNT = 100
COMPANY_COUNT = 500
OPEN_ORDER_COUNT = 10_000
TICK_LIMIT_SECONDS = 180
ORDER_BOOK_LIMIT_SECONDS = 3
MATCH_LIMIT_SECONDS = 10


def test_release_scale_tick_and_order_matching() -> None:
    """Exercise the roadmap target against real persistence and domain services."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    try:
        with SessionLocal() as db:
            world, city, district, profiles, profile_accounts = _seed_players(db)
            companies = _seed_companies(
                db,
                world_id=world.id,
                district_id=district.id,
                profiles=profiles,
            )
            db.commit()

            tick_started = perf_counter()
            tick = run_economy_tick(db, world.id, at=datetime.now(UTC))
            tick_seconds = perf_counter() - tick_started
            assert tick.status == "completed"
            assert tick.company_count == COMPANY_COUNT
            assert tick_seconds < TICK_LIMIT_SECONDS

            listing, share_class = _seed_order_book(
                db,
                world_id=world.id,
                company=companies[0],
                profiles=profiles,
                profile_accounts=profile_accounts,
            )
            db.commit()
            open_before = db.scalar(
                select(func.count())
                .select_from(ExchangeOrder)
                .where(ExchangeOrder.status == "open")
            )
            assert open_before == OPEN_ORDER_COUNT

            book_started = perf_counter()
            buys, sells = listing_order_book(
                db,
                profiles[0],
                listing.id,
                limit=50,
            )
            book_seconds = perf_counter() - book_started
            assert len(buys) == 50
            assert sells == []
            assert book_seconds < ORDER_BOOK_LIMIT_SECONDS

            match_started = perf_counter()
            matched = place_order(
                db,
                profiles[0],
                listing_id=listing.id,
                side="sell",
                order_type="limit",
                quantity=1,
                limit_price_cents=100,
                expires_at=datetime.now(UTC) + timedelta(hours=1),
                idempotency_key="release-scale-match",
                request_id="release-scale",
                settings=Settings(),
            )
            match_seconds = perf_counter() - match_started
            assert matched.status == "filled"
            assert match_seconds < MATCH_LIMIT_SECONDS
            assert db.scalar(select(func.count()).select_from(ExchangeTrade)) == 1
            assert (
                db.scalar(
                    select(func.count())
                    .select_from(ExchangeOrder)
                    .where(ExchangeOrder.status == "open")
                )
                == OPEN_ORDER_COUNT - 1
            )
            assert share_class.total_shares == 100_000
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def _seed_players(
    db: Session,
) -> tuple[World, City, District, list[PlayerProfile], list[Account]]:
    world = World(
        slug="release-scale",
        name="Release Scale",
        status="active",
        ends_at=datetime.now(UTC) + timedelta(days=14),
    )
    db.add(world)
    db.flush()
    city = City(
        world_id=world.id,
        slug="koeln",
        name="Köln",
        region_key="nordrhein-westfalen",
        instance_key="scale",
        status="active",
    )
    db.add(city)
    db.flush()
    district = District(
        world_id=world.id,
        city_id=city.id,
        slug="innenstadt",
        name="Innenstadt",
        prosperity=70,
        employment=70,
        safety=70,
        authority_presence=60,
        digital_infrastructure=80,
        property_value=75,
        public_trust=65,
        media_attention=50,
        economic_activity=80,
        social_stability=70,
        map_x=50,
        map_y=50,
        map_points="0,0 100,0 100,100 0,100",
    )
    db.add(district)
    db.flush()

    profiles: list[PlayerProfile] = []
    accounts: list[Account] = []
    for index in range(PLAYER_COUNT):
        user = User(
            id=uuid_str(),
            email=f"scale-{index:03d}@example.invalid",
            password_hash="not-used-by-load-test",  # noqa: S106
            display_name=f"Scale Player {index:03d}",
            email_verified=True,
        )
        profile = PlayerProfile(
            id=uuid_str(),
            user_id=user.id,
            world_id=world.id,
            city_id=city.id,
            home_district_id=district.id,
            codename=f"Scale {index:03d}",
            archetype="operator",
            protected_until=datetime.now(UTC),
        )
        account = Account(
            id=uuid_str(),
            world_id=world.id,
            owner_type="profile",
            owner_id=profile.id,
            currency="EUR",
            balance_cents=10_000_000,
            reserved_cents=0,
        )
        db.add_all(
            (
                user,
                profile,
                ResourceBalance(
                    profile_id=profile.id,
                    cash=Decimal("100000.00"),
                    capital=Decimal("0"),
                    influence=Decimal("0"),
                    intelligence=Decimal("0"),
                    logistics_capacity=Decimal("0"),
                    personnel_capacity=Decimal("0"),
                ),
                account,
            )
        )
        profiles.append(profile)
        accounts.append(account)
    db.flush()
    return world, city, district, profiles, accounts


def _seed_companies(
    db: Session,
    *,
    world_id: str,
    district_id: str,
    profiles: list[PlayerProfile],
) -> list[Company]:
    industries = ("gastronomy", "logistics", "technology")
    companies: list[Company] = []
    for index in range(COMPANY_COUNT):
        company_id = uuid_str()
        account = Account(
            id=uuid_str(),
            world_id=world_id,
            owner_type="company",
            owner_id=company_id,
            currency="EUR",
            balance_cents=5_000_000,
        )
        company = Company(
            id=company_id,
            world_id=world_id,
            founder_profile_id=profiles[index % PLAYER_COUNT].id,
            district_id=district_id,
            account_id=account.id,
            industry=industries[index % len(industries)],
            name=f"Scale Company {index:03d}",
            normalized_name=f"scale company {index:03d}",
            status="private",
            enterprise_value_cents=20_000_000,
            revenue_cents=3_500_000,
            cost_cents=2_700_000,
            profit_cents=800_000,
            debt_cents=0,
            employees=8,
            capacity=100,
            quality=5_000,
            market_share_bps=0,
            reputation_bps=5_000,
            compliance_bps=6_500,
            innovation_bps=4_000,
            risk_bps=1_200,
            investigation_pressure_bps=0,
        )
        db.add_all((account, company))
        companies.append(company)
    db.flush()
    return companies


def _seed_order_book(
    db: Session,
    *,
    world_id: str,
    company: Company,
    profiles: list[PlayerProfile],
    profile_accounts: list[Account],
) -> tuple[ExchangeListing, ShareClass]:
    fee_transaction = LedgerTransaction(
        id=uuid_str(),
        world_id=world_id,
        actor_profile_id=company.founder_profile_id,
        transaction_type="ipo_fee",
        idempotency_key="release-scale-ipo-fee",
        reference_type="company",
        reference_id=company.id,
    )
    db.add(fee_transaction)
    db.flush()
    listing = ExchangeListing(
        id=uuid_str(),
        world_id=world_id,
        company_id=company.id,
        symbol="LOAD",
        status="active",
        total_shares=100_000,
        offered_shares=10_000,
        initial_price_cents=100,
        last_price_cents=100,
        ipo_fee_cents=0,
        fee_transaction_id=fee_transaction.id,
        idempotency_key="release-scale-listing",
    )
    db.add(listing)
    db.flush()
    share_class = ShareClass(
        id=uuid_str(),
        listing_id=listing.id,
        class_code="common",
        name="Common shares",
        total_shares=100_000,
        voting_rights_per_share=1,
        dividend_priority=0,
        tradable=True,
    )
    db.add(share_class)
    db.flush()
    db.add_all(
        (
            ShareHolding(
                id=uuid_str(),
                share_class_id=share_class.id,
                owner_type="company",
                company_id=company.id,
                quantity=99_990,
                reserved_quantity=0,
                average_cost_cents=100,
            ),
            ShareHolding(
                id=uuid_str(),
                share_class_id=share_class.id,
                owner_type="profile",
                profile_id=profiles[0].id,
                quantity=10,
                reserved_quantity=0,
                average_cost_cents=100,
            ),
        )
    )
    db.flush()

    for account in profile_accounts:
        account.reserved_cents = OPEN_ORDER_COUNT // PLAYER_COUNT * 100
    created_at = datetime.now(UTC) - timedelta(minutes=1)
    rows = []
    for index in range(OPEN_ORDER_COUNT):
        profile = profiles[index % PLAYER_COUNT]
        rows.append(
            {
                "id": uuid_str(),
                "listing_id": listing.id,
                "share_class_id": share_class.id,
                "profile_id": profile.id,
                "issuer_company_id": None,
                "owner_key": profile.id,
                "side": "buy",
                "order_type": "limit",
                "limit_price_cents": 100,
                "original_quantity": 1,
                "remaining_quantity": 1,
                "reserved_cash_cents": 100,
                "reserved_shares": 0,
                "status": "open",
                "idempotency_key": f"release-load-{index:05d}",
                "expires_at": created_at + timedelta(days=1),
                "created_at": created_at + timedelta(microseconds=index),
                "updated_at": created_at + timedelta(microseconds=index),
            }
        )
    db.execute(insert(ExchangeOrder), rows)
    return listing, share_class
