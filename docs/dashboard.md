# Public Status Dashboard

`site/` is a static, responsive, accessible dashboard generated from `data/service-metrics.json` and `data/incidents.json`. It has no framework, trackers, analytics, external fonts, cookies, or authentication.

Run `python -m portfolio_ops.cli build-dashboard` locally. The Pages workflow rebuilds it on `main`; enable **Settings → Pages → GitHub Actions** in the repository to deploy it. The dashboard reports scheduled observations, not continuous uptime or an SLA.
