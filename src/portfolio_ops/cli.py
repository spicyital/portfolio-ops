"""Command-line entry point for public portfolio checks and reports."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from .config import ConfigurationError, load_targets
from .http_check import check_target
from .storage import append_unique_results, load_results
from .summary import generate_summary_files

LOGGER = logging.getLogger("portfolio_ops")
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _data_paths(data_dir: Path) -> tuple[Path, Path, Path]:
    return data_dir / "uptime.csv", data_dir / "latest-status.json", data_dir / "status-summary.md"


def _run_check(config_path: Path | None, data_dir: Path, timeout: float) -> int:
    targets = load_targets(config_path=config_path)
    LOGGER.info("monitor_start target_count=%d timeout_seconds=%s", len(targets), timeout)
    results = [check_target(target, timeout=timeout) for target in targets]
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
    changed = append_unique_results(uptime_path, results)
    generate_summary_files(load_results(uptime_path), latest_path, markdown_path)
    LOGGER.info("monitor_complete csv_changed=%s", changed)
    return 0


def _run_summary(data_dir: Path) -> int:
    uptime_path, latest_path, markdown_path = _data_paths(data_dir)
    generate_summary_files(load_results(uptime_path), latest_path, markdown_path)
    LOGGER.info("summary_generated result_count=%d", len(load_results(uptime_path)))
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
            return _run_check(arguments.config, arguments.data_dir, arguments.timeout)
        if arguments.command == "summary":
            return _run_summary(arguments.data_dir)
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
