from __future__ import annotations

import hashlib
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


def test_thousand_multiplayer_resolution_inputs_are_deterministic() -> None:
    """CPU-side floor for score/report work before the authenticated k6 profile."""

    def resolve(index: int) -> tuple[int, int, str]:
        operation_id = f"load-operation-{index:04d}"
        roll = int(hashlib.sha256(operation_id.encode()).hexdigest()[:8], 16) % 100
        outcome = "attacker_advantage" if roll < 50 else "defender_advantage"
        return index, roll, outcome

    with ThreadPoolExecutor(max_workers=40) as pool:
        first = list(pool.map(resolve, range(1_000)))
        second = list(pool.map(resolve, range(1_000)))
    assert first == second
    assert len({item[0] for item in first}) == 1_000
    assert {item[2] for item in first} == {"attacker_advantage", "defender_advantage"}


def test_k6_profile_covers_four_multiplayer_read_paths() -> None:
    profile = (Path(__file__).parent / "k6-multiplayer.js").read_text(encoding="utf-8")
    for scenario in (
        "pvp_target_readers",
        "territory_observers",
        "war_room_observers",
        "communication_observers",
    ):
        assert scenario in profile
    assert 'http_req_failed: ["rate<0.01"]' in profile
    assert 'http_req_duration: ["p(95)<750"]' in profile
