from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal
from shadowgrid.engagement import record_engagement_event
from shadowgrid.models import (
    EngagementEvent,
    GoalChoiceWindow,
    GoalInstance,
    GoalReward,
    GoalTemplate,
    PlayerOpenPlan,
    SessionSummary,
    User,
)
from sqlalchemy import func, select


def _current_goals(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.get("/api/v1/engagement/goals/current", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _goal_by_key(window: dict[str, object], template_key: str) -> dict[str, object]:
    goals = window["goals"]
    assert isinstance(goals, list)
    return next(item for item in goals if item["template_key"] == template_key)


def test_goal_choice_limit_swap_and_company_event_progress_are_idempotent(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    window = _current_goals(client, auth_headers)
    goals = window["goals"]
    assert isinstance(goals, list)
    assert len(goals) == 8
    assert window["max_choices"] == 3

    selected_ids: list[str] = []
    for index, goal in enumerate(goals[:3]):
        response = client.post(
            f"/api/v1/engagement/goals/{goal['id']}/select",
            headers={**auth_headers, "Idempotency-Key": f"goal-select-{index:04d}"},
        )
        assert response.status_code == 200, response.text
        selected_ids.append(response.json()["id"])

    over_limit = client.post(
        f"/api/v1/engagement/goals/{goals[3]['id']}/select",
        headers={**auth_headers, "Idempotency-Key": "goal-select-over-limit"},
    )
    assert over_limit.status_code == 409
    assert over_limit.json()["error"]["code"] == "engagement.goal_limit"

    replacement = client.post(
        f"/api/v1/engagement/goals/{selected_ids[1]}/swap",
        headers={**auth_headers, "Idempotency-Key": "goal-swap-0001"},
        json={"replacement_goal_id": goals[3]["id"]},
    )
    repeated = client.post(
        f"/api/v1/engagement/goals/{selected_ids[1]}/swap",
        headers={**auth_headers, "Idempotency-Key": "goal-swap-0001"},
        json={"replacement_goal_id": goals[3]["id"]},
    )
    assert replacement.status_code == repeated.status_code == 200
    assert replacement.json()["id"] == repeated.json()["id"]
    with SessionLocal() as db:
        replaced = db.get(GoalInstance, selected_ids[1])
        assert replaced is not None and replaced.status == "swapped"

    fresh_window = _current_goals(client, auth_headers)
    company_goal = _goal_by_key(fresh_window, "establish_company")
    assert company_goal["status"] == "active"

    district = client.get("/api/v1/districts", headers=auth_headers).json()[0]
    company_headers = {**auth_headers, "Idempotency-Key": "engagement-company-create"}
    payload = {
        "name": "Engagement Works",
        "industry": "technology",
        "district_id": district["id"],
    }
    created = client.post("/api/v1/companies", headers=company_headers, json=payload)
    repeated_company = client.post("/api/v1/companies", headers=company_headers, json=payload)
    assert created.status_code == repeated_company.status_code == 201

    completed = _goal_by_key(_current_goals(client, auth_headers), "establish_company")
    assert completed["status"] == "completed"
    assert completed["progress_value"] == completed["target_value"] == 1
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count(EngagementEvent.id)).where(
                    EngagementEvent.event_type == "company.founded"
                )
            )
            == 1
        )
        assert (
            db.scalar(
                select(func.count(GoalReward.id)).where(
                    GoalReward.goal_instance_id == completed["id"]
                )
            )
            == 1
        )


def test_command_center_open_plans_session_summary_and_return_briefing(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    plan_payloads = [
        ("urgent", "Review a confirmed deadline", "Open the contract", "/contracts", 90),
        ("strategic", "Continue company expansion", "Review capacity", "/companies", 70),
        ("discoverable", "Explore the current event", "Open the dossier", "/news", 40),
        ("strategic", "Compare another path", "Review the market", "/market", 20),
    ]
    created_ids: list[str] = []
    for index, (category, title, next_step, target_path, priority) in enumerate(plan_payloads):
        response = client.post(
            "/api/v1/engagement/open-plans",
            headers={**auth_headers, "Idempotency-Key": f"open-plan-{index:04d}"},
            json={
                "category": category,
                "title": title,
                "next_step": next_step,
                "target_path": target_path,
                "priority": priority,
            },
        )
        assert response.status_code == 200, response.text
        created_ids.append(response.json()["id"])

    center = client.get("/api/v1/engagement/command-center", headers=auth_headers)
    assert center.status_code == 200
    opportunities = center.json()["opportunities"]
    assert len(opportunities) == 3
    assert [item["category"] for item in opportunities] == [
        "urgent",
        "strategic",
        "discoverable",
    ]

    started = client.post(
        "/api/v1/engagement/sessions",
        headers=auth_headers,
        json={"client_session_key": "web-session-0001"},
    )
    repeated_start = client.post(
        "/api/v1/engagement/sessions",
        headers=auth_headers,
        json={"client_session_key": "web-session-0001"},
    )
    assert started.status_code == repeated_start.status_code == 200
    assert started.json()["id"] == repeated_start.json()["id"]

    completed_plan = client.patch(
        f"/api/v1/engagement/open-plans/{created_ids[0]}",
        headers={**auth_headers, "Idempotency-Key": "open-plan-complete-0001"},
        json={"status": "completed"},
    )
    assert completed_plan.status_code == 200

    finished = client.post(
        f"/api/v1/engagement/sessions/{started.json()['id']}/finish",
        headers=auth_headers,
        json={"decision_keys": ["reviewed_contract_options"]},
    )
    repeated_finish = client.post(
        f"/api/v1/engagement/sessions/{started.json()['id']}/finish",
        headers=auth_headers,
        json={"decision_keys": ["reviewed_contract_options"]},
    )
    assert finished.status_code == repeated_finish.status_code == 200
    assert finished.json()["id"] == repeated_finish.json()["id"]
    assert len(finished.json()["next_entry_points_json"]) <= 3
    assert all(item["id"] != created_ids[0] for item in finished.json()["open_plans_json"])

    briefing = client.post("/api/v1/engagement/return-briefings", headers=auth_headers)
    repeated_briefing = client.post("/api/v1/engagement/return-briefings", headers=auth_headers)
    assert briefing.status_code == repeated_briefing.status_code == 200
    assert briefing.json()["id"] == repeated_briefing.json()["id"]
    assert len(briefing.json()["entry_points_json"]) <= 3
    acknowledged = client.post(
        f"/api/v1/engagement/return-briefings/{briefing.json()['id']}/acknowledge",
        headers=auth_headers,
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged_at"] is not None
    with SessionLocal() as db:
        assert db.scalar(select(func.count(SessionSummary.id))) == 1
        assert db.scalar(select(func.count(PlayerOpenPlan.id))) == 4


def test_notification_preferences_protect_critical_and_allow_social_muting(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    preferences = client.get(
        "/api/v1/engagement/notification-preferences",
        headers=auth_headers,
    )
    assert preferences.status_code == 200
    assert [item["category"] for item in preferences.json()] == [
        "critical",
        "strategic",
        "social",
        "summary",
    ]
    payload = {
        "live_enabled": False,
        "digest_frequency": "off",
        "quiet_start_minute": 1320,
        "quiet_end_minute": 420,
        "timezone": "Europe/Berlin",
    }
    critical = client.put(
        "/api/v1/engagement/notification-preferences/critical",
        headers=auth_headers,
        json=payload,
    )
    social = client.put(
        "/api/v1/engagement/notification-preferences/social",
        headers=auth_headers,
        json=payload,
    )
    assert critical.status_code == social.status_code == 200
    assert critical.json()["live_enabled"] is True
    assert critical.json()["digest_frequency"] == "immediate"
    assert social.json()["live_enabled"] is False
    assert social.json()["digest_frequency"] == "off"

    invalid_timezone = client.put(
        "/api/v1/engagement/notification-preferences/social",
        headers=auth_headers,
        json={**payload, "timezone": "Mars/Olympus"},
    )
    assert invalid_timezone.status_code == 422
    assert invalid_timezone.json()["error"]["code"] == "engagement.timezone_invalid"


def test_guardrails_block_rollout_until_economic_and_wellbeing_evidence_pass(
    client: TestClient,
    auth_headers: dict[str, str],
    verified_user: User,
    joined_profile: dict[str, object],
) -> None:
    with SessionLocal() as db:
        user = db.get(User, verified_user.id)
        assert user is not None
        user.is_admin = True
        db.commit()

    incomplete = client.post(
        "/api/v1/engagement/admin/guardrails/evaluate",
        headers={**auth_headers, "Idempotency-Key": "guardrails-incomplete-0001"},
        json={
            "wellbeing_status": "insufficient_data",
            "technical_status": "insufficient_data",
            "accessibility_status": "insufficient_data",
            "voluntary_return_status": "insufficient_data",
            "wellbeing_signals": {
                "very_long_sessions_delta_bps": 0,
                "push_disable_delta_bps": 0,
                "obligation_reports": 0,
                "fear_motivated_return_bps": 0,
                "absence_pressure_reports": 0,
                "exhaustion_after_session_bps": 0,
            },
        },
    )
    assert incomplete.status_code == 200
    assert incomplete.json()["passed"] is False
    blocked = client.put(
        "/api/v1/engagement/admin/rollouts/engagement-foundation",
        headers=auth_headers,
        json={"cohort_bps": 0},
    )
    assert blocked.status_code == 409

    passed = client.post(
        "/api/v1/engagement/admin/guardrails/evaluate",
        headers={**auth_headers, "Idempotency-Key": "guardrails-passed-0001"},
        json={
            "wellbeing_status": "passed",
            "technical_status": "passed",
            "accessibility_status": "passed",
            "voluntary_return_status": "passed",
            "wellbeing_signals": {
                "very_long_sessions_delta_bps": 0,
                "push_disable_delta_bps": 0,
                "obligation_reports": 0,
                "fear_motivated_return_bps": 0,
                "absence_pressure_reports": 0,
                "exhaustion_after_session_bps": 0,
            },
        },
    )
    assert passed.status_code == 200, passed.text
    assert passed.json()["passed"] is True
    assert passed.json()["strategy_spread_bps"] <= 2000
    assert passed.json()["cartel_dominance_bps"] <= 2500
    assert passed.json()["newcomer_wealth_bps"] >= 8000
    assert passed.json()["ledger_imbalance_cents"] == 0

    internal = client.put(
        "/api/v1/engagement/admin/rollouts/engagement-foundation",
        headers=auth_headers,
        json={"cohort_bps": 0},
    )
    assert internal.status_code == 200
    assert internal.json()["status"] == "internal"
    skipped = client.put(
        "/api/v1/engagement/admin/rollouts/engagement-foundation",
        headers=auth_headers,
        json={"cohort_bps": 2000},
    )
    assert skipped.status_code == 409
    staged = client.put(
        "/api/v1/engagement/admin/rollouts/engagement-foundation",
        headers=auth_headers,
        json={"cohort_bps": 500},
    )
    assert staged.status_code == 200
    assert staged.json()["status"] == "staged"
    for cohort_bps in (2_000, 5_000, 10_000):
        advanced = client.put(
            "/api/v1/engagement/admin/rollouts/engagement-foundation",
            headers=auth_headers,
            json={"cohort_bps": cohort_bps},
        )
        assert advanced.status_code == 200, advanced.text
    assert advanced.json()["status"] == "active"


def test_goal_catalog_is_versioned_and_immutable(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    _current_goals(client, auth_headers)
    with SessionLocal() as db:
        template = db.scalar(select(GoalTemplate))
        assert template is not None and template.version == 1
        template.target_value += 1
        try:
            db.commit()
        except ValueError as exc:
            assert "immutable" in str(exc)
            db.rollback()
        else:
            raise AssertionError("Goal template mutation unexpectedly succeeded")


def test_parallel_initialization_returns_one_goal_window(
    client: TestClient,
    auth_headers: dict[str, str],
    joined_profile: dict[str, object],
) -> None:
    def initialize(index: int) -> tuple[int, str]:
        response = client.post(
            "/api/v1/engagement/initialize",
            headers={
                **auth_headers,
                "Idempotency-Key": f"parallel-engagement-initialize-{index}",
            },
        )
        return response.status_code, str(response.json().get("id", ""))

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(initialize, range(2)))

    assert [status for status, _ in results] == [200, 200]
    assert len({window_id for _, window_id in results}) == 1
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count(GoalChoiceWindow.id)).where(
                    GoalChoiceWindow.profile_id == str(joined_profile["id"])
                )
            )
            == 1
        )


def test_parallel_semantic_events_are_recorded_once(
    joined_profile: dict[str, object],
) -> None:
    profile_id = str(joined_profile["id"])

    def record(index: int) -> str:
        with SessionLocal() as db:
            event = record_engagement_event(
                db,
                profile_id=profile_id,
                event_type="world_event.responded",
                source_type="world_event_response",
                source_id="semantic-world-response",
                idempotency_key=f"semantic-world-response-{index}",
            )
            db.commit()
            return event.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        event_ids = list(executor.map(record, range(2)))

    assert len(set(event_ids)) == 1
    with SessionLocal() as db:
        assert (
            db.scalar(
                select(func.count(EngagementEvent.id)).where(
                    EngagementEvent.profile_id == profile_id,
                    EngagementEvent.source_id == "semantic-world-response",
                )
            )
            == 1
        )
