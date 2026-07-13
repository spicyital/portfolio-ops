from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest

from portfolio_ops.config import ConfigurationError, load_targets
from portfolio_ops.dns_check import resolve_public_hostname
from portfolio_ops.http_check import check_target
from portfolio_ops.models import Target
from portfolio_ops.security_headers import evaluate_security_headers
from portfolio_ops.tls_check import tls_warning_state


class Response:
    def __init__(self, status: int = 200, body: bytes = b"WRepo", url: str = "https://wrepo.net"):
        self.status = status
        self._body = body
        self._url = url
        self.headers = {
            "Content-Length": str(len(body)),
            "Content-Security-Policy": "frame-ancestors 'self'",
        }

    def getcode(self) -> int:
        return self.status

    def geturl(self) -> str:
        return self._url

    def read(self, size: int = -1) -> bytes:
        return self._body[:size]

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def test_extended_target_configuration_and_strict_defaults():
    target = load_targets(
        environment={
            "MONITOR_TARGETS_JSON": """[{"name":"wrepo","display_name":"WRepo","url":"https://wrepo.net","enabled":true,"expected_statuses":[200,302],"timeout_seconds":15,"expected_text":"WRepo","check_dns":true,"check_tls":true,"check_security_headers":true,"latency_warning_ms":1500,"failure_threshold":2}]"""
        }
    )[0]

    assert target.display_name == "WRepo"
    assert target.expected_statuses == (200, 302)
    assert target.expected_text == "WRepo"
    assert target.failure_threshold == 2


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.test",
        "https://user:password@example.test",
        "http://localhost",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://169.254.1.1",
    ],
)
def test_rejects_unsafe_target_urls(url: str):
    with pytest.raises(ConfigurationError):
        load_targets(
            environment={"MONITOR_TARGETS_JSON": json.dumps([{"name": "bad", "url": url}])}
        )


def test_dns_check_discards_addresses_and_rejects_unsafe_resolution():
    with patch(
        "portfolio_ops.dns_check.socket.getaddrinfo", return_value=[(0, 0, 0, "", ("8.8.8.8", 443))]
    ):
        result = resolve_public_hostname("wrepo.net")
    assert result.resolved is True
    assert result.error_type == ""
    assert "8.8.8.8" not in result.to_dict().values()

    with patch(
        "portfolio_ops.dns_check.socket.getaddrinfo",
        return_value=[(0, 0, 0, "", ("127.0.0.1", 443))],
    ):
        unsafe = resolve_public_hostname("wrepo.net")
    assert unsafe.resolved is False
    assert unsafe.error_type == "unsafe_address"


def test_http_expected_text_redirect_metadata_and_size_are_recorded_without_body_storage():
    target = Target("wrepo", "https://wrepo.net", expected_text="WRepo", expected_statuses=(200,))
    with patch(
        "portfolio_ops.http_check.urlopen", return_value=Response(url="https://wrepo.net/home")
    ):
        result = check_target(target, now=lambda: datetime(2026, 7, 13, tzinfo=UTC))

    assert result.success is True
    assert result.final_url == "https://wrepo.net/home"
    assert result.content_assertion_passed is True
    assert result.response_size_bytes == 5
    assert "WRepo" not in str(result.to_dict())


def test_http_missing_expected_text_and_oversized_response_are_safe_failures():
    target = Target("wrepo", "https://wrepo.net", expected_text="missing")
    with patch("portfolio_ops.http_check.urlopen", return_value=Response(body=b"present")):
        result = check_target(target)
    assert result.success is False
    assert result.error_type == "content_assertion_failed"

    response = Response(body=b"x" * 16)
    response.headers = {"Content-Length": "999999"}
    with patch("portfolio_ops.http_check.urlopen", return_value=response):
        oversized = check_target(target, max_response_bytes=8)
    assert oversized.error_type == "response_too_large"


def test_security_headers_do_not_persist_values_and_honor_csp_frame_ancestors():
    states, score = evaluate_security_headers(
        {
            "Strict-Transport-Security": "max-age=1",
            "Content-Security-Policy": "frame-ancestors 'self'",
            "X-Content-Type-Options": "nosniff",
        }
    )
    frame = next(item for item in states if item.name == "X-Frame-Options")
    assert frame.state == "not-applicable"
    assert score > 0
    assert "max-age" not in str([item.to_dict() for item in states])


def test_tls_warning_levels():
    assert tls_warning_state(31) == "pass"
    assert tls_warning_state(29) == "warning-30d"
    assert tls_warning_state(13) == "warning-14d"
    assert tls_warning_state(6) == "warning-7d"
    assert tls_warning_state(-1) == "expired"
