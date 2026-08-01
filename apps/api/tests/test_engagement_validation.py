from __future__ import annotations

from fastapi.testclient import TestClient
from shadowgrid.database import SessionLocal, engine
from shadowgrid.models import EngagementMetricDaily, User
from sqlalchemy import inspect, select


def _wellbeing_signals(**overrides: int) -> dict[str, int]:
    signals = {
        "very_long_sessions_delta_bps": 0,
        "push_disable_delta_bps": 0,
        "obligation_reports": 0,
        "fear_motivated_return_bps": 0,
        "absence_pressure_reports": 0,
        "exhaustion_after_session_bps": 0,
    }
    signals.update(overrides)
    return signals


def test_rollout_rejects_negative_wellbeing_signals_even_when_status_claims_passed(
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
    evaluation = client.post(
        "/api/v1/engagement/admin/guardrails/evaluate",
        headers={**auth_headers, "Idempotency-Key": "wellbeing-signal-failure"},
        json={
            "wellbeing_status": "passed",
            "technical_status": "passed",
            "accessibility_status": "passed",
            "voluntary_return_status": "passed",
            "wellbeing_signals": _wellbeing_signals(
                very_long_sessions_delta_bps=1_001,
                absence_pressure_reports=1,
            ),
        },
    )
    assert evaluation.status_code == 200, evaluation.text
    assert evaluation.json()["passed"] is False
    assert "wellbeing_signal_very_long_sessions_delta_bps" in evaluation.json()["reasons_json"]
    assert "wellbeing_signal_absence_pressure_reports" in evaluation.json()["reasons_json"]
    rollout = client.put(
        "/api/v1/engagement/admin/rollouts/validation-test",
        headers=auth_headers,
        json={"cohort_bps": 0},
    )
    assert rollout.status_code == 409
    assert str(joined_profile["id"])


def test_daily_metrics_are_admin_only_aggregate_k_anonymous_and_immutable(
    client: TestClient,
    auth_headers: dict[str, str],
    verified_user: User,
    joined_profile: dict[str, object],
) -> None:
    unauthorized = client.post(
        "/api/v1/engagement/admin/metrics/daily",
        headers={**auth_headers, "Idempotency-Key": "metrics-unauthorized"},
        json={"survey_response_count": 0},
    )
    assert unauthorized.status_code == 403
    with SessionLocal() as db:
        user = db.get(User, verified_user.id)
        assert user is not None
        user.is_admin = True
        db.commit()

    district = client.get("/api/v1/districts", headers=auth_headers).json()[0]
    company = client.post(
        "/api/v1/companies",
        headers={**auth_headers, "Idempotency-Key": "metrics-company"},
        json={
            "name": "Aggregate Metrics Works",
            "industry": "technology",
            "district_id": district["id"],
        },
    )
    assert company.status_code == 201
    created = client.post(
        "/api/v1/engagement/admin/metrics/daily",
        headers={**auth_headers, "Idempotency-Key": "metrics-daily-one"},
        json={
            "satisfaction_bps": 8_000,
            "fairness_bps": 9_000,
            "survey_response_count": 4,
        },
    )
    repeated = client.post(
        "/api/v1/engagement/admin/metrics/daily",
        headers={**auth_headers, "Idempotency-Key": "metrics-daily-one"},
        json={
            "satisfaction_bps": 8_000,
            "fairness_bps": 9_000,
            "survey_response_count": 4,
        },
    )
    assert created.status_code == repeated.status_code == 200, created.text
    assert created.json()["id"] == repeated.json()["id"]
    assert created.json()["profile_count"] == 1
    assert created.json()["meaningful_decision_count"] >= 1
    assert created.json()["story_progress_count"] >= 1
    assert created.json()["satisfaction_bps"] is None
    assert created.json()["fairness_bps"] is None
    assert created.json()["survey_response_count"] == 4

    listed = client.get("/api/v1/engagement/admin/metrics/daily", headers=auth_headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == created.json()["id"]
    columns = {item["name"] for item in inspect(engine).get_columns("engagement_metrics_daily")}
    assert "profile_id" not in columns
    assert "user_id" not in columns
    assert "device_id" not in columns
    assert "advertising_id" not in columns
    assert "chat_content" not in columns

    with SessionLocal() as db:
        metric = db.scalar(select(EngagementMetricDaily))
        assert metric is not None
        metric.profile_count += 1
        try:
            db.commit()
        except ValueError:
            db.rollback()
        else:
            raise AssertionError("Daily aggregate metric mutation unexpectedly succeeded")
    assert str(joined_profile["id"])
