from __future__ import annotations

import socket
from datetime import UTC, datetime
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from portfolio_ops.http_check import check_target
from portfolio_ops.models import Target


class FakeResponse:
    def __init__(self, status: int) -> None:
        self.status = status

    def getcode(self) -> int:
        return self.status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def fixed_now() -> datetime:
    return datetime(2026, 7, 13, 12, 0, tzinfo=UTC)


def test_records_a_successful_http_200_without_reading_body():
    with patch("portfolio_ops.http_check.urlopen", return_value=FakeResponse(200)) as request:
        result = check_target(Target("demo", "https://example.test"), now=fixed_now)

    assert result.success is True
    assert result.status_code == 200
    assert result.error_type == ""
    assert result.checked_date == "2026-07-13"
    assert result.response_time_ms >= 0
    assert request.call_args.args[0].method == "GET"


def test_follows_redirects_using_standard_urlopen_behavior():
    with patch("portfolio_ops.http_check.urlopen", return_value=FakeResponse(200)):
        result = check_target(Target("redirect", "https://example.test/redirect"), now=fixed_now)

    assert result.success is True
    assert result.status_code == 200


def test_records_http_error_statuses_without_crashing():
    for status in (404, 500):
        error = HTTPError("https://example.test", status, "error", None, BytesIO())
        with patch("portfolio_ops.http_check.urlopen", side_effect=error):
            result = check_target(Target("demo", "https://example.test"), now=fixed_now)

        assert result.success is False
        assert result.status_code == status
        assert result.error_type == "http_status"


def test_normalizes_timeout_and_connection_failures():
    errors = [
        (TimeoutError(), "timeout"),
        (URLError(socket.gaierror()), "dns_error"),
        (URLError(OSError()), "connection_error"),
    ]
    for error, expected_type in errors:
        with patch("portfolio_ops.http_check.urlopen", side_effect=error):
            result = check_target(Target("demo", "https://example.test"), now=fixed_now)

        assert result.success is False
        assert result.status_code is None
        assert result.error_type == expected_type
