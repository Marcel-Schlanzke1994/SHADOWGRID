from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_authoritative_sources_use_agents_contract_locations() -> None:
    specification = PROJECT_ROOT / "docs" / "game-design" / "SHADOWGRID_SPEC.md"
    architecture = PROJECT_ROOT / "docs" / "architecture" / "ARCHITECTURE.md"

    assert specification.read_text(encoding="utf-8").startswith("Grundidee von SHADOWGRID")
    assert "canonical technical source of truth" in architecture.read_text(encoding="utf-8")


def test_makefile_exposes_roadmap_quality_and_operations_targets() -> None:
    makefile = (PROJECT_ROOT / "Makefile").read_text(encoding="utf-8")
    targets = set(re.findall(r"^([a-z][a-z0-9-]*):", makefile, flags=re.MULTILINE))
    required_targets = {
        "help",
        "bootstrap",
        "up",
        "down",
        "migrate",
        "seed-demo",
        "backend-lint",
        "backend-typecheck",
        "backend-test",
        "frontend-lint",
        "frontend-typecheck",
        "frontend-test",
        "e2e",
        "test",
        "review-ready",
        "backup-local",
        "restore-local",
        "verify-release",
    }

    assert required_targets <= targets
