"""Coordinate DNS, HTTP, TLS, and security checks for public targets."""

from __future__ import annotations

from dataclasses import replace
from urllib.parse import urlsplit

from .dns_check import resolve_public_hostname
from .http_check import check_target
from .models import CheckResult, Target
from .tls_check import check_tls


def monitor_target(target: Target) -> CheckResult:
    """Run configured public probes; routine availability failures remain results."""
    hostname = urlsplit(target.url).hostname
    assert hostname is not None  # Target validation guarantees a host.
    dns = resolve_public_hostname(hostname) if target.check_dns else None
    if dns is not None and not dns.resolved:
        # Avoid every HTTP request when DNS yields no safe public address.
        from datetime import UTC, datetime

        current = datetime.now(UTC)
        return CheckResult(
            checked_date=current.date().isoformat(),
            checked_at=current.isoformat(timespec="seconds").replace("+00:00", "Z"),
            target_name=target.name,
            url=target.url,
            status_code=None,
            response_time_ms=0,
            success=False,
            error_type=dns.error_type,
            dns_resolved=False,
            dns_duration_ms=dns.duration_ms,
            dns_error=dns.error_type,
        )
    result = check_target(target)
    if dns is not None:
        result = replace(
            result,
            dns_resolved=dns.resolved,
            dns_duration_ms=dns.duration_ms,
            dns_error=dns.error_type,
        )
    if target.check_tls and urlsplit(target.url).scheme == "https":
        tls = check_tls(hostname, timeout=target.timeout_seconds)
        result = replace(
            result,
            tls_valid=tls.valid,
            tls_expires_at=tls.expires_at,
            tls_days_remaining=tls.days_remaining,
            tls_hostname_match=tls.hostname_match,
            tls_error=tls.error_type,
        )
    return result


def monitor_targets(
    targets: list[Target], selected_name: str | None = None, timeout: float | None = None
) -> list[CheckResult]:
    """Check enabled targets, optionally narrowing to a single normalized target name."""
    selected = [
        target
        for target in targets
        if target.enabled and (selected_name is None or target.name == selected_name)
    ]
    if selected_name is not None and not selected:
        raise ValueError(f"No enabled target named {selected_name!r}.")
    return [
        monitor_target(replace(target, timeout_seconds=timeout) if timeout is not None else target)
        for target in selected
    ]
