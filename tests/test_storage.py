from __future__ import annotations

import csv
import json
import os
from unittest.mock import patch

from portfolio_ops.cli import main
from portfolio_ops.models import CheckResult
from portfolio_ops.storage import append_unique_results, load_results


def result(name: str = "wrepo", timestamp: str = "2026-07-13T12:00:00Z") -> CheckResult:
    return CheckResult("2026-07-13", timestamp, name, "https://wrepo.net", 200, 41, True, "")


def test_creates_csv_atomically_when_missing(tmp_path):
    path = tmp_path / "uptime.csv"

    with patch("portfolio_ops.storage.os.replace", wraps=os.replace) as replace:
        assert append_unique_results(path, [result()]) is True

    replace.assert_called_once()
    assert load_results(path) == [result()]
    assert not list(tmp_path.glob("*.tmp"))


def test_preserves_existing_rows_and_sorts_consistently(tmp_path):
    path = tmp_path / "uptime.csv"
    older = CheckResult(
        "2026-07-12", "2026-07-12T12:00:00Z", "wrepo", "https://wrepo.net", 200, 40, True, ""
    )
    append_unique_results(path, [result()])
    append_unique_results(path, [older])

    assert load_results(path) == [older, result()]
    with path.open(newline="", encoding="utf-8") as handle:
        assert next(csv.reader(handle))[0] == "utc_date"


def test_cli_check_runs_with_a_mocked_public_target(tmp_path):
    config_path = tmp_path / "targets.json"
    config_path.write_text(
        json.dumps([{"name": "demo", "url": "https://example.test"}]), encoding="utf-8"
    )
    monitored = CheckResult(
        "2026-07-13",
        "2026-07-13T12:00:00Z",
        "demo",
        "https://example.test",
        200,
        24,
        True,
        "",
    )

    with patch("portfolio_ops.cli.monitor_targets", return_value=[monitored]):
        exit_code = main(["check", "--config", str(config_path), "--data-dir", str(tmp_path)])

    assert exit_code == 0
    assert load_results(tmp_path / "uptime.csv") == [monitored]
