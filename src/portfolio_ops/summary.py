"""Create privacy-safe latest-status JSON and an evidence-based Markdown summary."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from .models import CheckResult
from .storage import atomic_write_text


def latest_by_target(results: list[CheckResult]) -> list[CheckResult]:
    """Return the newest result for every target in stable name order."""
    latest: dict[str, CheckResult] = {}
    for result in results:
        current = latest.get(result.target_name)
        if current is None or result.checked_at > current.checked_at:
            latest[result.target_name] = result
    return [latest[name] for name in sorted(latest)]


def _rate(results: list[CheckResult], latest_date: date, days: int) -> float | None:
    first_date = latest_date.fromordinal(latest_date.toordinal() - days + 1)
    window = [
        result
        for result in results
        if first_date <= date.fromisoformat(result.checked_date) <= latest_date
    ]
    if len({result.checked_date for result in window}) < days:
        return None
    return 100 * sum(result.success for result in window) / len(window)


def _render_target(result: CheckResult, records: list[CheckResult]) -> list[str]:
    latest_date = date.fromisoformat(result.checked_date)
    lines = [
        f"### {result.target_name}",
        "",
        f"- Current public status: {'available' if result.success else 'unavailable'}",
        f"- Last checked: {result.checked_at}",
        f"- Latest HTTP code: {result.status_code if result.status_code is not None else 'none'}",
        f"- Latest response time: {result.response_time_ms} ms",
    ]
    for days in (7, 30):
        rate = _rate(records, latest_date, days)
        label = f"{days}-day success rate"
        lines.append(
            f"- {label}: {rate:.1f}%" if rate is not None else f"- {label}: Insufficient history"
        )
    return lines


def generate_summary_files(
    results: list[CheckResult], latest_path: Path, markdown_path: Path
) -> None:
    """Atomically write the latest JSON and cautious human-readable summary."""
    latest = latest_by_target(results)
    generated_at = max((result.checked_at for result in latest), default=None)
    payload = {"generated_at": generated_at, "targets": [result.to_dict() for result in latest]}
    atomic_write_text(latest_path, json.dumps(payload, indent=2, sort_keys=True) + "\n")

    lines = [
        "# Public Service Status",
        "",
        "This reflects recorded checks, not a guaranteed uptime claim.",
        "",
    ]
    if not latest:
        lines.extend(["No public checks have been recorded yet.", ""])
    grouped: dict[str, list[CheckResult]] = defaultdict(list)
    for result in results:
        grouped[result.target_name].append(result)
    for result in latest:
        lines.extend(_render_target(result, grouped[result.target_name]))
        lines.append("")
    atomic_write_text(markdown_path, "\n".join(lines))
