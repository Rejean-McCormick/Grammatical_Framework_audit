from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models import (
    CompileSummary,
    DiffEntry,
    FileResult,
    RunConfig,
    RunPaths,
    RunResult,
    ScanCounts,
    SourceFingerprint,
)


def find_previous_run_dir(*, out_root: Path, current_run_dir: Path) -> Path | None:
    """
    Find the most recent run_* directory strictly older than current_run_dir.

    Expected layout:
      out_root/
        run_YYYYMMDD_HHMMSS/
        run_YYYYMMDD_HHMMSS/
    """
    resolved_out_root = Path(out_root)
    resolved_current_run_dir = Path(current_run_dir)

    if not resolved_out_root.exists() or not resolved_out_root.is_dir():
        return None

    candidate_dirs = sorted(
        (
            entry
            for entry in resolved_out_root.iterdir()
            if entry.is_dir() and entry.name.startswith("run_")
        ),
        key=lambda entry: entry.name,
    )

    previous_candidates = [
        entry
        for entry in candidate_dirs
        if entry.name < resolved_current_run_dir.name
    ]

    if not previous_candidates:
        return None

    return previous_candidates[-1]


def load_previous_summary(summary_path: Path | None) -> RunResult | None:
    """
    Load a previous summary.json and rebuild a minimal RunResult object.

    Accepts either:
      - a direct path to summary.json
      - a run directory containing summary.json
    """
    if summary_path is None:
        return None

    resolved_input = Path(summary_path)
    resolved_summary_path = (
        resolved_input / "summary.json"
        if resolved_input.exists() and resolved_input.is_dir()
        else resolved_input
    )

    if not resolved_summary_path.exists() or not resolved_summary_path.is_file():
        return None

    try:
        payload = json.loads(resolved_summary_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    if not isinstance(payload, dict):
        return None

    run_paths = _build_run_paths_from_payload(
        summary_path=resolved_summary_path,
        payload=payload.get("run_paths", {}),
    )
    run_config = _build_run_config_from_payload(
        out_root=run_paths.run_dir.parent,
        payload=payload.get("run_config", {}),
    )
    file_results = [
        _build_file_result_from_payload(item)
        for item in payload.get("file_results", [])
        if isinstance(item, dict)
    ]
    diff_entries = [
        _build_diff_entry_from_payload(item)
        for item in payload.get("diff_entries", [])
        if isinstance(item, dict)
    ]
    top_errors = _normalize_top_errors(payload.get("top_errors", {}))

    run_result = RunResult(
        run_config=run_config,
        run_paths=run_paths,
        started_at=payload.get("started_at", "1970-01-01T00:00:00+00:00"),
        finished_at=payload.get("finished_at", "1970-01-01T00:00:00+00:00"),
        duration_ms=int(payload.get("duration_ms", 0)),
        gf_version=str(payload.get("gf_version", "")),
        files_seen=int(payload.get("files_seen", len(file_results))),
        files_included=int(payload.get("files_included", len(file_results))),
        files_excluded=int(payload.get("files_excluded", 0)),
        ok_count=int(payload.get("ok_count", 0)),
        fail_count=int(payload.get("fail_count", 0)),
        direct_fail_count=int(payload.get("direct_fail_count", 0)),
        downstream_fail_count=int(payload.get("downstream_fail_count", 0)),
        ambiguous_fail_count=int(payload.get("ambiguous_fail_count", 0)),
        excluded_noise_count=int(payload.get("excluded_noise_count", 0)),
        file_results=file_results,
        diff_entries=diff_entries,
        top_errors=top_errors,
    )
    run_result.recompute_counts()
    return run_result


def build_diff_entries(
    *,
    previous_run_result: RunResult,
    current_run_result: RunResult,
) -> list[DiffEntry]:
    """
    Compare two RunResult objects and return normalized DiffEntry objects.

    change_kind values:
      - unchanged
      - improved
      - regressed
      - new
      - removed
    """
    previous_file_map = _build_file_map(previous_run_result.file_results)
    current_file_map = _build_file_map(current_run_result.file_results)

    all_keys = sorted(set(previous_file_map) | set(current_file_map))
    diff_entries: list[DiffEntry] = []

    for normalized_key in all_keys:
        previous_item = previous_file_map.get(normalized_key)
        current_item = current_file_map.get(normalized_key)

        file_path = _diff_display_path(previous_item, current_item)
        previous_status = previous_item.status if previous_item is not None else ""
        current_status = current_item.status if current_item is not None else ""

        if previous_item is None and current_item is not None:
            change_kind = "new"
            message = f"{file_path}: new ({current_status})"
        elif previous_item is not None and current_item is None:
            change_kind = "removed"
            message = f"{file_path}: removed (was {previous_status})"
        elif previous_status == current_status:
            detail_change_message = _build_detail_change_message(previous_item, current_item)
            change_kind = "unchanged"
            if detail_change_message:
                message = f"{file_path}: unchanged ({current_status}), {detail_change_message}"
            else:
                message = f"{file_path}: unchanged ({current_status})"
        elif _is_improvement(previous_status, current_status):
            change_kind = "improved"
            message = f"{file_path}: {previous_status} -> {current_status}"
        elif _is_regression(previous_status, current_status):
            change_kind = "regressed"
            message = f"{file_path}: {previous_status} -> {current_status}"
        else:
            change_kind = "unchanged"
            message = f"{file_path}: {previous_status} -> {current_status}"

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


def _build_run_config_from_payload(out_root: Path, payload: dict[str, Any]) -> RunConfig:
    return RunConfig(
        project_root=Path(payload.get("project_root", ".")),
        rgl_root=Path(payload.get("rgl_root", ".")),
        gf_exe=Path(payload.get("gf_exe", "gf")),
        out_root=Path(payload.get("out_root", out_root)),
        scan_dir=str(payload.get("scan_dir", "lib/src/albanian")),
        scan_glob=str(payload.get("scan_glob", "*.gf")),
        gf_path=str(payload.get("gf_path", "")),
        timeout_sec=int(payload.get("timeout_sec", 60)),
        max_files=int(payload.get("max_files", 0)),
        skip_version_probe=bool(payload.get("skip_version_probe", False)),
        no_compile=bool(payload.get("no_compile", False)),
        emit_cpu_stats=bool(payload.get("emit_cpu_stats", False)),
        mode=str(payload.get("mode", "all")),
        target_file=str(payload.get("target_file", "")),
        include_regex=str(payload.get("include_regex", r"^[A-Z][A-Za-z0-9_]*\.gf$")),
        exclude_regex=str(payload.get("exclude_regex", r"( - Copie\.gf$|\.bak\.gf$|\.tmp\.gf$|\.disabled\.gf$|\s)")),
        keep_ok_details=bool(payload.get("keep_ok_details", False)),
        diff_previous=bool(payload.get("diff_previous", True)),
    )


def _build_run_paths_from_payload(summary_path: Path, payload: dict[str, Any]) -> RunPaths:
    run_dir = Path(payload.get("run_dir", summary_path.parent))
    raw_dir = Path(payload.get("raw_dir", run_dir / "raw"))
    details_dir = Path(payload.get("details_dir", run_dir / "details"))
    artifacts_dir = Path(payload.get("artifacts_dir", run_dir / "artifacts"))

    return RunPaths(
        run_id=str(payload.get("run_id", run_dir.name.removeprefix("run_"))),
        run_dir=run_dir,
        master_log_path=Path(payload.get("master_log_path", raw_dir / "master.log")),
        all_scan_logs_path=Path(payload.get("all_scan_logs_path", raw_dir / "ALL_SCAN_LOGS.TXT")),
        all_logs_path=Path(payload.get("all_logs_path", raw_dir / "ALL_LOGS.TXT")),
        summary_json_path=Path(payload.get("summary_json_path", summary_path)),
        summary_md_path=Path(payload.get("summary_md_path", run_dir / "summary.md")),
        ai_brief_path=Path(payload.get("ai_brief_path", run_dir / "ai_brief.txt")),
        top_errors_path=Path(payload.get("top_errors_path", run_dir / "top_errors.txt")),
        details_dir=details_dir,
        raw_dir=raw_dir,
        compile_logs_dir=Path(payload.get("compile_logs_dir", raw_dir / "compile")),
        scan_logs_dir=Path(payload.get("scan_logs_dir", raw_dir / "scan")),
        artifacts_dir=artifacts_dir,
        gfo_dir=Path(payload.get("gfo_dir", artifacts_dir / "gfo")),
        out_dir=Path(payload.get("out_dir", artifacts_dir / "out")),
    )


def _build_file_result_from_payload(payload: dict[str, Any]) -> FileResult:
    file_path = _display_path(payload.get("file_path", ""))
    module_name = str(payload.get("module_name", Path(file_path).stem))
    compile_payload = payload.get("compile_summary", {})
    scan_payload = payload.get("scan_counts", {})
    fingerprint_payload = payload.get("fingerprint", {})

    return FileResult(
        file_path=file_path,
        module_name=module_name,
        status=str(payload.get("status", "SKIPPED")),
        diagnostic_class=str(payload.get("diagnostic_class", "skipped")),
        is_direct=bool(payload.get("is_direct", False)),
        blocked_by=[_display_path(item) for item in payload.get("blocked_by", [])],
        scan_counts=ScanCounts(
            single_slash_eq=int(scan_payload.get("single_slash_eq", 0)),
            double_slash_dash=int(scan_payload.get("double_slash_dash", 0)),
            runtime_str_match=int(scan_payload.get("runtime_str_match", 0)),
            untyped_case_str_pat=int(scan_payload.get("untyped_case_str_pat", 0)),
            untyped_table_str_pat=int(scan_payload.get("untyped_table_str_pat", 0)),
            trailing_spaces=int(scan_payload.get("trailing_spaces", 0)),
        ),
        fingerprint=SourceFingerprint(
            size_bytes=int(fingerprint_payload.get("size_bytes", 0)),
            sha1_short=str(fingerprint_payload.get("sha1_short", "")),
            last_modified_utc=str(fingerprint_payload.get("last_modified_utc", "")),
        ),
        compile_summary=CompileSummary(
            exit_code=int(compile_payload.get("exit_code", 0)),
            timed_out=bool(compile_payload.get("timed_out", False)),
            duration_ms=int(compile_payload.get("duration_ms", 0)),
            error_kind=str(compile_payload.get("error_kind", "OK")),
            first_error=str(compile_payload.get("first_error", "")),
            error_detail=str(compile_payload.get("error_detail", "")),
            stdout_path=Path(str(compile_payload.get("stdout_path", "stdout.txt"))),
            stderr_path=Path(str(compile_payload.get("stderr_path", "stderr.txt"))),
        ),
        scan_log_path=Path(str(payload.get("scan_log_path", f"{module_name}.scan.txt"))),
    )


def _build_diff_entry_from_payload(payload: dict[str, Any]) -> DiffEntry:
    return DiffEntry(
        file_path=_display_path(payload.get("file_path", "")),
        previous_status=str(payload.get("previous_status", "")),
        current_status=str(payload.get("current_status", "")),
        change_kind=str(payload.get("change_kind", "unchanged")),
        message=str(payload.get("message", "")),
    )


def _build_file_map(file_results: list[FileResult]) -> dict[str, FileResult]:
    result: dict[str, FileResult] = {}
    for file_result in file_results:
        result[_file_key(file_result.file_path)] = file_result
    return result


def _diff_display_path(previous_item: FileResult | None, current_item: FileResult | None) -> str:
    if current_item is not None:
        return _display_path(current_item.file_path)
    if previous_item is not None:
        return _display_path(previous_item.file_path)
    return ""


def _normalize_top_errors(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(key): int(count) for key, count in value.items()}


def _is_improvement(previous_status: str, current_status: str) -> bool:
    return previous_status == "FAIL" and current_status == "OK"


def _is_regression(previous_status: str, current_status: str) -> bool:
    return previous_status == "OK" and current_status == "FAIL"


def _build_detail_change_message(
    previous_item: FileResult | None,
    current_item: FileResult | None,
) -> str:
    if previous_item is None or current_item is None:
        return ""

    previous_error_kind = str(previous_item.compile_summary.error_kind or "")
    current_error_kind = str(current_item.compile_summary.error_kind or "")
    previous_first_error = str(previous_item.compile_summary.first_error or "")
    current_first_error = str(current_item.compile_summary.first_error or "")

    if previous_error_kind != current_error_kind and previous_error_kind and current_error_kind:
        return f"error kind changed: {previous_error_kind} -> {current_error_kind}"

    if previous_first_error != current_first_error and previous_first_error and current_first_error:
        return "first error changed"

    return ""


def _display_path(value: object) -> str:
    if value is None:
        return ""
    return str(value).replace("\\", "/").strip()


def _file_key(value: object) -> str:
    return _display_path(value).lower()