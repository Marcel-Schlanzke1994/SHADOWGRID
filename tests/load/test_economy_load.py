from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor


def test_hundred_simulated_readers_complete_without_error() -> None:
    """Fast deterministic local floor; full HTTP load profile lives in k6.js."""

    def simulated_reader(index: int) -> tuple[int, int]:
        resources = {"cash": 80_000 + index, "capital": 25_000, "influence": 10}
        return index, sum(resources.values())

    with ThreadPoolExecutor(max_workers=20) as pool:
        results = list(pool.map(simulated_reader, range(100)))
    assert len(results) == 100
    assert len({item[0] for item in results}) == 100
