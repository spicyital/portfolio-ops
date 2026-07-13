"""Build versioned public monitoring outputs from detailed check history."""

from __future__ import annotations

import json
from pathlib import Path

from .incidents import build_incidents
from .metrics import build_service_metrics
from .models import CheckResult, Target
from .storage import atomic_write_text


def write_observability_outputs(
    data_dir: Path, checks: list[CheckResult], targets: list[Target]
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    """Write deterministic aggregate metrics/incidents without raw network material."""
    metrics = build_service_metrics(checks)
    incidents = build_incidents(
        checks, {target.name: target.failure_threshold for target in targets}
    )
    atomic_write_text(
        data_dir / "service-metrics.json",
        json.dumps(
            {"schema_version": 1, "services": list(metrics.values())}, indent=2, sort_keys=True
        )
        + "\n",
    )
    atomic_write_text(
        data_dir / "incidents.json",
        json.dumps({"schema_version": 1, "incidents": incidents}, indent=2, sort_keys=True) + "\n",
    )
    return metrics, incidents
