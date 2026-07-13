"""Typed records shared by configuration, monitoring, and storage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Target:
    """A named, sanitized public URL to check."""

    name: str
    url: str


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

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation without headers or response content."""
        return {
            "utc_date": self.checked_date,
            "checked_at": self.checked_at,
            "target_name": self.target_name,
            "url": self.url,
            "status_code": self.status_code,
            "response_time_ms": self.response_time_ms,
            "success": self.success,
            "error_type": self.error_type,
        }
