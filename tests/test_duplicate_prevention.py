from __future__ import annotations

from portfolio_ops.models import CheckResult
from portfolio_ops.storage import append_unique_results, load_results


def test_prevents_second_record_for_target_on_same_utc_date(tmp_path):
    path = tmp_path / "uptime.csv"
    first = CheckResult(
        "2026-07-13", "2026-07-13T01:00:00Z", "wrepo", "https://wrepo.net", 200, 31, True, ""
    )
    second = CheckResult(
        "2026-07-13",
        "2026-07-13T23:00:00Z",
        "wrepo",
        "https://wrepo.net",
        500,
        80,
        False,
        "http_status",
    )

    assert append_unique_results(path, [first]) is True
    assert append_unique_results(path, [second]) is False
    assert load_results(path) == [first]
