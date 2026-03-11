from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.audit.diff import build_diff_entries, find_previous_run_dir, load_previous_summary
from app.models import CompileSummary, DiffEntry, FileResult, RunConfig, RunPaths, RunResult, ScanCounts, SourceFingerprint


def _make_run_config(out_root: Path) -> RunConfig:
    return RunConfig(
        project_root=Path("C:/work/project"),
        rgl_root=Path("C:/work/gf-rgl/src"),
        gf_exe=Path("C:/work/gf.exe"),
        out_root=out_root,
        scan_dir="lib/src/albanian",
        scan_glob="*.gf",
        gf_path="lib/src:lib/src/albanian:abstract:common:prelude",
        timeout_sec=60,
        max_files=0,
        skip_version_probe=False,
        no_compile=False,
        emit_cpu_stats=False,
        mode="all",
        target_file="",
        include_regex=r"^[A-Z][A-Za-z0-9_]*\.gf$",
        exclude_regex=r"( - Copie\.gf$|\.bak\.gf$|\.tmp\.gf$|\.disabled\.gf$|\s)",
        keep_ok_details=False,
        diff_previous=True,
    )


def _make_run_paths(out_root: Path, run_id: str) -> RunPaths:
    run_dir = out_root / f"run_{run_id}"
    return RunPaths(
        run_id=run_id,
        run_dir=run_dir,
        master_log_path=run_dir / "raw" / "master.log",
        all_scan_logs_path=run_dir / "raw" / "ALL_SCAN_LOGS.TXT",
        all_logs_path=run_dir / "raw" / "ALL_LOGS.TXT",
        summary_json_path=run_dir / "summary.json",
        summary_md_path=run_dir / "summary.md",
        ai_brief_path=run_dir / "ai_brief.txt",
        top_errors_path=run_dir / "top_errors.txt",
        details_dir=run_dir / "details",
        raw_dir=run_dir / "raw",
        compile_logs_dir=run_dir / "raw" / "compile",
        scan_logs_dir=run_dir / "raw" / "scan",
        artifacts_dir=run_dir / "artifacts",
        gfo_dir=run_dir / "artifacts" / "gfo",
        out_dir=run_dir / "artifacts" / "out",
    )


def _make_compile_summary(
    *,
    exit_code: int,
    error_kind: str,
    first_error: str = "",
    duration_ms: int = 10,
) -> CompileSummary:
    return CompileSummary(
        exit_code=exit_code,
        timed_out=False,
        duration_ms=duration_ms,
        error_kind=error_kind,
        first_error=first_error,
        error_detail="",
        stdout_path=Path("stdout.txt"),
        stderr_path=Path("stderr.txt"),
    )


def _make_scan_counts() -> ScanCounts:
    return ScanCounts(
        single_slash_eq=0,
        double_slash_dash=0,
        runtime_str_match=0,
        untyped_case_str_pat=0,
        untyped_table_str_pat=0,
        trailing_spaces=0,
    )


def _make_fingerprint() -> SourceFingerprint:
    return SourceFingerprint(
        size_bytes=123,
        sha1_short="abc1234",
        last_modified_utc="2026-03-11T12:00:00Z",
    )


def _make_file_result(
    file_path: str,
    *,
    status: str,
    diagnostic_class: str,
    error_kind: str,
    first_error: str = "",
    blocked_by: list[str] | None = None,
) -> FileResult:
    return FileResult(
        file_path=file_path,
        module_name=Path(file_path).stem,
        status=status,
        diagnostic_class=diagnostic_class,
        is_direct=(diagnostic_class == "direct"),
        blocked_by=blocked_by or [],
        scan_counts=_make_scan_counts(),
        fingerprint=_make_fingerprint(),
        compile_summary=_make_compile_summary(
            exit_code=0 if status == "OK" else 1,
            error_kind=error_kind,
            first_error=first_error,
        ),
        scan_log_path=Path(f"{Path(file_path).stem}.scan.txt"),
    )


def _make_run_result(
    out_root: Path,
    run_id: str,
    file_results: list[FileResult],
) -> RunResult:
    fail_count = sum(1 for item in file_results if item.status == "FAIL")
    ok_count = sum(1 for item in file_results if item.status == "OK")
    direct_fail_count = sum(1 for item in file_results if item.diagnostic_class == "direct")
    downstream_fail_count = sum(1 for item in file_results if item.diagnostic_class == "downstream")
    ambiguous_fail_count = sum(1 for item in file_results if item.diagnostic_class == "ambiguous")

    return RunResult(
        run_config=_make_run_config(out_root),
        run_paths=_make_run_paths(out_root, run_id),
        started_at="2026-03-11T12:00:00Z",
        finished_at="2026-03-11T12:00:02Z",
        duration_ms=2000,
        gf_version="3.12",
        files_seen=len(file_results),
        files_included=len(file_results),
        files_excluded=0,
        ok_count=ok_count,
        fail_count=fail_count,
        direct_fail_count=direct_fail_count,
        downstream_fail_count=downstream_fail_count,
        ambiguous_fail_count=ambiguous_fail_count,
        excluded_noise_count=0,
        file_results=file_results,
        diff_entries=[],
        top_errors=[],
    )


def test_find_previous_run_dir_returns_latest_older_run(tmp_path: Path) -> None:
    out_root = tmp_path / "_gf_audit"
    older = out_root / "run_20260311_100000"
    previous = out_root / "run_20260311_110000"
    current = out_root / "run_20260311_120000"

    older.mkdir(parents=True)
    previous.mkdir(parents=True)
    current.mkdir(parents=True)

    result = find_previous_run_dir(out_root=out_root, current_run_dir=current)

    assert result == previous


def test_find_previous_run_dir_ignores_non_run_directories(tmp_path: Path) -> None:
    out_root = tmp_path / "_gf_audit"
    (out_root / "cache").mkdir(parents=True)
    (out_root / "notes").mkdir(parents=True)
    current = out_root / "run_20260311_120000"
    current.mkdir(parents=True)

    result = find_previous_run_dir(out_root=out_root, current_run_dir=current)

    assert result is None


def test_build_diff_entries_marks_improved_regressed_new_and_removed(tmp_path: Path) -> None:
    out_root = tmp_path / "_gf_audit"

    previous_run_result = _make_run_result(
        out_root=out_root,
        run_id="20260311_110000",
        file_results=[
            _make_file_result(
                "lib/src/albanian/GrammarSqi.gf",
                status="FAIL",
                diagnostic_class="direct",
                error_kind="OTHER",
                first_error="lib/src/albanian/GrammarSqi.gf: cannot unify",
            ),
            _make_file_result(
                "lib/src/albanian/ExtendSqi.gf",
                status="FAIL",
                diagnostic_class="downstream",
                error_kind="OTHER",
                first_error="lib/src/albanian/GrammarSqi.gf",
                blocked_by=["lib/src/albanian/GrammarSqi.gf"],
            ),
            _make_file_result(
                "lib/src/albanian/MorphoSqi.gf",
                status="OK",
                diagnostic_class="ok",
                error_kind="OK",
            ),
        ],
    )

    current_run_result = _make_run_result(
        out_root=out_root,
        run_id="20260311_120000",
        file_results=[
            _make_file_result(
                "lib/src/albanian/GrammarSqi.gf",
                status="FAIL",
                diagnostic_class="direct",
                error_kind="OTHER",
                first_error="lib/src/albanian/GrammarSqi.gf: still failing",
            ),
            _make_file_result(
                "lib/src/albanian/ExtendSqi.gf",
                status="OK",
                diagnostic_class="ok",
                error_kind="OK",
            ),
            _make_file_result(
                "lib/src/albanian/StructuralSqi.gf",
                status="FAIL",
                diagnostic_class="direct",
                error_kind="INTERNAL",
                first_error="Internal error in GeneratePMCFG",
            ),
        ],
    )

    diff_entries = build_diff_entries(
        previous_run_result=previous_run_result,
        current_run_result=current_run_result,
    )

    entries_by_file = {entry.file_path: entry for entry in diff_entries}

    assert entries_by_file["lib/src/albanian/GrammarSqi.gf"].change_kind == "unchanged"
    assert entries_by_file["lib/src/albanian/GrammarSqi.gf"].previous_status == "FAIL"
    assert entries_by_file["lib/src/albanian/GrammarSqi.gf"].current_status == "FAIL"

    assert entries_by_file["lib/src/albanian/ExtendSqi.gf"].change_kind == "improved"
    assert entries_by_file["lib/src/albanian/ExtendSqi.gf"].previous_status == "FAIL"
    assert entries_by_file["lib/src/albanian/ExtendSqi.gf"].current_status == "OK"

    assert entries_by_file["lib/src/albanian/StructuralSqi.gf"].change_kind == "new"
    assert entries_by_file["lib/src/albanian/StructuralSqi.gf"].previous_status == ""
    assert entries_by_file["lib/src/albanian/StructuralSqi.gf"].current_status == "FAIL"

    assert entries_by_file["lib/src/albanian/MorphoSqi.gf"].change_kind == "removed"
    assert entries_by_file["lib/src/albanian/MorphoSqi.gf"].previous_status == "OK"
    assert entries_by_file["lib/src/albanian/MorphoSqi.gf"].current_status == ""


def test_build_diff_entries_marks_regression_when_ok_becomes_fail(tmp_path: Path) -> None:
    out_root = tmp_path / "_gf_audit"

    previous_run_result = _make_run_result(
        out_root=out_root,
        run_id="20260311_110000",
        file_results=[
            _make_file_result(
                "lib/src/albanian/LangSqi.gf",
                status="OK",
                diagnostic_class="ok",
                error_kind="OK",
            ),
        ],
    )

    current_run_result = _make_run_result(
        out_root=out_root,
        run_id="20260311_120000",
        file_results=[
            _make_file_result(
                "lib/src/albanian/LangSqi.gf",
                status="FAIL",
                diagnostic_class="downstream",
                error_kind="OTHER",
                first_error="lib/src/albanian/GrammarSqi.gf",
                blocked_by=["lib/src/albanian/GrammarSqi.gf"],
            ),
        ],
    )

    diff_entries = build_diff_entries(
        previous_run_result=previous_run_result,
        current_run_result=current_run_result,
    )

    assert len(diff_entries) == 1
    assert diff_entries[0].file_path == "lib/src/albanian/LangSqi.gf"
    assert diff_entries[0].change_kind == "regressed"
    assert diff_entries[0].previous_status == "OK"
    assert diff_entries[0].current_status == "FAIL"


def test_load_previous_summary_reads_summary_json(tmp_path: Path) -> None:
    run_dir = tmp_path / "run_20260311_110000"
    run_dir.mkdir(parents=True)

    summary_path = run_dir / "summary.json"
    payload = {
        "run_paths": {
            "run_id": "20260311_110000",
            "run_dir": str(run_dir),
            "summary_json_path": str(summary_path),
        },
        "file_results": [
            {
                "file_path": "lib/src/albanian/GrammarSqi.gf",
                "module_name": "GrammarSqi",
                "status": "FAIL",
                "diagnostic_class": "direct",
                "is_direct": True,
                "blocked_by": [],
                "scan_counts": {
                    "single_slash_eq": 0,
                    "double_slash_dash": 0,
                    "runtime_str_match": 0,
                    "untyped_case_str_pat": 0,
                    "untyped_table_str_pat": 0,
                    "trailing_spaces": 0,
                },
                "fingerprint": {
                    "size_bytes": 123,
                    "sha1_short": "abc1234",
                    "last_modified_utc": "2026-03-11T12:00:00Z",
                },
                "compile_summary": {
                    "exit_code": 1,
                    "timed_out": False,
                    "duration_ms": 10,
                    "error_kind": "OTHER",
                    "first_error": "lib/src/albanian/GrammarSqi.gf: cannot unify",
                    "error_detail": "",
                    "stdout_path": "stdout.txt",
                    "stderr_path": "stderr.txt",
                },
                "scan_log_path": "GrammarSqi.scan.txt",
            }
        ],
    }
    summary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    loaded = load_previous_summary(summary_path)

    assert loaded is not None
    assert loaded.run_paths.run_id == "20260311_110000"
    assert len(loaded.file_results) == 1
    assert loaded.file_results[0].file_path == "lib/src/albanian/GrammarSqi.gf"
    assert loaded.file_results[0].status == "FAIL"


def test_load_previous_summary_returns_none_when_file_is_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing_summary.json"

    loaded = load_previous_summary(missing_path)

    assert loaded is None


def test_build_diff_entries_returns_diff_entry_objects(tmp_path: Path) -> None:
    out_root = tmp_path / "_gf_audit"

    previous_run_result = _make_run_result(
        out_root=out_root,
        run_id="20260311_110000",
        file_results=[],
    )
    current_run_result = _make_run_result(
        out_root=out_root,
        run_id="20260311_120000",
        file_results=[
            _make_file_result(
                "lib/src/albanian/TestSqi.gf",
                status="OK",
                diagnostic_class="ok",
                error_kind="OK",
            ),
        ],
    )

    diff_entries = build_diff_entries(
        previous_run_result=previous_run_result,
        current_run_result=current_run_result,
    )

    assert len(diff_entries) == 1
    assert isinstance(diff_entries[0], DiffEntry)
    assert diff_entries[0].change_kind == "new"