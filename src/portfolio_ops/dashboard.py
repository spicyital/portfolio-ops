"""Generate a static, tracker-free dashboard from sanitized aggregates."""

from __future__ import annotations

import json
from pathlib import Path

from .storage import atomic_write_text

_INDEX = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Portfolio Ops Status</title><link rel="stylesheet" href="styles.css"></head>
<body><main><header><p class="eyebrow">Portfolio Ops</p><h1>Public service status</h1>
<p>Scheduled observations, not continuous uptime guarantees.</p></header>
<section><h2>Services</h2><div id="services" aria-live="polite"></div></section>
<section><h2>Incidents</h2><div id="incidents"></div></section>
<section><h2>Methodology</h2>
<p>Only public endpoints are checked. No response bodies, accounts, cookies,
or private application data are stored.</p></section>
</main><script src="app.js"></script></body></html>
"""

_CSS = """*{box-sizing:border-box}body{margin:0;background:#f5f7fb;color:#172033;font:16px system-ui,sans-serif}main{max-width:960px;margin:auto;padding:40px 20px}.eyebrow{color:#3867d6;font-weight:700;text-transform:uppercase;letter-spacing:.08em}h1{font-size:clamp(2rem,5vw,3rem)}#services{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:16px}.card{background:#fff;border:1px solid #dce3f0;border-radius:12px;padding:20px;margin:12px 0}.ok{color:#157347}.bad{color:#b42318}dl{display:grid;grid-template-columns:auto 1fr;gap:8px}dt{font-weight:700}dd{margin:0}@media(max-width:500px){main{padding:24px 14px}}\n"""  # noqa: E501

_APP = """fetch('status.json').then(r=>r.json()).then(data=>{const rate=v=>v==null?'Insufficient history':v+'%';const services=data.services||[];document.querySelector('#services').innerHTML=services.map(s=>{const l=s.latest||{};return `<article class="card"><h3>${s.target_name}</h3><p class="${l.success?'ok':'bad'}">${l.success?'Operational':'Check failed'}</p><dl><dt>Last check</dt><dd>${l.checked_at||'No checks yet'}</dd><dt>HTTP</dt><dd>${l.status_code??'—'}</dd><dt>Latency</dt><dd>${l.response_time_ms??'—'} ms</dd><dt>24h observed availability</dt><dd>${rate(s.availability_24h)}</dd><dt>7d observed availability</dt><dd>${rate(s.availability_7d)}</dd><dt>30d observed availability</dt><dd>${rate(s.availability_30d)}</dd><dt>p50 / p95</dt><dd>${s.p50_latency_ms??'—'} / ${s.p95_latency_ms??'—'} ms</dd><dt>TLS days</dt><dd>${s.tls_days_remaining??'—'}</dd><dt>Security posture</dt><dd>${s.security_header_score??'—'}%</dd></dl></article>`}).join('')||'<p>No live observations recorded yet.</p>';const incidents=data.incidents||[];document.querySelector('#incidents').innerHTML=incidents.map(i=>`<article class="card"><strong>${i.target}</strong>: ${i.status} — ${i.failure_reason}</article>`).join('')||'<p>No incidents recorded.</p>';});\n"""  # noqa: E501


def build_dashboard(
    metrics: dict[str, dict[str, object]], incidents: list[dict[str, object]], output: Path
) -> None:
    """Write static assets and only sanitized, machine-readable state."""
    output.mkdir(parents=True, exist_ok=True)
    payload = {"schema_version": 1, "services": list(metrics.values()), "incidents": incidents}
    atomic_write_text(output / "index.html", _INDEX)
    atomic_write_text(output / "styles.css", _CSS)
    atomic_write_text(output / "app.js", _APP)
    atomic_write_text(output / "status.json", json.dumps(payload, indent=2, sort_keys=True) + "\n")
