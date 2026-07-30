from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from shadowgrid.config import get_settings
from shadowgrid.database import SessionLocal
from shadowgrid.models import (
    Account,
    AccountLedgerEntry,
    Company,
    CompanyEconomyReport,
    CompanyOwnership,
    LedgerTransaction,
    MarketEconomyReport,
    SeedRun,
    ShareClass,
    ShareHolding,
)


@dataclass(frozen=True)
class IntegrityFinding:
    code: str
    detail: str


def validate_release_invariants(db: Session) -> list[IntegrityFinding]:
    findings: list[IntegrityFinding] = []
    accounts = list(db.scalars(select(Account)))
    entries = list(
        db.scalars(
            select(AccountLedgerEntry).order_by(
                AccountLedgerEntry.created_at,
                AccountLedgerEntry.id,
            )
        )
    )
    transaction_sums: dict[str, int] = defaultdict(int)
    transaction_counts: dict[str, int] = defaultdict(int)
    latest_entry: dict[str, AccountLedgerEntry] = {}
    for entry in entries:
        transaction_sums[entry.transaction_id] += entry.amount_cents
        transaction_counts[entry.transaction_id] += 1
        latest_entry[entry.account_id] = entry
    for transaction_id in db.scalars(select(LedgerTransaction.id)):
        if transaction_counts[transaction_id] < 2 or transaction_sums[transaction_id] != 0:
            findings.append(
                IntegrityFinding(
                    "ledger.unbalanced",
                    f"Transaction {transaction_id} is not a balanced multi-entry transfer",
                )
            )
    for account in accounts:
        if account.owner_type != "system" and account.balance_cents < 0:
            findings.append(
                IntegrityFinding(
                    "account.negative",
                    f"Account {account.id} has a negative non-system balance",
                )
            )
        if account.reserved_cents < 0 or (
            account.owner_type != "system" and account.reserved_cents > account.balance_cents
        ):
            findings.append(
                IntegrityFinding(
                    "account.reservation",
                    f"Account {account.id} has an invalid reservation",
                )
            )
        latest = latest_entry.get(account.id)
        if latest is not None and latest.balance_after_cents != account.balance_cents:
            findings.append(
                IntegrityFinding(
                    "ledger.account_projection",
                    f"Account {account.id} differs from its latest ledger entry",
                )
            )

    ownership_totals: dict[str, int] = {
        str(company_id): int(total or 0)
        for company_id, total in db.execute(
            select(
                CompanyOwnership.company_id,
                func.sum(CompanyOwnership.ownership_bps),
            ).group_by(CompanyOwnership.company_id)
        )
    }
    for company in db.scalars(select(Company).where(Company.status == "private")):
        if int(ownership_totals.get(company.id, 0)) != 10_000:
            findings.append(
                IntegrityFinding(
                    "ownership.private_total",
                    f"Private company {company.id} ownership does not total 10,000 bps",
                )
            )

    holding_totals: dict[str, int] = {
        str(share_class_id): int(total or 0)
        for share_class_id, total in db.execute(
            select(
                ShareHolding.share_class_id,
                func.sum(ShareHolding.quantity),
            ).group_by(ShareHolding.share_class_id)
        )
    }
    for share_class in db.scalars(select(ShareClass)):
        if int(holding_totals.get(share_class.id, 0)) != share_class.total_shares:
            findings.append(
                IntegrityFinding(
                    "shares.supply",
                    f"Share class {share_class.id} holdings differ from fixed supply",
                )
            )

    report_totals = {
        str(row[0]): (int(row[1] or 0), int(row[2] or 0))
        for row in db.execute(
            select(
                CompanyEconomyReport.market_report_id,
                func.sum(CompanyEconomyReport.allocated_units),
                func.sum(CompanyEconomyReport.market_share_bps),
            ).group_by(CompanyEconomyReport.market_report_id)
        )
    }
    for report in db.scalars(select(MarketEconomyReport)):
        allocated, share_bps = report_totals.get(report.id, (0, 0))
        if allocated != report.allocated_units or not 0 <= share_bps <= 10_000:
            findings.append(
                IntegrityFinding(
                    "market.allocation",
                    f"Market report {report.id} allocation projection is inconsistent",
                )
            )

    if db.bind is not None and db.bind.dialect.name == "sqlite":
        for row in db.execute(text("PRAGMA foreign_key_check")):
            findings.append(
                IntegrityFinding(
                    "database.foreign_key",
                    f"SQLite foreign-key violation in {row[0]} row {row[1]}",
                )
            )
    settings = get_settings()
    seed_run = db.scalar(
        select(SeedRun).where(
            SeedRun.seed_key == "demo",
            SeedRun.version == settings.seed_version,
        )
    )
    if seed_run is None:
        findings.append(
            IntegrityFinding(
                "seed.contract_missing",
                f"Configured demo seed version {settings.seed_version} has not been applied",
            )
        )
    elif seed_run.random_seed != settings.demo_random_seed:
        findings.append(
            IntegrityFinding(
                "seed.contract_mismatch",
                "Persisted demo random seed differs from the configured release contract",
            )
        )
    return findings


def main() -> None:
    with SessionLocal() as db:
        findings = validate_release_invariants(db)
    if findings:
        for finding in findings:
            print(f"{finding.code}: {finding.detail}")
        raise SystemExit(1)
    print("Release data invariants passed.")


if __name__ == "__main__":
    main()
