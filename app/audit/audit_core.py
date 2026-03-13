from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from ..bootstrap import build_run_paths
from ..models import (
    CompileSummary,
    DiffEntry,
    FileResult,
    RunConfig,
    RunPaths,
    RunResult,
    ScanCounts,
    SourceFingerprint,
)
from ..reports.report_ai_ready import write_ai_ready
from ..reports.report_details import write_file_detail_logs
from ..reports.report_json import write_summary_json
from ..reports.report_logs import (
    write_all_logs,
    write_all_scan_logs,
    write_master_log,
    write_top_errors,
)
from ..reports.report_md import write_summary_md
from .classifier import classify_file_results
from .compiler import compile_file, probe_gf_version
from .diff import build_diff_entries, find_previous_run_dir, load_previous_summary
from .file_selector import extract_module_name, select_files
from .fingerprint import build_source_fingerprint
from .result_model import (
    bucket_top_errors,
    build_file_result,
    build_run_result,
    update_run_counts,
)
from .scanner import scan_file


def run_audit(run_config: RunConfig, run_paths: RunPaths | None = None) -> RunResult:
    if run_config.mode == "file":
        return run_single_file_audit(run_config=run_config, run_paths=run_paths)
    return run_full_audit(run_config=run_config, run_paths=run_paths)


def run_single_file_audit(run_config: RunConfig, run_paths: RunPaths | None = None) -> RunResult:
    if not run_config.target_file:
        raise ValueError("target_file is required when mode='file'")
    return _run_audit_impl(run_config=run_config, run_paths=run_paths)


def run_full_audit(run_config: RunConfig, run_paths: RunPaths | None = None) -> RunResult:
    return _run_audit_impl(run_config=run_config, run_paths=run_paths)


def _run_audit_impl(run_config: RunConfig, run_paths: RunPaths | None = None) -> RunResult:
    started_at = datetime.now(timezone.utc)
    started_clock = perf_counter()

    run_paths = run_paths or build_run_paths(run_config)
    master_log_lines: list[str] = []
    file_results: list[FileResult] = []
    diff_entries: list[DiffEntry] = []
    gf_version = ""

    files_seen = 0
    files_excluded = 0
    excluded_noise_count = 0

    _log_master(master_log_lines, f"run_id={run_paths.run_id}")
    _log_master(master_log_lines, f"mode={run_config.mode}")
    _log_master(master_log_lines, f"project_root={run_config.project_root}")
    _log_master(master_log_lines, f"rgl_root={run_config.rgl_root}")
    _log_master(master_log_lines, f"gf_exe={run_config.gf_exe}")
    _log_master(master_log_lines, f"out_root={run_config.out_root}")
    _log_master(master_log_lines, f"run_dir={run_paths.run_dir}")
    _log_master(master_log_lines, f"scan_dir={run_config.scan_dir}")
    _log_master(master_log_lines, f"scan_glob={run_config.scan_glob}")
    _log_master(master_log_lines, f"timeout_sec={run_config.timeout_sec}")
    _log_master(master_log_lines, f"no_compile={run_config.no_compile}")
    _log_master(master_log_lines, f"target_file={run_config.target_file or ''}")

    try:
        if not run_config.skip_version_probe:
            try:
                gf_version = probe_gf_version(run_config=run_config, run_paths=run_paths)
                _log_master(master_log_lines, f"gf_version={gf_version}")
            except Exception as exc:
                _log_master(master_log_lines, f"warning: version_probe_failed={exc}")
                gf_version = ""

        selected_files, excluded_files = select_files(run_config)

        files_seen = len(selected_files) + len(excluded_files)
        files_excluded = len(excluded_files)
        excluded_noise_count = len(excluded_files)

        _log_master(master_log_lines, f"files_seen={files_seen}")
        _log_master(master_log_lines, f"files_included={len(selected_files)}")
        _log_master(master_log_lines, f"files_excluded={files_excluded}")

        for file_path in selected_files:
            _log_master(master_log_lines, f"file_start={file_path}")

            try:
                module_name = extract_module_name(file_path)
                _log_master(master_log_lines, f"module_name={module_name}")

                scan_counts, scan_log_path = scan_file(
                    file_path=file_path,
                    run_config=run_config,
                    run_paths=run_paths,
                )

                fingerprint = build_source_fingerprint(file_path)

                compile_summary = compile_file(
                    file_path=file_path,
                    run_config=run_config,
                    run_paths=run_paths,
                )

                file_result = build_file_result(
                    file_path=file_path,
                    status="SKIPPED" if run_config.no_compile else ("FAIL" if compile_summary.exit_code != 0 else "OK"),
                    diagnostic_class="skipped" if run_config.no_compile else ("ambiguous" if compile_summary.exit_code != 0 else "ok"),
                    is_direct=False,
                    blocked_by=[],
                    scan_counts=scan_counts,
                    fingerprint=fingerprint,
                    compile_summary=compile_summary,
                    scan_log_path=scan_log_path,
                )
                file_results.append(file_result)

                _log_master(
                    master_log_lines,
                    "file_done="
                    f"{file_path} "
                    f"exit_code={compile_summary.exit_code} "
                    f"timed_out={compile_summary.timed_out} "
                    f"error_kind={compile_summary.error_kind} "
                    f"first_error={compile_summary.first_error or ''}",
                )

            except Exception as exc:
                script_error_result = _build_script_error_file_result(
                    file_path=file_path,
                    error_message=str(exc),
                    fingerprint=_safe_fingerprint(file_path),
                )
                file_results.append(script_error_result)
                _log_master(master_log_lines, f"file_error={file_path} error={exc}")

        file_results = classify_file_results(file_results)

        finished_at = datetime.now(timezone.utc)
        duration_ms = int((perf_counter() - started_clock) * 1000)

        run_result = build_run_result(
            run_config=run_config,
            run_paths=run_paths,
            file_results=file_results,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            gf_version=gf_version,
            files_seen=files_seen,
            files_excluded=files_excluded,
            excluded_noise_count=excluded_noise_count,
            diff_entries=[],
            top_errors=[],
        )

        run_result = update_run_counts(run_result)
        run_result.top_errors = bucket_top_errors(run_result.file_results)

        if run_config.diff_previous:
            previous_run_dir = find_previous_run_dir(
                out_root=Path(run_config.out_root),
                current_run_dir=Path(run_paths.run_dir),
            )
            if previous_run_dir is not None:
                try:
                    previous_run_result = load_previous_summary(previous_run_dir / "summary.json")
                    if previous_run_result is not None:
                        diff_entries = build_diff_entries(
                            previous_run_result=previous_run_result,
                            current_run_result=run_result,
                        )
                except Exception as exc:
                    _log_master(master_log_lines, f"warning: diff_failed={exc}")
                    diff_entries = []

            run_result.diff_entries = diff_entries

        _write_reports(
            run_result=run_result,
            master_log_lines=master_log_lines,
        )

        return run_result

    except Exception as exc:
        finished_at = datetime.now(timezone.utc)
        duration_ms = int((perf_counter() - started_clock) * 1000)

        _log_master(master_log_lines, f"fatal_error={exc}")

        run_result = build_run_result(
            run_config=run_config,
            run_paths=run_paths,
            file_results=file_results,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            gf_version=gf_version,
            files_seen=files_seen,
            files_excluded=files_excluded,
            excluded_noise_count=excluded_noise_count,
            diff_entries=[],
            top_errors=[],
        )

        run_result = update_run_counts(run_result)
        run_result.top_errors = bucket_top_errors(run_result.file_results)

        _write_reports_best_effort(
            run_result=run_result,
            master_log_lines=master_log_lines,
        )

        raise


def _write_reports(run_result: RunResult, master_log_lines: list[str]) -> None:
    write_master_log(run_result.run_paths.master_log_path, master_log_lines)
    write_summary_json(run_result)
    write_summary_md(run_result)
    write_ai_ready(run_result)
    write_top_errors(run_result)
    write_file_detail_logs(run_result)
    write_all_scan_logs(run_result)
    write_all_logs(run_result)


def _write_reports_best_effort(run_result: RunResult, master_log_lines: list[str]) -> None:
    try:
        _write_reports(run_result=run_result, master_log_lines=master_log_lines)
    except Exception as report_exc:
        _log_master(master_log_lines, f"warning: report_write_failed={report_exc}")
        try:
            write_master_log(run_result.run_paths.master_log_path, master_log_lines)
        except Exception:
            pass


def _build_skipped_compile_summary() -> CompileSummary:
    return CompileSummary(
        exit_code=0,
        timed_out=False,
        duration_ms=0,
        error_kind="OK",
        first_error="",
        error_detail="compile skipped (-no-compile)",
        stdout_path=None,
        stderr_path=None,
    )


def _build_script_error_file_result(
    file_path: Path,
    error_message: str,
    fingerprint: SourceFingerprint,
) -> FileResult:
    compile_summary = CompileSummary(
        exit_code=998,
        timed_out=False,
        duration_ms=0,
        error_kind="SCRIPT",
        first_error=error_message,
        error_detail="",
        stdout_path=None,
        stderr_path=None,
    )

    return build_file_result(
        file_path=file_path,
        status="FAIL",
        diagnostic_class="ambiguous",
        is_direct=False,
        blocked_by=[],
        scan_counts=_empty_scan_counts(),
        fingerprint=fingerprint,
        compile_summary=compile_summary,
        scan_log_path=None,
    )


def _empty_scan_counts() -> ScanCounts:
    return ScanCounts(
        single_slash_eq=0,
        double_slash_dash=0,
        runtime_str_match=0,
        untyped_case_str_pat=0,
        untyped_table_str_pat=0,
        trailing_spaces=0,
    )


def _safe_fingerprint(file_path: Path) -> SourceFingerprint:
    try:
        return build_source_fingerprint(file_path)
    except Exception:
        return SourceFingerprint(
            size_bytes=0,
            sha1_short="",
            last_modified_utc="",
        )


def _log_master(master_log_lines: list[str], message: str) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    master_log_lines.append(f"{timestamp}  {message}")