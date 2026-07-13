"""Optional GitHub incident issue automation using the built-in Actions token."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from urllib.request import Request, urlopen


def sync_incident_issues(
    incidents: list[dict[str, object]], environment: Mapping[str, str] | None = None
) -> None:
    """Create one public-metadata issue for each active incident when explicitly enabled."""
    env = os.environ if environment is None else environment
    token, repository = env.get("GITHUB_TOKEN"), env.get("GITHUB_REPOSITORY")
    if env.get("MONITOR_ISSUE_ALERTS") != "true" or not token or not repository:
        return

    def request_json(
        url: str, method: str = "GET", payload: dict[str, object] | None = None
    ) -> object:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            method=method,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "Portfolio-Ops",
            },
        )
        with urlopen(request, timeout=15) as response:  # noqa: S310 - fixed GitHub API host
            raw = response.read(256 * 1024)
        return json.loads(raw) if raw else None

    open_issues = request_json(
        f"https://api.github.com/repos/{repository}/issues?state=open&labels=incident"
    )
    if not isinstance(open_issues, list):
        return
    for incident in incidents:
        title = f"[Incident] {incident['target']} public availability failure"
        matching = next(
            (item for item in open_issues if isinstance(item, dict) and item.get("title") == title),
            None,
        )
        if incident.get("status") == "active" and matching is None:
            body = "\n".join(
                [
                    "Public monitoring incident",
                    f"Detected: {incident['detected_at']}",
                    f"Reason: {incident['failure_reason']}",
                    f"Failed checks: {incident['failed_check_count']}",
                ]
            )
            request_json(
                f"https://api.github.com/repos/{repository}/issues",
                "POST",
                {"title": title, "body": body, "labels": ["incident", "monitoring"]},
            )
        if (
            incident.get("status") == "resolved"
            and isinstance(matching, dict)
            and isinstance(matching.get("number"), int)
        ):
            number = matching["number"]
            recovery_count = incident["recovery_check_count"]
            request_json(
                f"https://api.github.com/repos/{repository}/issues/{number}/comments",
                "POST",
                {"body": f"Recovered after {recovery_count} successful public checks."},
            )
            request_json(
                f"https://api.github.com/repos/{repository}/issues/{number}",
                "PATCH",
                {"state": "closed"},
            )
