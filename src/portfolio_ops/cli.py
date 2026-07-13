"""Command-line entry point for public portfolio checks and reports."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ConfigurationError, load_targets
from .dashboard import build_dashboard
from .github_issues import sync_incident_issues
from .monitor import monitor_targets
from .observability import write_observability_outputs
from .storage import (
    append_detailed_checks,
    append_unique_results,
    load_detailed_checks,
    load_results,
    migrate_csv_to_detailed,
)
from .summary import generate_summary_files

LOGGER = logging.getLogger("portfolio_ops")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _data_paths(data_dir: Path) -> tuple[Path, Path, Path]:
    return data_dir / "uptime.csv", data_dir / "latest-status.json", data_dir / "status-summary.md"


def _history(data_dir: Path):
    migrate_csv_to_detailed(data_dir / "uptime.csv", data_dir / "checks.jsonl")
    detailed = load_detailed_checks(data_dir / "checks.jsonl")
    return detailed or load_results(data_dir / "uptime.csv")


def _run_check(
    config_path: Path | None,
    data_dir: Path,
    timeout: float,
    target_name: str | None,
    issue_alerts: bool,
) -> int:
    targets = load_targets(config_path=config_path)
    results = monitor_targets(targets, target_name, timeout)
    for result in results:
        LOGGER.info(
            "monitor_result target=%s status=%s success=%s error=%s latency_ms=%d",
            result.target_name,
            result.status_code,
            result.success,
            result.error_type or "none",
            result.response_time_ms,
        )
    uptime_path, latest_path, markdown_path = _data_paths(data_dir)
    csv_changed = append_unique_results(uptime_path, results)
    detail_changed = append_detailed_checks(data_dir / "checks.jsonl", results)
    history = _history(data_dir)
    generate_summary_files(history, latest_path, markdown_path)
    metrics, incidents = write_observability_outputs(data_dir, history, targets)
    if issue_alerts:
        import os

        os.environ["MONITOR_ISSUE_ALERTS"] = "true"
        sync_incident_issues(incidents)
    LOGGER.info(
        "monitor_complete csv_changed=%s detailed_changed=%s services=%d",
        csv_changed,
        detail_changed,
        len(metrics),
    )
    return 0


def _run_summary(data_dir: Path) -> int:
    uptime_path, latest_path, markdown_path = _data_paths(data_dir)
    history = _history(data_dir)
    generate_summary_files(history, latest_path, markdown_path)
    write_observability_outputs(data_dir, history, load_targets())
    LOGGER.info("summary_generated result_count=%d", len(history))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the documented CLI parser."""
    parser = argparse.ArgumentParser(
        prog="portfolio-ops",
        description="Record availability metadata for public portfolio URLs only.",
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser(
        "check", help="check configured public URLs and update local data"
    )
    check.add_argument(
        "--config", type=Path, help="local JSON target configuration (takes precedence)"
    )
    check.add_argument(
        "--data-dir", type=Path, default=PROJECT_ROOT / "data", help="directory for generated data"
    )
    check.add_argument(
        "--timeout", type=float, default=10.0, help="per-target request timeout in seconds"
    )
    check.add_argument("--target", help="check one configured target by normalized name")
    check.add_argument(
        "--issue-alerts", action="store_true", help="enable Actions-only incident issue automation"
    )
    summary = subcommands.add_parser(
        "summary", help="rebuild latest JSON and Markdown status summary"
    )
    summary.add_argument(
        "--data-dir", type=Path, default=PROJECT_ROOT / "data", help="directory for generated data"
    )
    show = subcommands.add_parser("show-latest", help="print the current latest-status JSON")
    show.add_argument(
        "--data-dir", type=Path, default=PROJECT_ROOT / "data", help="directory for generated data"
    )
    incidents = subcommands.add_parser("incidents", help="print current public incident records")
    incidents.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    dashboard = subcommands.add_parser(
        "build-dashboard", help="generate static public dashboard assets"
    )
    dashboard.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    dashboard.add_argument("--output", type=Path, default=PROJECT_ROOT / "site")
    validate = subcommands.add_parser(
        "validate-config", help="validate target configuration without networking"
    )
    validate.add_argument("--config", type=Path)
    compact = subcommands.add_parser(
        "compact-history", help="compact detailed JSONL checks older than 90 days"
    )
    compact.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run a CLI command; return non-zero only for internal/configuration failures."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "check":
            if arguments.timeout <= 0:
                raise ConfigurationError("Timeout must be greater than zero.")
            return _run_check(
                arguments.config,
                arguments.data_dir,
                arguments.timeout,
                arguments.target,
                arguments.issue_alerts,
            )
        if arguments.command == "summary":
            return _run_summary(arguments.data_dir)
        if arguments.command == "validate-config":
            print(
                json.dumps(
                    [
                        {"name": target.name, "url": target.url}
                        for target in load_targets(arguments.config)
                    ],
                    indent=2,
                )
            )
            return 0
        if arguments.command == "compact-history":
            append_detailed_checks(arguments.data_dir / "checks.jsonl", [])
            return _run_summary(arguments.data_dir)
        if arguments.command == "build-dashboard":
            metrics, incidents = write_observability_outputs(
                arguments.data_dir, _history(arguments.data_dir), load_targets()
            )
            build_dashboard(metrics, incidents, arguments.output)
            LOGGER.info("dashboard_built output=%s", arguments.output)
            return 0
        if arguments.command == "incidents":
            path = arguments.data_dir / "incidents.json"
            print(
                path.read_text(encoding="utf-8")
                if path.exists()
                else '{"schema_version": 1, "incidents": []}'
            )
            return 0
        latest_path = arguments.data_dir / "latest-status.json"
        if not latest_path.exists():
            raise FileNotFoundError(f"No latest status file exists at {latest_path}.")
        print(
            json.dumps(
                json.loads(latest_path.read_text(encoding="utf-8")), indent=2, sort_keys=True
            )
        )
        return 0
    except (ConfigurationError, OSError, ValueError, json.JSONDecodeError) as error:
        LOGGER.error("command_failed error=%s", error)
        return 1


if __name__ == "__main__":
    sys.exit(main())
