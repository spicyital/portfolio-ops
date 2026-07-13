"""Deterministic incident state machine for consecutive public failures."""

from __future__ import annotations

import hashlib
from collections import defaultdict

from .models import CheckResult


def build_incidents(
    records: list[CheckResult], thresholds: dict[str, int]
) -> list[dict[str, object]]:
    """Create one incident per failure episode and resolve it after two successes."""
    grouped: dict[str, list[CheckResult]] = defaultdict(list)
    for record in records:
        grouped[record.target_name].append(record)
    incidents: list[dict[str, object]] = []
    for target, checks in sorted(grouped.items()):
        failures: list[CheckResult] = []
        incident: dict[str, object] | None = None
        recoveries = 0
        for check in sorted(checks, key=lambda item: item.checked_at):
            if check.success:
                failures = []
                if incident and incident["status"] == "active":
                    recoveries += 1
                    incident["recovery_check_count"] = recoveries
                    if recoveries >= 2:
                        incident["status"] = "resolved"
                        incident["resolved_at"] = check.checked_at
                        incidents.append(incident)
                        incident = None
                        recoveries = 0
                continue
            recoveries = 0
            failures.append(check)
            if incident is None and len(failures) >= thresholds.get(target, 2):
                first = failures[0]
                incident = {
                    "incident_id": hashlib.sha256(
                        f"{target}|{first.checked_at}".encode()
                    ).hexdigest()[:16],
                    "target": target,
                    "started_at": first.checked_at,
                    "detected_at": check.checked_at,
                    "resolved_at": None,
                    "status": "active",
                    "failure_reason": check.error_type or "http_status",
                    "failed_check_count": len(failures),
                    "recovery_check_count": 0,
                }
            elif incident is not None:
                incident["failed_check_count"] = int(incident["failed_check_count"]) + 1
        if incident is not None:
            incidents.append(incident)
    return incidents
