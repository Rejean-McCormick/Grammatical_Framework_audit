from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
from typing import Any

from app.models import DiffEntry, FileResult, RunPaths, RunResult


def find_previous_run_dir(run_paths: RunPaths) -> Path | None:
    """
    Find the most recent sibling run directory before the current run.

    Expected layout:
      out_root/
        run_YYYYMMDD_HHMMSS/
        run_YYYYMMDD_HHMMSS/

    The current run directory is excluded from the search.
    """
    current_run_dir = Path(run_paths.run_dir)
    out_root = current_run_dir.parent

    if not out_root.exists() or not out_root.is_dir():
        return None

    run_dirs = sorted(
        (
            path
            for path in out_root.iterdir()
            if path.is_dir() and path.name.startswith("run_")
        ),
        key=lambda path: path.name,
    )

    previous_dirs = [path for path in run_dirs if path != current_run_dir]
    if not previous_dirs:
        return None

    return previous_dirs[-1]


def load_previous_summary(previous_run_dir: Path | None) -> dict[str, Any] | None:
    """
    Load the previous run summary from summary.json.

    Returns the decoded JSON payload if present and valid, otherwise None.
    """
    if previous_run_dir is None:
        return None

    summary_json_path = previous_run_dir / "summary.json"
    if not summary_json_path.exists() or not summary_json_path.is_file():
        return None

    try:
        return json.loads(summary_json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_diff_entries(current_run_result: RunResult) -> list[DiffEntry]:
    """
    Compare the current run to the previous run and return normalized diff entries.

    change_kind values:
      - unchanged
      - improved
      - regressed
      - new
      - removed
    """
    previous_run_dir = find_previous_run_dir(current_run_result.run_paths)
    previous_summary = load_previous_summary(previous_run_dir)

    previous_file_map = _build_previous_file_map(previous_summary)
    current_file_map = {
        file_result.file_path: file_result
        for file_result in current_run_result.file_results
    }

    all_file_paths = sorted(set(previous_file_map) | set(current_file_map))
    diff_entries: list[DiffEntry] = []

    for file_path in all_file_paths:
        previous_item = previous_file_map.get(file_path)
        current_item = current_file_map.get(file_path)

        previous_status = _extract_status(previous_item)
        current_status = _extract_status(current_item)

        if previous_item is None and current_item is not None:
            change_kind = "new"
            message = f"{file_path}: new in current run ({current_status})"
        elif previous_item is not None and current_item is None:
            change_kind = "removed"
            message = f"{file_path}: removed from current run (was {previous_status})"
        else:
            change_kind, message = _compare_statuses(
                file_path=file_path,
                previous_item=previous_item,
                current_item=current_item,
                previous_status=previous_status,
                current_status=current_status,
            )

        diff_entries.append(
            DiffEntry(
                file_path=file_path,
                previous_status=previous_status,
                current_status=current_status,
                change_kind=change_kind,
                message=message,
            )
        )

    return diff_entries


def _build_previous_file_map(previous_summary: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not previous_summary:
        return {}

    raw_file_results = previous_summary.get("file_results", [])
    if not isinstance(raw_file_results, list):
        return {}

    previous_file_map: dict[str, dict[str, Any]] = {}

    for item in raw_file_results:
        if not isinstance(item, dict):
            continue

        file_path = item.get("file_path")
        if not isinstance(file_path, str) or not file_path.strip():
            continue

        previous_file_map[file_path] = item

    return previous_file_map


def _extract_status(item: dict[str, Any] | FileResult | None) -> str:
    if item is None:
        return "MISSING"

    if isinstance(item, FileResult):
        return item.status

    status = item.get("status")
    if isinstance(status, str) and status.strip():
        return status

    compile_summary = item.get("compile_summary")
    if isinstance(compile_summary, dict):
        exit_code = compile_summary.get("exit_code")
        if exit_code == 0:
            return "OK"
        if isinstance(exit_code, int):
            return "FAIL"

    return "UNKNOWN"


def _compare_statuses(
    *,
    file_path: str,
    previous_item: dict[str, Any] | None,
    current_item: FileResult | None,
    previous_status: str,
    current_status: str,
) -> tuple[str, str]:
    if previous_status == current_status:
        detail_change_message = _build_detail_change_message(previous_item, current_item)
        if detail_change_message:
            return "unchanged", f"{file_path}: {current_status}, {detail_change_message}"
        return "unchanged", f"{file_path}: unchanged ({current_status})"

    if _is_improvement(previous_status, current_status):
        return "improved", f"{file_path}: {previous_status} -> {current_status}"

    if _is_regression(previous_status, current_status):
        return "regressed", f"{file_path}: {previous_status} -> {current_status}"

    return "unchanged", f"{file_path}: {previous_status} -> {current_status}"


def _is_improvement(previous_status: str, current_status: str) -> bool:
    return previous_status == "FAIL" and current_status == "OK"


def _is_regression(previous_status: str, current_status: str) -> bool:
    return previous_status == "OK" and current_status == "FAIL"


def _build_detail_change_message(
    previous_item: dict[str, Any] | None,
    current_item: FileResult | None,
) -> str:
    previous_error_kind = _extract_error_kind(previous_item)
    current_error_kind = _extract_error_kind(current_item)

    previous_first_error = _extract_first_error(previous_item)
    current_first_error = _extract_first_error(current_item)

    if previous_error_kind != current_error_kind and previous_error_kind and current_error_kind:
        return f"error kind changed: {previous_error_kind} -> {current_error_kind}"

    if previous_first_error != current_first_error and previous_first_error and current_first_error:
        return "first error changed"

    return ""


def _extract_error_kind(item: dict[str, Any] | FileResult | None) -> str:
    if item is None:
        return ""

    if isinstance(item, FileResult):
        return item.compile_summary.error_kind

    compile_summary = item.get("compile_summary")
    if isinstance(compile_summary, dict):
        error_kind = compile_summary.get("error_kind")
        if isinstance(error_kind, str):
            return error_kind

    return ""


def _extract_first_error(item: dict[str, Any] | FileResult | None) -> str:
    if item is None:
        return ""

    if isinstance(item, FileResult):
        return item.compile_summary.first_error

    compile_summary = item.get("compile_summary")
    if isinstance(compile_summary, dict):
        first_error = compile_summary.get("first_error")
        if isinstance(first_error, str):
            return first_error

    return ""

