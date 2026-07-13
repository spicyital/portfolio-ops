"""CSV persistence with duplicate protection and atomic writes."""

from __future__ import annotations

import csv
import json
import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from .models import CheckResult

CSV_FIELDS = [
    "utc_date",
    "checked_at",
    "target_name",
    "url",
    "status_code",
    "response_time_ms",
    "success",
    "error_type",
]


def _result_from_row(row: dict[str, str]) -> CheckResult:
    if set(row) != set(CSV_FIELDS):
        raise ValueError("uptime.csv has unexpected columns.")
    try:
        success_text = row["success"].lower()
        if success_text not in {"true", "false"}:
            raise ValueError("success must be true or false")
        return CheckResult(
            checked_date=row["utc_date"],
            checked_at=row["checked_at"],
            target_name=row["target_name"],
            url=row["url"],
            status_code=int(row["status_code"]) if row["status_code"] else None,
            response_time_ms=int(row["response_time_ms"]),
            success=success_text == "true",
            error_type=row["error_type"],
        )
    except (KeyError, ValueError) as error:
        raise ValueError("uptime.csv contains an invalid record.") from error


def load_results(path: Path) -> list[CheckResult]:
    """Read historical metadata or return no results when the file is new."""
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != CSV_FIELDS:
            raise ValueError("uptime.csv has an unexpected or missing header.")
        return [_result_from_row(row) for row in reader]


def _sort_key(result: CheckResult) -> tuple[str, str, str]:
    return result.checked_date, result.target_name, result.checked_at


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def write_results(path: Path, results: list[CheckResult]) -> None:
    """Write a complete, sorted CSV replacement in the destination directory."""
    from io import StringIO

    buffer = StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, lineterminator="\n")
    writer.writeheader()
    for result in sorted(results, key=_sort_key):
        row = {
            "utc_date": result.checked_date,
            "checked_at": result.checked_at,
            "target_name": result.target_name,
            "url": result.url,
            "status_code": "" if result.status_code is None else str(result.status_code),
            "response_time_ms": str(result.response_time_ms),
            "success": str(result.success).lower(),
            "error_type": result.error_type,
        }
        writer.writerow(row)
    _atomic_write_text(path, buffer.getvalue())


def append_unique_results(path: Path, new_results: list[CheckResult]) -> bool:
    """Append only target/date combinations absent from the historical CSV."""
    existing = load_results(path)
    known = {(result.target_name, result.checked_date) for result in existing}
    additions: list[CheckResult] = []
    for result in new_results:
        key = (result.target_name, result.checked_date)
        if key not in known:
            known.add(key)
            additions.append(result)
    if not additions:
        return False
    write_results(path, [*existing, *additions])
    return True


def atomic_write_text(path: Path, content: str) -> None:
    """Expose the safe text writer for JSON and Markdown summary outputs."""
    _atomic_write_text(path, content)


def load_detailed_checks(path: Path) -> list[CheckResult]:
    """Validate and load schema-v1 JSON Lines checks without response content."""
    if not path.exists():
        return []
    records: list[CheckResult] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
            if not isinstance(payload, dict) or payload.get("schema_version") != 1:
                raise ValueError("unsupported schema")
            records.append(CheckResult.from_dict(payload))
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ValueError(f"checks.jsonl is corrupt at line {number}.") from error
    return sorted(records, key=lambda item: (item.checked_at, item.check_id))


def append_detailed_checks(
    path: Path, checks: list[CheckResult], retention_days: int = 90, now: datetime | None = None
) -> bool:
    """Append unique checks and atomically compact only expired detailed history."""
    if retention_days < 1:
        raise ValueError("retention_days must be positive.")
    current = datetime.now(UTC) if now is None else now.astimezone(UTC)
    cutoff = current - timedelta(days=retention_days)
    existing = load_detailed_checks(path)
    merged = {record.check_id: record for record in existing}
    before = set(merged)
    for record in checks:
        merged.setdefault(record.check_id, record)
    retained = [
        record
        for record in merged.values()
        if datetime.fromisoformat(record.checked_at.replace("Z", "+00:00")) >= cutoff
    ]
    retained.sort(key=lambda item: (item.checked_at, item.check_id))
    changed = set(record.check_id for record in retained) != before or bool(
        checks and not path.exists()
    )
    if changed:
        _atomic_write_text(
            path,
            "".join(
                json.dumps(record.to_dict(), sort_keys=True, separators=(",", ":")) + "\n"
                for record in retained
            ),
        )
    return changed


def migrate_csv_to_detailed(csv_path: Path, detailed_path: Path) -> bool:
    """Seed detailed history from the legacy CSV once, preserving every CSV field."""
    if detailed_path.exists():
        return False
    legacy = load_results(csv_path)
    return append_detailed_checks(detailed_path, legacy) if legacy else False
