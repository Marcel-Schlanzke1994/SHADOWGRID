from __future__ import annotations

from datetime import UTC, datetime

from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.models import (
    Account,
    AccountLedgerEntry,
    LedgerTransaction,
    SeedRun,
    World,
    uuid_str,
)
from shadowgrid.release_checks import validate_release_invariants
from sqlalchemy import select


def _record_current_seed(*, random_seed: int | None = None) -> None:
    settings = get_settings()
    with SessionLocal() as db:
        db.add(
            SeedRun(
                seed_key="demo",
                version=settings.seed_version,
                random_seed=(settings.demo_random_seed if random_seed is None else random_seed),
                applied_at=datetime.now(UTC),
            )
        )
        db.commit()


def test_release_invariant_check_accepts_clean_database() -> None:
    _record_current_seed()
    with SessionLocal() as db:
        assert validate_release_invariants(db) == []


def test_release_invariant_check_detects_unbalanced_ledger() -> None:
    with SessionLocal() as db:
        world = db.scalar(select(World))
        assert world is not None
        account = Account(
            world_id=world.id,
            owner_type="system",
            owner_id="release-check-system",
            balance_cents=100,
        )
        transaction = LedgerTransaction(
            world_id=world.id,
            transaction_type="release_check",
            idempotency_key="release-check-unbalanced",
            reference_type="release_check",
            reference_id=uuid_str(),
        )
        db.add_all((account, transaction))
        db.flush()
        db.add(
            AccountLedgerEntry(
                transaction_id=transaction.id,
                account_id=account.id,
                amount_cents=100,
                balance_after_cents=100,
            )
        )
        db.commit()

        findings = validate_release_invariants(db)

    assert "ledger.unbalanced" in {finding.code for finding in findings}


def test_release_invariant_check_detects_seed_contract_mismatch() -> None:
    settings = get_settings()
    _record_current_seed(random_seed=settings.demo_random_seed + 1)

    with SessionLocal() as db:
        findings = validate_release_invariants(db)

    assert "seed.contract_mismatch" in {finding.code for finding in findings}


def test_release_invariant_check_detects_missing_seed_contract() -> None:
    with SessionLocal() as db:
        findings = validate_release_invariants(db)

    assert "seed.contract_missing" in {finding.code for finding in findings}
