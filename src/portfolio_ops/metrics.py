"""Observed availability and latency aggregates for sparse scheduled checks."""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from .models import CheckResult


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[max(0, math.ceil(percentile * len(ordered)) - 1)]


def _availability(records: list[CheckResult], now: datetime, hours: int) -> float | None:
    window = [
        record
        for record in records
        if datetime.fromisoformat(record.checked_at.replace("Z", "+00:00"))
        >= now - timedelta(hours=hours)
    ]
    if len(window) < 2:
        return None
    first_observation = min(
        datetime.fromisoformat(record.checked_at.replace("Z", "+00:00")) for record in window
    )
    if hours > 24 and first_observation > now - timedelta(hours=hours - 24):
        return None
    return round(100 * sum(record.success for record in window) / len(window), 1)


def build_service_metrics(
    records: list[CheckResult], now: datetime | None = None
) -> dict[str, dict[str, object]]:
    """Build labelled observed metrics and keep sparse window rates null."""
    current = datetime.now(UTC) if now is None else now.astimezone(UTC)
    grouped: dict[str, list[CheckResult]] = defaultdict(list)
    for record in records:
        grouped[record.target_name].append(record)
    output: dict[str, dict[str, object]] = {}
    for name, checks in grouped.items():
        checks.sort(key=lambda item: item.checked_at)
        latest = checks[-1]
        success_streak = failure_streak = 0
        for record in reversed(checks):
            if record.success and failure_streak == 0:
                success_streak += 1
            elif not record.success and success_streak == 0:
                failure_streak += 1
            else:
                break
        latencies = [record.response_time_ms for record in checks]
        output[name] = {
            "target_name": name,
            "latest": latest.to_dict(),
            "total_checks": len(checks),
            "successful_checks": sum(record.success for record in checks),
            "failed_checks": sum(not record.success for record in checks),
            "success_streak": success_streak,
            "failure_streak": failure_streak,
            "availability_24h": _availability(checks, current, 24),
            "availability_7d": _availability(checks, current, 24 * 7),
            "availability_30d": _availability(checks, current, 24 * 30),
            "p50_latency_ms": _percentile(latencies, 0.5),
            "p95_latency_ms": _percentile(latencies, 0.95),
            "max_latency_ms": max(latencies) if latencies else None,
            "average_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
            "tls_days_remaining": latest.tls_days_remaining,
            "security_header_score": latest.security_score,
            "last_successful_check": next(
                (item.checked_at for item in reversed(checks) if item.success), None
            ),
            "last_failed_check": next(
                (item.checked_at for item in reversed(checks) if not item.success), None
            ),
            "observation_interval": "scheduled checks; not continuous monitoring",
        }
    return dict(sorted(output.items()))
