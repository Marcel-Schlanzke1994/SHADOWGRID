from __future__ import annotations

from shadowgrid.balance_simulation import (
    CARTEL_COUNT,
    COMPANY_COUNT,
    PLAYER_COUNT,
    SEASON_COUNT,
    run_simulation,
)


def test_multi_season_balance_simulation_is_deterministic_and_fair() -> None:
    first = run_simulation()
    repeated = run_simulation()

    assert first == repeated
    assert first.player_count == PLAYER_COUNT == 100
    assert first.company_count == COMPANY_COUNT == 500
    assert first.cartel_count == CARTEL_COUNT >= 5
    assert first.season_count == SEASON_COUNT >= 3
    assert first.ledger_imbalance_cents == 0
    assert first.critical_exploits == []
    assert first.strategy_spread_bps <= 2_000
    assert all(season.active_companies == 500 for season in first.seasons)
    assert all(season.cartel_dominance_bps <= 2_500 for season in first.seasons)
    assert all(season.new_to_early_wealth_bps >= 8_000 for season in first.seasons)
    assert all(season.meaningful_decisions_per_player >= 10 for season in first.seasons)
    assert all(value > 0 for value in first.investment_roi_bps.values())
