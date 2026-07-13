# Adding Public Targets

For a local run, copy `config/targets.example.json` to `config/targets.json` and edit it. The local file is ignored by Git.

For GitHub Actions, add a repository **variable** named `MONITOR_TARGETS_JSON` under **Settings → Secrets and variables → Actions → Variables**. Its value must be a JSON array, for example:

```json
[
  {"name": "wrepo", "url": "https://wrepo.net"},
  {
    "name": "impact-extension",
    "url": "https://chromewebstore.google.com/detail/your-public-listing"
  }
]
```

Only add URLs that are public, safe to request without logging in, and represent a portfolio service you control. Do not include private dashboards, API endpoints requiring credentials, URLs containing credentials, or URLs that carry personal data in their query string. Query strings and fragments are removed before storage.

Targets can additionally set expected status codes, a timeout (1–60 seconds), an optional bounded `expected_text` assertion, DNS/TLS/header flags, latency warning threshold, and incident failure threshold. Portfolio Ops rejects malformed hosts, local names, loopback, private, link-local, reserved, and multicast address literals; DNS answers without a public address are rejected before HTTP monitoring.

The Chrome Web Store URL is checked only for public availability. Portfolio Ops does not access the Chrome Web Store developer console, user identities, reviews, or account information.
