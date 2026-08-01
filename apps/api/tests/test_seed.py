from __future__ import annotations

import importlib

import pytest
from shadowgrid.config import Settings
from shadowgrid.seed import build_organization_membership_seed_plan


def test_demo_membership_plan_assigns_each_profile_once() -> None:
    eligible_profile_ids = [f"profile-{index:02d}" for index in range(20)]
    organization_ids = [f"organization-{index}" for index in range(4)]

    plan = build_organization_membership_seed_plan(
        eligible_profile_ids,
        organization_ids,
        director_profile_id="profile-01",
        member_profile_id="profile-00",
    )

    assert len(plan) == len(eligible_profile_ids)
    assert len({profile_id for profile_id, _, _ in plan}) == len(plan)
    assert ("profile-01", "organization-0", "director") in plan
    assert ("profile-00", "organization-0", "member") in plan
    director_organizations = {
        organization_id for _, organization_id, role in plan if role == "director"
    }
    assert director_organizations == set(organization_ids)


def test_demo_seed_refuses_production_even_when_flag_is_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seed_module = importlib.import_module("shadowgrid.seed")
    settings = Settings(
        app_env="production",
        local_demo_mode=True,
        secret_key="test-secret-key",
        refresh_pepper="test-refresh-pepper",
        seed_secret="test-seed-secret",
        metrics_token="test-metrics-token-with-at-least-thirty-two-characters",
        web_origins=["https://shadowgrid.example"],
        smtp_host="smtp.shadowgrid.example",
        smtp_from="noreply@shadowgrid.example",
    )
    monkeypatch.setattr(seed_module, "get_settings", lambda: settings)

    with pytest.raises(RuntimeError, match="disabled"):
        seed_module.seed()
