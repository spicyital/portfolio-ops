"""Perform one public GET request without retaining response content."""

from __future__ import annotations

import socket
import ssl
import time
from collections.abc import Callable
from datetime import UTC, datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .models import CheckResult, Target

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
    )


def check_target(
    target: Target, timeout: float = 10.0, now: NowProvider = lambda: datetime.now(UTC)
) -> CheckResult:
    """Check a public URL once; expected network failures become normal results."""
    started = time.perf_counter()
    request = Request(target.url, headers={"User-Agent": "Portfolio-Ops/1.0"}, method="GET")
    try:
        # urllib follows ordinary HTTP redirects. The response is never read or persisted.
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - URL is validated config
            status_code = response.getcode()
        success = status_code == 200
        return _result(target, now, started, status_code, success, "" if success else "http_status")
    except HTTPError as error:
        return _result(target, now, started, error.code, False, "http_status")
    except (URLError, OSError, ssl.SSLError, TimeoutError) as error:
        return _result(target, now, started, None, False, _error_type(error))
