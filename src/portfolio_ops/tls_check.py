"""Minimal public TLS certificate checks that discard certificate contents."""

from __future__ import annotations

import socket
import ssl
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class TlsResult:
    valid: bool
    expires_at: str | None
    days_remaining: int | None
    hostname_match: bool | None
    error_type: str = ""


def tls_warning_state(days_remaining: int) -> str:
    if days_remaining < 0:
        return "expired"
    if days_remaining < 7:
        return "warning-7d"
    if days_remaining < 14:
        return "warning-14d"
    if days_remaining < 30:
        return "warning-30d"
    return "pass"


def check_tls(hostname: str, port: int = 443, timeout: float = 15.0) -> TlsResult:
    """Return expiry metadata only; no certificate subject or chain is persisted."""
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, port), timeout=timeout) as raw_socket:
            with context.wrap_socket(raw_socket, server_hostname=hostname) as secure_socket:
                certificate = secure_socket.getpeercert()
        expiry = datetime.strptime(certificate["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(
            tzinfo=UTC
        )
        days = (expiry.date() - datetime.now(UTC).date()).days
        return TlsResult(
            days >= 0, expiry.date().isoformat(), days, True, "" if days >= 0 else "expired"
        )
    except ssl.SSLCertVerificationError:
        return TlsResult(False, None, None, False, "hostname_mismatch")
    except ssl.SSLError:
        return TlsResult(False, None, None, None, "tls_error")
    except (OSError, TimeoutError):
        return TlsResult(False, None, None, None, "tls_connection_error")
