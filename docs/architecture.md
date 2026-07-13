# Architecture

`portfolio_ops.config` loads targets from a local `config/targets.json`, then the `MONITOR_TARGETS_JSON` GitHub Actions repository variable, then the built-in WRepo public URL. Validation allows only credential-free HTTP(S) URLs and strips query strings and fragments before any result is stored.

`portfolio_ops.http_check` issues one normal `GET` per target through Python's standard library. It follows redirects and normalizes HTTP, DNS, timeout, TLS, and connection outcomes into a `CheckResult`; it never reads a response body.

`portfolio_ops.storage` parses the historical CSV, rejects malformed schemas, detects duplicate `(target name, UTC date)` pairs, sorts records consistently, and writes replacements through a temporary file in the destination directory followed by an atomic replace. `portfolio_ops.summary` derives the latest result per target and cautious 7-/30-day rates only when enough dates exist.

The monitor coordinates DNS safety, HTTP, bounded content assertion, TLS metadata, and header posture into a typed check record. JSONL stores 90-day detailed history; the existing CSV remains the daily compatibility record. Metrics and incidents are deterministic derivatives, and the dashboard consumes only their sanitized JSON.

The four-times-daily workflow tests the package before it checks public URLs. It uses the repository-scoped `GITHUB_TOKEN` with `contents: write` and optional `issues: write`, then commits only changed generated data with the GitHub Actions bot identity. No personal access token or secret is required.
