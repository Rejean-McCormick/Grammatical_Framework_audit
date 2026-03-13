from __future__ import annotations

from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence

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


def build_file_result(
    *,
    file_path: str | Path,
    scan_counts: ScanCounts | None = None,
    fingerprint: SourceFingerprint | None = None,
    compile_summary: CompileSummary | None = None,
    scan_log_path: str | Path | None = None,
    status: str | None = None,
    diagnostic_class: str | None = None,
    is_direct: bool = False,
    blocked_by: Sequence[str] | None = None,
) -> FileResult:
    normalized_file_path = _normalize_file_path(file_path)
    normalized_scan_log_path = _normalize_optional_path(scan_log_path)

    effective_scan_counts = scan_counts or _default_scan_counts()
    effective_fingerprint = fingerprint or _default_source_fingerprint()

    effective_status = status or _derive_status(compile_summary)
    effective_diagnostic_class = diagnostic_class or _derive_diagnostic_class(effective_status)
    effective_compile_summary = compile_summary or _default_compile_summary()

    return FileResult(
        file_path=normalized_file_path,
        module_name=Path(normalized_file_path).stem,
        status=effective_status,
        diagnostic_class=effective_diagnostic_class,
        is_direct=bool(is_direct),
        blocked_by=[_normalize_file_path(item) for item in (blocked_by or [])],
        scan_counts=effective_scan_counts,
        fingerprint=effective_fingerprint,
        compile_summary=effective_compile_summary,
        scan_log_path=normalized_scan_log_path,
    )


def build_run_result(
    *,
    run_config: RunConfig,
    run_paths: RunPaths,
    file_results: Sequence[FileResult] | None = None,
    started_at: str | datetime | None = None,
    finished_at: str | datetime | None = None,
    duration_ms: int | None = None,
    gf_version: str = "",
    files_seen: int | None = None,
    files_excluded: int | None = None,
    excluded_noise_count: int | None = None,
    diff_entries: Sequence[DiffEntry] | None = None,
    top_errors: Mapping[str, int] | Sequence[tuple[str, int]] | None = None,
) -> RunResult:
    normalized_started_at = _normalize_timestamp(started_at)
    normalized_finished_at = _normalize_timestamp(finished_at)

    effective_file_results = list(file_results or [])
    effective_diff_entries = list(diff_entries or [])

    effective_duration_ms = duration_ms
    if effective_duration_ms is None:
        effective_duration_ms = _duration_ms_from_timestamps(
            normalized_started_at,
            normalized_finished_at,
        )

    effective_files_excluded = int(files_excluded) if files_excluded is not None else 0
    effective_files_seen = (
        int(files_seen)
        if files_seen is not None
        else len(effective_file_results) + effective_files_excluded
    )
    effective_excluded_noise_count = (
        int(excluded_noise_count)
        if excluded_noise_count is not None
        else effective_files_excluded
    )

    effective_top_errors = _normalize_top_errors(top_errors)
    if not effective_top_errors:
        effective_top_errors = bucket_top_errors(effective_file_results)

    run_result = RunResult(
        run_config=run_config,
        run_paths=run_paths,
        started_at=normalized_started_at,
        finished_at=normalized_finished_at,
        duration_ms=int(effective_duration_ms),
        gf_version=gf_version,
        files_seen=effective_files_seen,
        files_included=len(effective_file_results),
        files_excluded=effective_files_excluded,
        ok_count=0,
        fail_count=0,
        direct_fail_count=0,
        downstream_fail_count=0,
        ambiguous_fail_count=0,
        excluded_noise_count=effective_excluded_noise_count,
        file_results=effective_file_results,
        diff_entries=effective_diff_entries,
        top_errors=effective_top_errors,
    )

    return update_run_counts(run_result)


def update_run_counts(run_result: RunResult) -> RunResult:
    counts = _compute_counts(run_result.file_results)

    return replace(
        run_result,
        files_included=len(run_result.file_results),
        ok_count=counts["ok_count"],
        fail_count=counts["fail_count"],
        direct_fail_count=counts["direct_fail_count"],
        downstream_fail_count=counts["downstream_fail_count"],
        ambiguous_fail_count=counts["ambiguous_fail_count"],
    )


def bucket_top_errors(
    file_results: Iterable[FileResult],
    *,
    limit: int = 120,
) -> dict[str, int]:
    counter: Counter[str] = Counter()

    for file_result in file_results:
        if file_result.status != "FAIL":
            continue

        compile_summary = file_result.compile_summary
        error_kind = _safe_strip(getattr(compile_summary, "error_kind", ""))
        first_error = _safe_strip(getattr(compile_summary, "first_error", ""))

        if not error_kind or error_kind == "OK":
            continue
        if not first_error:
            continue

        bucket = f"[{error_kind}] {first_error}"
        counter[bucket] += 1

    ranked = sorted(
        counter.items(),
        key=lambda item: (-item[1], item[0].lower()),
    )

    if limit > 0:
        ranked = ranked[:limit]

    return {bucket: count for bucket, count in ranked}


def _compute_counts(file_results: Sequence[FileResult]) -> dict[str, int]:
    ok_count = 0
    fail_count = 0
    direct_fail_count = 0
    downstream_fail_count = 0
    ambiguous_fail_count = 0

    for file_result in file_results:
        status = _safe_strip(file_result.status).upper()
        diagnostic_class = _safe_strip(file_result.diagnostic_class).lower()

        if status == "OK":
            ok_count += 1
            continue

        if status == "FAIL":
            fail_count += 1

            if diagnostic_class == "direct":
                direct_fail_count += 1
            elif diagnostic_class == "downstream":
                downstream_fail_count += 1
            elif diagnostic_class == "ambiguous":
                ambiguous_fail_count += 1

    return {
        "ok_count": ok_count,
        "fail_count": fail_count,
        "direct_fail_count": direct_fail_count,
        "downstream_fail_count": downstream_fail_count,
        "ambiguous_fail_count": ambiguous_fail_count,
    }


def _derive_status(compile_summary: CompileSummary | None) -> str:
    if compile_summary is None:
        return "SKIPPED"

    if bool(getattr(compile_summary, "timed_out", False)):
        return "FAIL"

    exit_code = int(getattr(compile_summary, "exit_code", 0))
    if exit_code == 0:
        return "OK"

    return "FAIL"


def _derive_diagnostic_class(status: str) -> str:
    normalized_status = _safe_strip(status).upper()

    if normalized_status == "OK":
        return "ok"
    if normalized_status == "SKIPPED":
        return "skipped"
    return "ambiguous"


def _default_scan_counts() -> ScanCounts:
    return ScanCounts(
        single_slash_eq=0,
        double_slash_dash=0,
        runtime_str_match=0,
        untyped_case_str_pat=0,
        untyped_table_str_pat=0,
        trailing_spaces=0,
    )


def _default_source_fingerprint() -> SourceFingerprint:
    return SourceFingerprint(
        size_bytes=0,
        sha1_short="",
        last_modified_utc="",
    )


def _default_compile_summary() -> CompileSummary:
    return CompileSummary(
        exit_code=0,
        timed_out=False,
        duration_ms=0,
        error_kind="OK",
        first_error="",
        error_detail="",
        stdout_path=None,
        stderr_path=None,
    )


def _normalize_timestamp(value: str | datetime | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()

    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return datetime.now(timezone.utc).isoformat()

    return text


def _duration_ms_from_timestamps(started_at: str, finished_at: str) -> int:
    try:
        started_dt = datetime.fromisoformat(started_at)
        finished_dt = datetime.fromisoformat(finished_at)

        if started_dt.tzinfo is None:
            started_dt = started_dt.replace(tzinfo=timezone.utc)
        if finished_dt.tzinfo is None:
            finished_dt = finished_dt.replace(tzinfo=timezone.utc)

        delta = finished_dt - started_dt
        return max(0, int(delta.total_seconds() * 1000))
    except Exception:
        return 0


def _normalize_file_path(value: str | Path) -> str:
    return Path(str(value)).as_posix()


def _normalize_optional_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    return Path(text)


def _normalize_top_errors(
    value: Mapping[str, int] | Sequence[tuple[str, int]] | None,
) -> dict[str, int]:
    if value is None:
        return {}

    if isinstance(value, Mapping):
        return {str(bucket): int(count) for bucket, count in value.items()}

    normalized: dict[str, int] = {}
    for item in value:
        if not isinstance(item, tuple) or len(item) != 2:
            continue
        bucket, count = item
        normalized[str(bucket)] = int(count)
    return normalized


def _safe_strip(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()

