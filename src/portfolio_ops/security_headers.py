"""Presence-only public HTTP security-header posture checks."""

from __future__ import annotations

from collections.abc import Mapping

from .models import SecurityHeaderState

_REQUIRED = (
    "Strict-Transport-Security",
    "Content-Security-Policy",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
)


def evaluate_security_headers(
    headers: Mapping[str, str],
) -> tuple[tuple[SecurityHeaderState, ...], int]:
    """Inspect values transiently and retain names, presence, and simple states only."""
    lower = {name.lower(): value for name, value in headers.items()}
    states = [
        SecurityHeaderState(
            name, name.lower() in lower, "pass" if name.lower() in lower else "warning"
        )
        for name in _REQUIRED
    ]
    csp = lower.get("content-security-policy", "")
    frame_not_applicable = "frame-ancestors" in csp.lower()
    frame_present = "x-frame-options" in lower
    states.append(
        SecurityHeaderState(
            "X-Frame-Options",
            frame_present,
            "not-applicable" if frame_not_applicable else ("pass" if frame_present else "warning"),
        )
    )
    applicable = [item for item in states if item.state != "not-applicable"]
    score = (
        round(100 * sum(item.present for item in applicable) / len(applicable))
        if applicable
        else 100
    )
    return tuple(states), score
