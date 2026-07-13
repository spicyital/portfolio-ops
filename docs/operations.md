# Operations

The monitoring workflow runs at 00:17, 06:17, 12:17, and 18:17 UTC, with manual dispatch available. Tests run before public monitoring. A concurrency group prevents overlaps, and GitHub Actions commits only changed generated data with `github-actions[bot]`.

Detailed JSONL checks retain 90 days. CSV daily compatibility history and aggregate metrics are retained. Use `python -m portfolio_ops.cli compact-history` to safely compact detailed history and `python -m portfolio_ops.cli validate-config` before adding a public target.
