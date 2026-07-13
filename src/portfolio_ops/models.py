"""Typed, privacy-safe domain records for public monitoring."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Target:
    """A named, sanitized public URL to check."""

    name: str
    url: str
    display_name: str = ""
    enabled: bool = True
    expected_statuses: tuple[int, ...] = (200,)
    timeout_seconds: float = 15.0
    expected_text: str | None = None
    check_dns: bool = True
    check_tls: bool = True
    check_security_headers: bool = True
    latency_warning_ms: int = 1500
    failure_threshold: int = 2


@dataclass(frozen=True, slots=True)
class SecurityHeaderState:
    """Presence-only security-header result; no header value is retained."""

    name: str
    present: bool
    state: str

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "present": self.present, "state": self.state}


@dataclass(frozen=True, slots=True)
class CheckResult:
    """Non-sensitive metadata from a single public availability check."""

    checked_date: str
    checked_at: str
    target_name: str
    url: str
    status_code: int | None
    response_time_ms: int
    success: bool
    error_type: str
    check_id: str = ""
    final_url: str | None = None
    redirect_count: int = 0
    content_assertion_name: str | None = None
    content_assertion_passed: bool | None = None
    response_size_bytes: int | None = None
    dns_resolved: bool | None = None
    dns_duration_ms: int | None = None
    dns_error: str = ""
    tls_valid: bool | None = None
    tls_expires_at: str | None = None
    tls_days_remaining: int | None = None
    tls_hostname_match: bool | None = None
    tls_error: str = ""
    security_headers: tuple[SecurityHeaderState, ...] = ()
    security_score: int | None = None

    def __post_init__(self) -> None:
        if not self.check_id:
            digest = hashlib.sha256(
                f"{self.target_name}|{self.checked_at}|{self.url}".encode()
            ).hexdigest()[:20]
            object.__setattr__(self, "check_id", digest)
        if self.final_url is None:
            object.__setattr__(self, "final_url", self.url)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation without headers or response content."""
        return {
            "schema_version": 1,
            "check_id": self.check_id,
            "utc_date": self.checked_date,
            "checked_at": self.checked_at,
            "target_name": self.target_name,
            "url": self.url,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "success": self.success,
            "error_type": self.error_type,
            "final_url": self.final_url,
            "redirect_count": self.redirect_count,
            "content_assertion": {
                "name": self.content_assertion_name,
                "passed": self.content_assertion_passed,
            },
            "response_size_bytes": self.response_size_bytes,
            "dns": {
                "resolved": self.dns_resolved,
                "duration_ms": self.dns_duration_ms,
                "error": self.dns_error,
            },
            "tls": {
                "valid": self.tls_valid,
                "expires_at": self.tls_expires_at,
                "days_remaining": self.tls_days_remaining,
                "hostname_match": self.tls_hostname_match,
                "error": self.tls_error,
            },
            "security_headers": [header.to_dict() for header in self.security_headers],
            "security_score": self.security_score,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> CheckResult:
        assertion = payload.get("content_assertion") or {}
        dns = payload.get("dns") or {}
        tls = payload.get("tls") or {}
        headers = payload.get("security_headers") or []
        if not all(isinstance(value, dict) for value in (assertion, dns, tls)) or not isinstance(
            headers, list
        ):
            raise ValueError("Detailed check has invalid metadata.")
        return cls(
            checked_date=str(payload["utc_date"]),
            checked_at=str(payload["checked_at"]),
            target_name=str(payload["target_name"]),
            url=str(payload["url"]),
            status_code=int(payload["status_code"])
            if payload.get("status_code") is not None
            else None,
            response_time_ms=int(payload["response_time_ms"]),
            success=bool(payload["success"]),
            error_type=str(payload.get("error_type", "")),
            check_id=str(payload["check_id"]),
            final_url=str(payload["final_url"]) if payload.get("final_url") else None,
            redirect_count=int(payload.get("redirect_count", 0)),
            content_assertion_name=str(assertion["name"])
            if assertion.get("name") is not None
            else None,
            content_assertion_passed=bool(assertion["passed"])
            if assertion.get("passed") is not None
            else None,
            response_size_bytes=int(payload["response_size_bytes"])
            if payload.get("response_size_bytes") is not None
            else None,
            dns_resolved=bool(dns["resolved"]) if dns.get("resolved") is not None else None,
            dns_duration_ms=int(dns["duration_ms"]) if dns.get("duration_ms") is not None else None,
            dns_error=str(dns.get("error", "")),
            tls_valid=bool(tls["valid"]) if tls.get("valid") is not None else None,
            tls_expires_at=str(tls["expires_at"]) if tls.get("expires_at") else None,
            tls_days_remaining=int(tls["days_remaining"])
            if tls.get("days_remaining") is not None
            else None,
            tls_hostname_match=bool(tls["hostname_match"])
            if tls.get("hostname_match") is not None
            else None,
            tls_error=str(tls.get("error", "")),
            security_headers=tuple(
                SecurityHeaderState(str(item["name"]), bool(item["present"]), str(item["state"]))
                for item in headers
                if isinstance(item, dict)
            ),
            security_score=int(payload["security_score"])
            if payload.get("security_score") is not None
            else None,
        )
