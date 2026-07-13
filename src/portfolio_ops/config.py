"""Load and validate only public monitoring targets."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Mapping
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .models import Target


class ConfigurationError(ValueError):
    """Raised when a target configuration cannot safely be used."""


DEFAULT_TARGETS: tuple[Target, ...] = (
    Target(name="wrepo", display_name="WRepo", url="https://wrepo.net"),
)
_NAME_PATTERN = re.compile(r"[^a-z0-9]+")
_HOST_PATTERN = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)*[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$|^[a-z0-9]$"
)


def sanitize_name(value: object) -> str:
    """Normalize a human label to a stable, non-sensitive target identifier."""
    if not isinstance(value, str):
        raise ConfigurationError("Target names must be strings.")
    name = _NAME_PATTERN.sub("-", value.strip().lower()).strip("-")
    if not name or len(name) > 80:
        raise ConfigurationError("Target name must contain 1-80 letters, numbers, or hyphens.")
    return name


def sanitize_public_url(value: object) -> str:
    """Accept an HTTP(S) URL and remove query/fragment identifiers before storage."""
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError("Target URLs must be non-empty strings.")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ConfigurationError("Targets must use a public http or https URL.")
    if parsed.username or parsed.password:
        raise ConfigurationError("Targets must not contain credentials.")
    try:
        port = parsed.port
    except ValueError as error:
        raise ConfigurationError("Target URL has an invalid port.") from error
    host = parsed.hostname.lower()
    if host == "localhost" or host.endswith(".local"):
        raise ConfigurationError("Targets must not point to local infrastructure.")
    try:
        address = ip_address(host)
    except ValueError:
        address = None
        if not _HOST_PATTERN.fullmatch(host):
            raise ConfigurationError("Target URL has a malformed hostname.") from None
    if address is not None and not address.is_global:
        raise ConfigurationError("Targets must not point to non-public IP addresses.")
    netloc = host if port is None else f"{host}:{port}"
    path = parsed.path or "/"
    return (
        urlunsplit((parsed.scheme.lower(), netloc, path, "", "")).rstrip("/")
        or f"{parsed.scheme}://{netloc}"
    )


def _parse_targets(raw: str, source: str) -> list[Target]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ConfigurationError(f"{source} is not valid JSON.") from error
    if not isinstance(payload, list) or not payload:
        raise ConfigurationError(f"{source} must be a non-empty JSON list.")

    targets: list[Target] = []
    names: set[str] = set()
    for item in payload:
        if not isinstance(item, dict):
            raise ConfigurationError(f"Every target in {source} must be an object.")
        name = sanitize_name(item.get("name"))
        if name in names:
            raise ConfigurationError(f"Target names in {source} must be unique.")
        names.add(name)
        url = sanitize_public_url(item.get("url"))
        display_name = item.get("display_name", name)
        if not isinstance(display_name, str) or not display_name.strip() or len(display_name) > 100:
            raise ConfigurationError("display_name must be a 1-100 character string.")
        expected_statuses = item.get("expected_statuses", [200])
        if (
            not isinstance(expected_statuses, list)
            or not expected_statuses
            or any(type(code) is not int or not 100 <= code <= 599 for code in expected_statuses)
        ):
            raise ConfigurationError(
                "expected_statuses must be a non-empty list of HTTP status codes."
            )
        timeout_seconds = item.get("timeout_seconds", 15)
        if not isinstance(timeout_seconds, int | float) or not 1 <= timeout_seconds <= 60:
            raise ConfigurationError("timeout_seconds must be between 1 and 60.")
        expected_text = item.get("expected_text")
        if expected_text is not None and (
            not isinstance(expected_text, str) or len(expected_text) > 500
        ):
            raise ConfigurationError("expected_text must be a string up to 500 characters.")
        if any(
            not isinstance(item.get(field, True), bool)
            for field in ("enabled", "check_dns", "check_tls", "check_security_headers")
        ):
            raise ConfigurationError("enabled and check flags must be booleans.")
        latency_warning_ms = item.get("latency_warning_ms", 1500)
        failure_threshold = item.get("failure_threshold", 2)
        if type(latency_warning_ms) is not int or latency_warning_ms < 1:
            raise ConfigurationError("latency_warning_ms must be a positive integer.")
        if type(failure_threshold) is not int or not 1 <= failure_threshold <= 20:
            raise ConfigurationError("failure_threshold must be between 1 and 20.")
        targets.append(
            Target(
                name=name,
                url=url,
                display_name=display_name.strip(),
                enabled=item.get("enabled", True),
                expected_statuses=tuple(expected_statuses),
                timeout_seconds=float(timeout_seconds),
                expected_text=expected_text,
                check_dns=item.get("check_dns", True),
                check_tls=item.get("check_tls", True),
                check_security_headers=item.get("check_security_headers", True),
                latency_warning_ms=latency_warning_ms,
                failure_threshold=failure_threshold,
            )
        )
    return targets


def load_targets(
    config_path: Path | None = None, environment: Mapping[str, str] | None = None
) -> list[Target]:
    """Load local JSON first, then an Actions variable, then the safe default."""
    env = os.environ if environment is None else environment
    if config_path is not None and config_path.exists():
        return _parse_targets(config_path.read_text(encoding="utf-8"), str(config_path))
    variable = env.get("MONITOR_TARGETS_JSON", "").strip()
    if variable:
        return _parse_targets(variable, "MONITOR_TARGETS_JSON")
    return list(DEFAULT_TARGETS)
