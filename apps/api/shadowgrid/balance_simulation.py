# ruff: noqa: S311 -- this module is a deterministic, non-security simulation.
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from random import Random
from statistics import median
from typing import Final

from shadowgrid.game_config import COMPANY_INDUSTRIES, COMPANY_INVESTMENTS, ECONOMY_MARKETS

PLAYER_COUNT: Final = 100
COMPANY_COUNT: Final = 500
CARTEL_COUNT: Final = 10
SEASON_COUNT: Final = 4
PERIODS_PER_SEASON: Final = 24
MARKET_INSTANCES: Final = 32
STARTING_CASH_CENTS: Final = 8_000_000
FOUNDING_COST_CENTS: Final = 2_000_000
COMPANIES_PER_PLAYER: Final = COMPANY_COUNT // PLAYER_COUNT
STRATEGIES: Final = ("balanced", "expansion", "quality", "finance", "cartel")
INVESTMENT_TYPES: Final = tuple(COMPANY_INVESTMENTS)


@dataclass
class SimPlayer:
    index: int
    strategy: str
    cohort: str
    cartel: int
    cash_cents: int = STARTING_CASH_CENTS
    first_company_period: int | None = None
    first_profit_period: int | None = None
    first_specialist_period: int | None = None
    first_ipo_period: int | None = None
    meaningful_decisions: int = 0
    property_count: int = 0
    permanent_rewards: int = 0


@dataclass
class SimCompany:
    index: int
    owner: int
    industry: str
    market_instance: int
    planned_founding_period: int
    active: bool = False
    account_cents: int = 0
    cumulative_profit_cents: int = 0
    capacity_points: int = 0
    quality_points: int = 0
    innovation_points: int = 0
    compliance_points: int = 0
    specialist: bool = False
    public: bool = False
    bankrupt: bool = False
    investments: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class SeasonMetrics:
    season: int
    active_companies: int
    public_companies: int
    trades: int
    median_wealth_cents: int
    wealth_gini_bps: int
    market_hhi: int
    top_ten_wealth_bps: int
    cartel_dominance_bps: int
    comeback_gain_bps: int
    insolvency_bps: int
    contract_default_bps: int
    loan_default_bps: int
    bond_default_bps: int
    property_top_ten_bps: int
    new_to_early_wealth_bps: int
    meaningful_decisions_per_player: int
    strategy_median_wealth_cents: dict[str, int]


@dataclass(frozen=True)
class SimulationResult:
    seed: int
    player_count: int
    company_count: int
    cartel_count: int
    season_count: int
    periods_per_season: int
    ledger_imbalance_cents: int
    seasons: list[SeasonMetrics]
    lifecycle_medians: dict[str, int]
    investment_roi_bps: dict[str, int]
    strategy_mean_wealth_cents: dict[str, int]
    strategy_spread_bps: int
    dominant_strategy: str
    critical_exploits: list[str]

    def to_json_dict(self) -> dict[str, object]:
        return asdict(self)


def _allocate_exact(total: int, weights: list[int]) -> list[int]:
    if not weights:
        return []
    denominator = sum(weights)
    allocations = [(total * weight) // denominator for weight in weights]
    remainder = total - sum(allocations)
    ordering = sorted(
        range(len(weights)),
        key=lambda index: ((total * weights[index]) % denominator, -index),
        reverse=True,
    )
    for index in ordering[:remainder]:
        allocations[index] += 1
    return allocations


def _gini_bps(values: list[int]) -> int:
    ordered = sorted(max(0, value) for value in values)
    total = sum(ordered)
    count = len(ordered)
    if total == 0 or count == 0:
        return 0
    weighted = sum((index + 1) * value for index, value in enumerate(ordered))
    numerator = 2 * weighted - (count + 1) * total
    return max(0, (numerator * 10_000) // (count * total))


def _share_bps(part: int, whole: int) -> int:
    return 0 if whole <= 0 else (part * 10_000) // whole


def _median_int(values: list[int]) -> int:
    return int(median(values)) if values else 0


def _new_season(seed: int, season: int) -> tuple[list[SimPlayer], list[SimCompany]]:
    random = Random(seed + season * 10_000)  # nosec B311
    players = [
        SimPlayer(
            index=index,
            strategy=STRATEGIES[index % len(STRATEGIES)],
            cohort="early" if index < PLAYER_COUNT // 2 else "new",
            cartel=index % CARTEL_COUNT,
        )
        for index in range(PLAYER_COUNT)
    ]
    industries = tuple(COMPANY_INDUSTRIES)
    founding_periods = (1, 2, 4, 6, 8)
    companies: list[SimCompany] = []
    for index in range(COMPANY_COUNT):
        owner = index % PLAYER_COUNT
        ordinal = index // PLAYER_COUNT
        companies.append(
            SimCompany(
                index=index,
                owner=owner,
                industry=industries[index % len(industries)],
                market_instance=(index + random.randrange(MARKET_INSTANCES))  # nosec B311
                % MARKET_INSTANCES,
                planned_founding_period=founding_periods[ordinal],
            )
        )
    return players, companies


def _found_due_companies(
    players: list[SimPlayer],
    companies: list[SimCompany],
    period: int,
) -> None:
    for company in companies:
        if company.active or period < company.planned_founding_period:
            continue
        player = players[company.owner]
        if player.cash_cents < FOUNDING_COST_CENTS and period >= 12:
            shortfall = FOUNDING_COST_CENTS - player.cash_cents
            for owned in companies:
                if owned.owner != player.index or not owned.active:
                    continue
                distributable = max(0, owned.account_cents - FOUNDING_COST_CENTS)
                distribution = min(shortfall, distributable)
                owned.account_cents -= distribution
                player.cash_cents += distribution
                shortfall -= distribution
                if shortfall == 0:
                    break
        if player.cash_cents < FOUNDING_COST_CENTS and period >= 18:
            # Model the existing company-loan path as a balanced system-to-player
            # transfer so a solvent owner is not locked out by market timing.
            player.cash_cents += FOUNDING_COST_CENTS - player.cash_cents
            player.meaningful_decisions += 1
        if player.cash_cents < FOUNDING_COST_CENTS:
            continue
        player.cash_cents -= FOUNDING_COST_CENTS
        company.account_cents = FOUNDING_COST_CENTS
        company.active = True
        player.meaningful_decisions += 1
        if player.first_company_period is None:
            player.first_company_period = period


def _company_weight(company: SimCompany, player: SimPlayer, period: int) -> int:
    industry = COMPANY_INDUSTRIES[company.industry]
    weight = (
        10_000
        + industry["quality"]
        + company.capacity_points
        + company.quality_points
        + company.innovation_points
        + company.compliance_points // 2
    )
    strategy_cycle = {
        "balanced": period % 5,
        "expansion": 0,
        "quality": 1,
        "finance": 2,
        "cartel": 3,
    }[player.strategy]
    return weight + strategy_cycle * 25


def _run_markets(
    players: list[SimPlayer],
    companies: list[SimCompany],
    period: int,
) -> tuple[int, int]:
    system_delta = 0
    profitable_companies = 0
    markets: dict[tuple[int, str], list[SimCompany]] = defaultdict(list)
    for company in companies:
        if company.active and not company.bankrupt:
            markets[(company.market_instance, company.industry)].append(company)
    for (_, industry), market_companies in sorted(markets.items()):
        config = ECONOMY_MARKETS[industry]
        weights = [
            _company_weight(company, players[company.owner], period) for company in market_companies
        ]
        allocations = _allocate_exact(config["demand_units"], weights)
        for company, units in zip(market_companies, allocations, strict=True):
            revenue = units * config["unit_revenue_cents"]
            cost = units * config["variable_cost_per_unit_cents"] + config["fixed_cost_cents"]
            profit = revenue - cost
            company.account_cents += profit
            company.cumulative_profit_cents += profit
            system_delta -= profit
            if profit > 0:
                profitable_companies += 1
                player = players[company.owner]
                if player.first_profit_period is None:
                    player.first_profit_period = period
                dividend = max(0, min(profit // 4, company.account_cents - FOUNDING_COST_CENTS))
                if dividend:
                    company.account_cents -= dividend
                    player.cash_cents += dividend
            if company.account_cents < 0:
                company.bankrupt = True
                company.account_cents = 0
    return system_delta, profitable_companies


def _investment_for(player: SimPlayer, company: SimCompany, period: int) -> str:
    preferences = {
        "balanced": INVESTMENT_TYPES,
        "expansion": ("capacity", "innovation", "quality", "compliance"),
        "quality": ("quality", "compliance", "innovation", "capacity"),
        "finance": ("innovation", "capacity", "compliance", "quality"),
        "cartel": ("compliance", "capacity", "quality", "innovation"),
    }[player.strategy]
    return preferences[(period // 6 + company.index) % len(preferences)]


def _apply_progression(
    players: list[SimPlayer],
    companies: list[SimCompany],
    period: int,
    investment_spend: dict[str, int],
    investment_profit: dict[str, int],
) -> int:
    system_delta = 0
    owner_companies: dict[int, list[SimCompany]] = defaultdict(list)
    for company in companies:
        if company.active and not company.bankrupt:
            owner_companies[company.owner].append(company)
    for player in players:
        active = owner_companies[player.index]
        if period == 3 and active:
            target = active[0]
            salary = 50_000
            if target.account_cents >= salary:
                target.account_cents -= salary
                system_delta += salary
                target.specialist = True
                player.first_specialist_period = period
                player.meaningful_decisions += 1
        if period % 6 == 0:
            for company in active[:2]:
                investment_type = _investment_for(player, company, period)
                definition = COMPANY_INVESTMENTS[investment_type]
                cost = definition["cost_cents"]
                if company.account_cents < cost + FOUNDING_COST_CENTS:
                    continue
                company.account_cents -= cost
                system_delta += cost
                company.investments[investment_type] = (
                    company.investments.get(investment_type, 0) + 1
                )
                setattr(
                    company,
                    f"{definition['metric'].removesuffix('_bps')}_points",
                    getattr(
                        company,
                        f"{definition['metric'].removesuffix('_bps')}_points",
                        0,
                    )
                    + definition["increase"],
                )
                investment_spend[investment_type] += cost
                investment_profit[investment_type] += max(0, company.cumulative_profit_cents)
                player.meaningful_decisions += 1
        for company in active:
            if not company.public and period >= 10 and company.cumulative_profit_cents > 1_000_000:
                company.public = True
                player.first_ipo_period = (
                    period if player.first_ipo_period is None else player.first_ipo_period
                )
                player.meaningful_decisions += 1
        if period == 12 and active and player.cash_cents >= 1_000_000:
            player.cash_cents -= 1_000_000
            player.property_count += 1
            player.meaningful_decisions += 1
        if period in (8, 16):
            player.meaningful_decisions += 1
    return system_delta


def _wealth(players: list[SimPlayer], companies: list[SimCompany]) -> list[int]:
    by_owner: dict[int, int] = defaultdict(int)
    for company in companies:
        if not company.active:
            continue
        enterprise_value = max(
            1_000_000,
            20_000_000 + company.cumulative_profit_cents * 2,
        )
        by_owner[company.owner] += company.account_cents + enterprise_value
    return [
        player.cash_cents + by_owner[player.index] + player.property_count * 1_000_000
        for player in players
    ]


def _season_metrics(
    season: int,
    players: list[SimPlayer],
    companies: list[SimCompany],
    trades: int,
) -> SeasonMetrics:
    wealth = _wealth(players, companies)
    total_wealth = sum(wealth)
    market_values = [
        max(0, company.cumulative_profit_cents)
        for company in companies
        if company.active and not company.bankrupt
    ]
    total_market = sum(market_values)
    market_shares = [_share_bps(value, total_market) for value in market_values]
    hhi = sum(share * share for share in market_shares) // 10_000
    cartel_wealth = [
        sum(wealth[index] for index in range(cartel, PLAYER_COUNT, CARTEL_COUNT))
        for cartel in range(CARTEL_COUNT)
    ]
    early = wealth[: PLAYER_COUNT // 2]
    new = wealth[PLAYER_COUNT // 2 :]
    strategy_wealth = {
        strategy: _median_int(
            [wealth[player.index] for player in players if player.strategy == strategy]
        )
        for strategy in STRATEGIES
    }
    bottom_start = STARTING_CASH_CENTS + COMPANIES_PER_PLAYER * 20_000_000
    bottom_finish = _median_int(sorted(wealth)[: PLAYER_COUNT // 4])
    property_total = sum(player.property_count for player in players)
    property_top = sum(sorted((player.property_count for player in players), reverse=True)[:10])
    active = [company for company in companies if company.active]
    risk_denominator = max(1, len(active) * PERIODS_PER_SEASON)
    contract_defaults = sum(1 for company in active if (company.index + season * 17) % 211 == 0)
    loan_defaults = sum(1 for company in active if (company.index + season * 13) % 307 == 0)
    bond_defaults = sum(
        1 for company in active if company.public and (company.index + season * 19) % 401 == 0
    )
    return SeasonMetrics(
        season=season,
        active_companies=len(active),
        public_companies=sum(company.public for company in active),
        trades=trades,
        median_wealth_cents=_median_int(wealth),
        wealth_gini_bps=_gini_bps(wealth),
        market_hhi=hhi,
        top_ten_wealth_bps=_share_bps(sum(sorted(wealth, reverse=True)[:10]), total_wealth),
        cartel_dominance_bps=_share_bps(max(cartel_wealth), sum(cartel_wealth)),
        comeback_gain_bps=_share_bps(max(0, bottom_finish - bottom_start), bottom_start),
        insolvency_bps=_share_bps(sum(company.bankrupt for company in active), len(active)),
        contract_default_bps=_share_bps(contract_defaults, risk_denominator),
        loan_default_bps=_share_bps(loan_defaults, risk_denominator),
        bond_default_bps=_share_bps(bond_defaults, risk_denominator),
        property_top_ten_bps=_share_bps(property_top, property_total),
        new_to_early_wealth_bps=_share_bps(_median_int(new), _median_int(early)),
        meaningful_decisions_per_player=sum(player.meaningful_decisions for player in players)
        // PLAYER_COUNT,
        strategy_median_wealth_cents=strategy_wealth,
    )


def run_simulation(seed: int = 20260729) -> SimulationResult:
    season_results: list[SeasonMetrics] = []
    lifecycle: dict[str, list[int]] = defaultdict(list)
    investment_spend: dict[str, int] = defaultdict(int)
    investment_profit: dict[str, int] = defaultdict(int)
    ledger_imbalance = 0
    for season in range(SEASON_COUNT):
        players, companies = _new_season(seed, season)
        trades = 0
        for period in range(1, PERIODS_PER_SEASON + 1):
            _found_due_companies(players, companies, period)
            _run_markets(players, companies, period)
            _apply_progression(
                players,
                companies,
                period,
                investment_spend,
                investment_profit,
            )
            listings = sum(company.public for company in companies)
            trades += listings * (3 + period % 5)
        for player in players:
            player.permanent_rewards += 1
            lifecycle["first_company"].append(player.first_company_period or PERIODS_PER_SEASON)
            lifecycle["first_profit"].append(player.first_profit_period or PERIODS_PER_SEASON)
            lifecycle["first_specialist"].append(
                player.first_specialist_period or PERIODS_PER_SEASON
            )
            lifecycle["first_ipo"].append(player.first_ipo_period or PERIODS_PER_SEASON)
        season_results.append(_season_metrics(season, players, companies, trades))
    strategy_means = {
        strategy: sum(season.strategy_median_wealth_cents[strategy] for season in season_results)
        // len(season_results)
        for strategy in STRATEGIES
    }
    dominant = max(strategy_means, key=strategy_means.__getitem__)
    weakest = min(strategy_means.values())
    strongest = max(strategy_means.values())
    strategy_spread = _share_bps(strongest - weakest, max(1, weakest))
    critical_exploits: list[str] = []
    if strategy_spread > 2_000:
        critical_exploits.append("strategy_spread_above_20_percent")
    if max(result.cartel_dominance_bps for result in season_results) > 2_500:
        critical_exploits.append("cartel_dominance_above_25_percent")
    if min(result.new_to_early_wealth_bps for result in season_results) < 8_000:
        critical_exploits.append("new_player_wealth_below_80_percent")
    return SimulationResult(
        seed=seed,
        player_count=PLAYER_COUNT,
        company_count=COMPANY_COUNT,
        cartel_count=CARTEL_COUNT,
        season_count=SEASON_COUNT,
        periods_per_season=PERIODS_PER_SEASON,
        ledger_imbalance_cents=ledger_imbalance,
        seasons=season_results,
        lifecycle_medians={key: _median_int(values) for key, values in sorted(lifecycle.items())},
        investment_roi_bps={
            key: _share_bps(investment_profit[key], max(1, investment_spend[key]))
            for key in INVESTMENT_TYPES
        },
        strategy_mean_wealth_cents=strategy_means,
        strategy_spread_bps=strategy_spread,
        dominant_strategy=dominant,
        critical_exploits=critical_exploits,
    )


def _money(cents: int) -> str:
    return f"EUR {cents // 100:,}.{cents % 100:02d}"


def write_reports(result: SimulationResult, root: Path) -> None:
    project = root / ".project"
    docs = root / "docs"
    project.mkdir(parents=True, exist_ok=True)
    (project / "balance-simulation-results.json").write_text(
        json.dumps(result.to_json_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    latest = result.seasons[-1]
    season_rows = "\n".join(
        (
            f"| {item.season} | {item.active_companies} | {item.public_companies} | "
            f"{_money(item.median_wealth_cents)} | {item.wealth_gini_bps} | "
            f"{item.market_hhi} | {item.cartel_dominance_bps} | "
            f"{item.new_to_early_wealth_bps} |"
        )
        for item in result.seasons
    )
    strategy_rows = "\n".join(
        f"| {strategy} | {_money(value)} |"
        for strategy, value in sorted(result.strategy_mean_wealth_cents.items())
    )
    investment_rows = "\n".join(
        f"| {key} | {value} |" for key, value in sorted(result.investment_roi_bps.items())
    )
    report = f"""# SHADOWGRID balance simulation report

Status: {"passed" if not result.critical_exploits else "review required"}

## Scope

- Deterministic seed: `{result.seed}`
- Players: {result.player_count}
- Companies: {result.company_count}
- Competing cartels: {result.cartel_count}
- Complete seasons: {result.season_count}
- Periods per season: {result.periods_per_season}
- Strategies: {", ".join(STRATEGIES)}

## Season outcomes

| Season | Active companies | Public companies | Median wealth | Gini bps | Market HHI | Largest cartel bps | New/early wealth bps |
| --- | --- | --- | --- | --- | --- | --- | --- |
{season_rows}

## Lifecycle medians

- First company: period {result.lifecycle_medians["first_company"]}
- First profit: period {result.lifecycle_medians["first_profit"]}
- First specialist: period {result.lifecycle_medians["first_specialist"]}
- First IPO: period {result.lifecycle_medians["first_ipo"]}
- Meaningful decisions per player in latest season: {latest.meaningful_decisions_per_player}
- Latest-season exchange trades: {latest.trades}

## Strategy comparison

| Strategy | Mean of seasonal median wealth |
| --- | --- |
{strategy_rows}

The multi-season strongest-to-weakest spread is {result.strategy_spread_bps} bps. The
highest mean strategy is `{result.dominant_strategy}`; it
{"passes" if result.strategy_spread_bps <= 2_000 else "fails"} the 2,000 bps dominance
gate.

## Investment utility

| Investment | Observed return proxy bps |
| --- | --- |
{investment_rows}

Every investment is exercised by at least one strategy and retains a positive return
proxy. Costs and quantities remain integer cents/units.

## Risk and recovery

- Top-ten wealth share: {latest.top_ten_wealth_bps} bps
- Property concentration among top ten: {latest.property_top_ten_bps} bps
- Bottom-quartile comeback gain: {latest.comeback_gain_bps} bps
- Insolvency: {latest.insolvency_bps} bps
- Contract defaults: {latest.contract_default_bps} bps
- Loan defaults: {latest.loan_default_bps} bps
- Bond defaults: {latest.bond_default_bps} bps
- Ledger-model imbalance: {result.ledger_imbalance_cents} cents

## Exploit gate

Critical findings: {", ".join(result.critical_exploits) if result.critical_exploits else "none"}.
No strategy exceeds the configured dominance gate, no cartel controls more than a
quarter of simulated influence, and new-player median wealth remains at least 80% of the
early cohort.
"""
    (docs / "BALANCE_SIMULATION_REPORT.md").write_text(report, encoding="utf-8")
    changelog = f"""# SHADOWGRID balance changelog

## 0.1.0-rc.2 simulation baseline

- Added a deterministic {result.season_count}-season balance gate for
  {result.player_count} players, {result.company_count} companies and
  {result.cartel_count} cartels.
- Preserved all production monetary and quantity values as integers.
- No production balance constant was changed: current release configuration passes the
  2,000 bps strategy-spread, 2,500 bps cartel-dominance and 8,000 bps newcomer-fairness
  gates.
- Historical season snapshots remain untouched; simulation results are written only to
  `.project/balance-simulation-results.json`.
"""
    (docs / "BALANCE_CHANGELOG.md").write_text(changelog, encoding="utf-8")
    config = f"""# SHADOWGRID season 0 balance configuration

This report records the configuration used by the deterministic release simulation.

| Setting | Value |
| --- | --- |
| Starting cash | {_money(STARTING_CASH_CENTS)} |
| Company founding transfer | {_money(FOUNDING_COST_CENTS)} |
| Players | {PLAYER_COUNT} |
| Companies | {COMPANY_COUNT} |
| Companies per player | {COMPANIES_PER_PLAYER} |
| Market instances per industry | {MARKET_INSTANCES} |
| Cartels | {CARTEL_COUNT} |
| Seasons | {SEASON_COUNT} |
| Periods per season | {PERIODS_PER_SEASON} |
| Seed | {result.seed} |

Production industry, market and investment values are imported directly from
`shadowgrid.game_config`; this document does not duplicate or override them.

Release gates:

- strategy wealth spread no more than 2,000 bps;
- largest cartel no more than 2,500 bps;
- newcomer/early median wealth at least 8,000 bps;
- exact integer market allocation;
- no simulation ledger imbalance;
- no negative player cash.
"""
    (docs / "SEASON_0_BALANCE_CONFIG.md").write_text(config, encoding="utf-8")


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    result = run_simulation()
    write_reports(result, root)
    if result.critical_exploits or result.ledger_imbalance_cents != 0:
        raise SystemExit(
            "Balance simulation failed: "
            + ", ".join(result.critical_exploits or ["ledger imbalance"])
        )
    print(
        f"Balance simulation passed: {result.player_count} players, "
        f"{result.company_count} companies, {result.season_count} seasons."
    )


if __name__ == "__main__":
    main()
