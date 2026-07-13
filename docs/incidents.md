# Incident Model

An isolated failed check is recorded as an observation, not an incident. Portfolio Ops opens an active incident after the configured consecutive-failure threshold (default: two). The incident records sanitized timestamps, target, normalized reason, and check counts.

Two consecutive successful checks mark an active incident resolved. Optional GitHub issue automation creates at most one matching open issue per active incident, then comments and closes it on recovery. No response content, headers, identifiers, or infrastructure information is included.
