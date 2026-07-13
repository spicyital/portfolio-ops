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


DEFAULT_TARGETS: tuple[Target, ...] = (Target("wrepo", "https://wrepo.net"),)
_NAME_PATTERN = re.compile(r"[^a-z0-9]+")


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
        targets.append(Target(name=name, url=sanitize_public_url(item.get("url"))))
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
