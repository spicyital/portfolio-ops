from __future__ import annotations

import json
from datetime import UTC, datetime

from portfolio_ops.dashboard import build_dashboard
from portfolio_ops.incidents import build_incidents
from portfolio_ops.metrics import build_service_metrics
from portfolio_ops.models import CheckResult
from portfolio_ops.storage import append_detailed_checks, load_detailed_checks


def check(
    checked_at: str,
    success: bool = True,
    latency: int = 100,
    name: str = "wrepo",
) -> CheckResult:
    return CheckResult(
        checked_date=checked_at[:10],
        checked_at=checked_at,
        target_name=name,
        url="https://wrepo.net",
        status_code=200 if success else 503,
        response_time_ms=latency,
        success=success,
        error_type="" if success else "http_status",
        check_id=f"{name}-{checked_at}",
        dns_resolved=True,
        tls_valid=True,
        tls_days_remaining=45,
        security_score=80,
    )


def test_jsonl_storage_migrates_details_deduplicates_and_compacts(tmp_path):
    path = tmp_path / "checks.jsonl"
    old = check("2025-01-01T00:00:00Z")
    recent = check("2026-07-13T00:00:00Z")
    assert append_detailed_checks(
        path, [old, recent], retention_days=90, now=datetime(2026, 7, 13, tzinfo=UTC)
    )
    assert load_detailed_checks(path) == [recent]
    assert (
        append_detailed_checks(
            path, [recent], retention_days=90, now=datetime(2026, 7, 13, tzinfo=UTC)
        )
        is False
    )


def test_metrics_calculate_streaks_latency_and_insufficient_history():
    records = [
        check("2026-07-12T00:00:00Z", False, 300),
        check("2026-07-13T00:00:00Z", True, 100),
        check("2026-07-13T06:00:00Z", True, 200),
    ]
    metrics = build_service_metrics(records, now=datetime(2026, 7, 13, 7, tzinfo=UTC))["wrepo"]
    assert metrics["success_streak"] == 2
    assert metrics["failure_streak"] == 0
    assert metrics["p50_latency_ms"] == 200
    assert metrics["availability_7d"] is None


def test_incident_requires_threshold_and_recovers_after_two_successes():
    records = [
        check("2026-07-13T00:00:00Z", False),
        check("2026-07-13T06:00:00Z", False),
        check("2026-07-13T12:00:00Z", True),
        check("2026-07-13T18:00:00Z", True),
    ]
    incidents = build_incidents(records, {"wrepo": 2})
    assert len(incidents) == 1
    assert incidents[0]["status"] == "resolved"
    assert incidents[0]["failed_check_count"] == 2


def test_dashboard_build_is_sanitized_and_contains_no_local_paths_or_body(tmp_path):
    metrics = build_service_metrics(
        [check("2026-07-13T00:00:00Z")], now=datetime(2026, 7, 13, tzinfo=UTC)
    )
    output = tmp_path / "site"
    build_dashboard(metrics, [], output)
    payload = json.loads((output / "status.json").read_text(encoding="utf-8"))
    assert payload["services"][0]["target_name"] == "wrepo"
    assert "C:\\" not in (output / "index.html").read_text(encoding="utf-8")
    assert "response_body" not in json.dumps(payload)
