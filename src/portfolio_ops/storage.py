"""CSV persistence with duplicate protection and atomic writes."""

from __future__ import annotations

import csv
import os
import tempfile
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
        row = result.to_dict()
        row["status_code"] = "" if result.status_code is None else str(result.status_code)
        row["response_time_ms"] = str(result.response_time_ms)
        row["success"] = str(result.success).lower()
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
