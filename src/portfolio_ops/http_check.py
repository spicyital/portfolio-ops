"""Perform one public GET request without retaining response content."""

from __future__ import annotations

import socket
import ssl
import time
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import sanitize_public_url
from .models import CheckResult, Target
from .security_headers import evaluate_security_headers

NowProvider = Callable[[], datetime]


def _timestamp(now: NowProvider) -> tuple[str, str]:
    current = now().astimezone(UTC)
    return current.date().isoformat(), current.isoformat(timespec="seconds").replace("+00:00", "Z")


def _error_type(error: URLError | OSError | ssl.SSLError | TimeoutError) -> str:
    reason = error.reason if isinstance(error, URLError) else error
    if isinstance(reason, TimeoutError | socket.timeout):
        return "timeout"
    if isinstance(reason, socket.gaierror):
        return "dns_error"
    if isinstance(reason, ssl.SSLError):
        return "tls_error"
    return "connection_error"


def _result(
    target: Target,
    now: NowProvider,
    started: float,
    status_code: int | None,
    success: bool,
    error_type: str,
    **details: object,
) -> CheckResult:
    checked_date, checked_at = _timestamp(now)
    return CheckResult(
        checked_date=checked_date,
        checked_at=checked_at,
        target_name=target.name,
        url=target.url,
        status_code=status_code,
        response_time_ms=max(0, round((time.perf_counter() - started) * 1000)),
        success=success,
        error_type=error_type,
        **details,
    )


def check_target(
    target: Target,
    timeout: float | None = None,
    now: NowProvider = lambda: datetime.now(UTC),
    max_response_bytes: int = 256 * 1024,
) -> CheckResult:
    """Check a public URL once; expected network failures become normal results."""
    started = time.perf_counter()
    request = Request(target.url, headers={"User-Agent": "Portfolio-Ops/1.0"}, method="GET")
    effective_timeout = target.timeout_seconds if timeout is None else timeout
    try:
        # urllib follows ordinary HTTP redirects. The response is never read or persisted.
        with urlopen(request, timeout=effective_timeout) as response:  # noqa: S310 - URL is validated config
            status_code = response.getcode()
            final_url = sanitize_public_url(
                response.geturl() if hasattr(response, "geturl") else target.url
            )
            raw_headers = getattr(response, "headers", {})
            content_length = raw_headers.get("Content-Length")
            response_size = (
                int(content_length) if content_length and content_length.isdigit() else None
            )
            if response_size is not None and response_size > max_response_bytes:
                return _result(
                    target,
                    now,
                    started,
                    status_code,
                    False,
                    "response_too_large",
                    final_url=final_url,
                    response_size_bytes=response_size,
                )
            assertion_passed: bool | None = None
            if target.expected_text is not None:
                body = response.read(max_response_bytes + 1)
                if len(body) > max_response_bytes:
                    return _result(
                        target,
                        now,
                        started,
                        status_code,
                        False,
                        "response_too_large",
                        final_url=final_url,
                        response_size_bytes=response_size,
                    )
                assertion_passed = target.expected_text in body.decode("utf-8", errors="replace")
            headers, score = (
                evaluate_security_headers(raw_headers)
                if target.check_security_headers
                else ((), None)
            )
        success = status_code in target.expected_statuses and assertion_passed is not False
        error_type = (
            ""
            if success
            else ("content_assertion_failed" if assertion_passed is False else "http_status")
        )
        return _result(
            target,
            now,
            started,
            status_code,
            success,
            error_type,
            final_url=final_url,
            redirect_count=int(final_url != target.url),
            content_assertion_name="expected_text" if target.expected_text is not None else None,
            content_assertion_passed=assertion_passed,
            response_size_bytes=response_size,
            security_headers=headers,
            security_score=score,
        )
    except HTTPError as error:
        return _result(target, now, started, error.code, False, "http_status")
    except (URLError, OSError, ssl.SSLError, TimeoutError) as error:
        return _result(target, now, started, None, False, _error_type(error))
