from __future__ import annotations

import json

from portfolio_ops.models import CheckResult
from portfolio_ops.summary import generate_summary_files


def record(name: str, date: str, success: bool, status: int | None = 200) -> CheckResult:
    return CheckResult(
        date,
        f"{date}T12:00:00Z",
        name,
        "https://example.test",
        status,
        25,
        success,
        "" if success else "http_status",
    )


def test_generates_latest_json_and_honest_markdown_for_multiple_targets(tmp_path):
    records = [
        record("wrepo", "2026-07-12", False, 500),
        record("wrepo", "2026-07-13", True),
        record("impact-extension", "2026-07-13", True),
    ]
    latest_path = tmp_path / "latest-status.json"
    markdown_path = tmp_path / "status-summary.md"

    generate_summary_files(records, latest_path, markdown_path)

    payload = json.loads(latest_path.read_text(encoding="utf-8"))
    assert [item["target_name"] for item in payload["targets"]] == ["impact-extension", "wrepo"]
    assert payload["targets"][1]["status_code"] == 200
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "Current public status" in markdown
    assert "Insufficient history" in markdown


def test_generates_seven_day_rate_when_seven_distinct_days_exist(tmp_path):
    records = [record("wrepo", f"2026-07-{day:02d}", day != 7) for day in range(7, 14)]
    markdown_path = tmp_path / "status-summary.md"

    generate_summary_files(records, tmp_path / "latest.json", markdown_path)

    assert "7-day success rate: 85.7%" in markdown_path.read_text(encoding="utf-8")
