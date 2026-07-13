"""Public DNS checks that never retain resolved IP addresses."""

from __future__ import annotations

import socket
import time
from dataclasses import dataclass
from ipaddress import ip_address


@dataclass(frozen=True, slots=True)
class DnsResult:
    resolved: bool
    duration_ms: int
    error_type: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "resolved": self.resolved,
            "duration_ms": self.duration_ms,
            "error": self.error_type,
        }


def resolve_public_hostname(hostname: str) -> DnsResult:
    """Resolve a hostname and reject answer sets with no globally routable IP."""
    started = time.perf_counter()
    try:
        answers = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
        addresses = {answer[4][0] for answer in answers}
        duration = round((time.perf_counter() - started) * 1000)
        if not addresses or not any(ip_address(address).is_global for address in addresses):
            return DnsResult(False, duration, "unsafe_address")
        return DnsResult(True, duration)
    except socket.gaierror:
        return DnsResult(False, round((time.perf_counter() - started) * 1000), "dns_error")
    except TimeoutError:
        return DnsResult(False, round((time.perf_counter() - started) * 1000), "timeout")
    except OSError:
        return DnsResult(False, round((time.perf_counter() - started) * 1000), "dns_error")
