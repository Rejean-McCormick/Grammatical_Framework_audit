from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.reports.report_ai_brief import write_ai_brief


def _make_scan_counts(
    single_slash_eq: int = 0,
    double_slash_dash: int = 0,
    runtime_str_match: int = 0,
    untyped_case_str_pat: int = 0,
    untyped_table_str_pat: int = 0,
    trailing_spaces: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        single_slash_eq=single_slash_eq,
        double_slash_dash=double_slash_dash,
        runtime_str_match=runtime_str_match,
        untyped_case_str_pat=untyped_case_str_pat,
        untyped_table_str_pat=untyped_table_str_pat,
        trailing_spaces=trailing_spaces,
    )


def _make_compile_summary(
    error_kind: str = "OK",
    first_error: str = "",
    stdout_path: str | Path = "",
    stderr_path: str | Path = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        exit_code=0 if error_kind == "OK" else 1,
        timed_out=False,
        duration_ms=12,
        error_kind=error_kind,
        first_error=first_error,
        error_detail="",
        stdout_path=Path(stdout_path) if stdout_path else "",
        stderr_path=Path(stderr_path) if stderr_path else "",
    )


def _make_file_result(
    file_path: str,
    status: str,
    diagnostic_class: str,
    blocked_by: list[str] | None = None,
    scan_counts: SimpleNamespace | None = None,
    compile_summary: SimpleNamespace | None = None,
    scan_log_path: str | Path = "",
) -> SimpleNamespace:
    return SimpleNamespace(
        file_path=file_path,
        module_name=Path(file_path).stem,
        status=status,
        diagnostic_class=diagnostic_class,
        is_direct=diagnostic_class == "direct",
        blocked_by=blocked_by or [],
        scan_counts=scan_counts or _make_scan_counts(),
        fingerprint=None,
        compile_summary=compile_summary or _make_compile_summary(),
        scan_log_path=Path(scan_log_path) if scan_log_path else "",
    )


def _make_run_result(tmp_path: Path, file_results: list[SimpleNamespace]) -> SimpleNamespace:
    run_dir = tmp_path / "run_20260311_163720"
    ai_brief_path = run_dir / "ai_brief.txt"
    summary_json_path = run_dir / "summary.json"
    summary_md_path = run_dir / "summary.md"
    master_log_path = run_dir / "master.log"
    all_scan_logs_path = run_dir / "ALL_SCAN_LOGS.TXT"
    all_logs_path = run_dir / "ALL_LOGS.TXT"

    fail_count = sum(1 for item in file_results if item.status == "FAIL")
    ok_count = sum(1 for item in file_results if item.status == "OK")
    direct_fail_count = sum(1 for item in file_results if item.diagnostic_class == "direct")
    downstream_fail_count = sum(1 for item in file_results if item.diagnostic_class == "downstream")
    ambiguous_fail_count = sum(1 for item in file_results if item.diagnostic_class == "ambiguous")

    return SimpleNamespace(
        run_config=SimpleNamespace(mode="all"),
        run_paths=SimpleNamespace(
            run_id="20260311_163720",
            run_dir=run_dir,
            ai_brief_path=ai_brief_path,
            summary_json_path=summary_json_path,
            summary_md_path=summary_md_path,
            master_log_path=master_log_path,
            all_scan_logs_path=all_scan_logs_path,
            all_logs_path=all_logs_path,
        ),
        started_at="2026-03-11T16:37:20Z",
        finished_at="2026-03-11T16:38:00Z",
        duration_ms=40000,
        gf_version="3.12.0",
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
        diff_entries=[
            SimpleNamespace(
                file_path="lib/src/albanian/GrammarSqi.gf",
                previous_status="FAIL",
                current_status="FAIL",
                change_kind="unchanged",
                message="still FAIL",
            ),
            SimpleNamespace(
                file_path="lib/src/albanian/SymbolSqi.gf",
                previous_status="FAIL",
                current_status="OK",
                change_kind="improved",
                message="FAIL -> OK",
            ),
        ],
        top_errors=[
            ("[OTHER] cannot unify the information", 3),
            ("[INTERNAL] Internal error in GeneratePMCFG", 1),
        ],
    )


def test_write_ai_brief_writes_expected_sections(tmp_path: Path) -> None:
    direct = _make_file_result(
        file_path="lib/src/albanian/GrammarSqi.gf",
        status="FAIL",
        diagnostic_class="direct",
        compile_summary=_make_compile_summary(
            error_kind="OTHER",
            first_error="cannot unify the information oper sep : Str",
            stdout_path=tmp_path / "details" / "GrammarSqi.out.txt",
            stderr_path=tmp_path / "details" / "GrammarSqi.err.txt",
        ),
        scan_log_path=tmp_path / "details" / "GrammarSqi.scan.txt",
    )

    downstream = _make_file_result(
        file_path="lib/src/albanian/LangSqi.gf",
        status="FAIL",
        diagnostic_class="downstream",
        blocked_by=["lib/src/albanian/GrammarSqi.gf"],
        compile_summary=_make_compile_summary(
            error_kind="OTHER",
            first_error="blocked by failed dependency GrammarSqi.gf",
            stdout_path=tmp_path / "details" / "LangSqi.out.txt",
            stderr_path=tmp_path / "details" / "LangSqi.err.txt",
        ),
        scan_log_path=tmp_path / "details" / "LangSqi.scan.txt",
    )

    ambiguous = _make_file_result(
        file_path="lib/src/albanian/AllSqi.gf",
        status="FAIL",
        diagnostic_class="ambiguous",
        blocked_by=["lib/src/albanian/NounSqi.gf"],
        compile_summary=_make_compile_summary(
            error_kind="OTHER",
            first_error="first error points to NounSqi.gf",
            stdout_path=tmp_path / "details" / "AllSqi.out.txt",
            stderr_path=tmp_path / "details" / "AllSqi.err.txt",
        ),
        scan_log_path=tmp_path / "details" / "AllSqi.scan.txt",
    )

    ok_with_scan_hits = _make_file_result(
        file_path="lib/src/albanian/MorphoSqi.gf",
        status="OK",
        diagnostic_class="ok",
        scan_counts=_make_scan_counts(runtime_str_match=2, trailing_spaces=1),
        compile_summary=_make_compile_summary(error_kind="OK"),
    )

    ok_clean = _make_file_result(
        file_path="lib/src/albanian/NounSqi.gf",
        status="OK",
        diagnostic_class="ok",
        scan_counts=_make_scan_counts(),
        compile_summary=_make_compile_summary(error_kind="OK"),
    )

    run_result = _make_run_result(
        tmp_path,
        [direct, downstream, ambiguous, ok_with_scan_hits, ok_clean],
    )

    written_path = write_ai_brief(run_result)
    assert written_path == run_result.run_paths.ai_brief_path
    assert written_path.exists()

    content = written_path.read_text(encoding="utf-8")

    assert "RUN: 20260311_163720" in content
    assert "MODE: all" in content
    assert "GF_VERSION: 3.12.0" in content

    assert "DIRECT FAILURES:" in content
    assert "1. lib/src/albanian/GrammarSqi.gf" in content
    assert "kind: OTHER" in content
    assert "first_error: cannot unify the information oper sep : Str" in content

    assert "DOWNSTREAM FAILURES:" in content
    assert "1. lib/src/albanian/LangSqi.gf" in content
    assert "blocked_by: lib/src/albanian/GrammarSqi.gf" in content

    assert "AMBIGUOUS FAILURES:" in content
    assert "1. lib/src/albanian/AllSqi.gf" in content

    assert "HEURISTIC SCAN NOTES:" in content
    assert "lib/src/albanian/MorphoSqi.gf: compile OK, scan hits -> runtime_str_match=2, trailing_spaces=1" in content
    assert "lib/src/albanian/NounSqi.gf" not in content

    assert "CHANGES SINCE PREVIOUS RUN:" in content
    assert "- lib/src/albanian/SymbolSqi.gf: FAIL -> OK" in content
    assert "- lib/src/albanian/GrammarSqi.gf: still FAIL" not in content

    assert "TOP ERRORS:" in content
    assert "- 3x [OTHER] cannot unify the information" in content
    assert "- 1x [INTERNAL] Internal error in GeneratePMCFG" in content

    assert "OUTPUTS:" in content
    assert str(run_result.run_paths.summary_json_path) in content
    assert str(run_result.run_paths.summary_md_path) in content
    assert str(run_result.run_paths.ai_brief_path) in content

    assert "DETAIL FILES:" in content
    assert str(tmp_path / "details" / "GrammarSqi.scan.txt") in content
    assert str(tmp_path / "details" / "GrammarSqi.out.txt") in content
    assert str(tmp_path / "details" / "GrammarSqi.err.txt") in content
    assert str(tmp_path / "details" / "LangSqi.scan.txt") in content
    assert str(tmp_path / "details" / "AllSqi.err.txt") in content


def test_write_ai_brief_handles_empty_sections(tmp_path: Path) -> None:
    ok_result = _make_file_result(
        file_path="lib/src/albanian/SymbolSqi.gf",
        status="OK",
        diagnostic_class="ok",
        scan_counts=_make_scan_counts(),
        compile_summary=_make_compile_summary(error_kind="OK"),
    )

    run_result = _make_run_result(tmp_path, [ok_result])
    run_result.gf_version = ""
    run_result.diff_entries = []
    run_result.top_errors = []

    written_path = write_ai_brief(run_result)
    content = written_path.read_text(encoding="utf-8")

    assert "GF_VERSION:" not in content

    assert "DIRECT FAILURES:" in content
    assert "DOWNSTREAM FAILURES:" in content
    assert "AMBIGUOUS FAILURES:" in content
    assert "HEURISTIC SCAN NOTES:" in content

    assert "DIRECT FAILURES:\nNone." in content
    assert "DOWNSTREAM FAILURES:\nNone." in content
    assert "AMBIGUOUS FAILURES:\nNone." in content
    assert "HEURISTIC SCAN NOTES:\nNone." in content

    assert "CHANGES SINCE PREVIOUS RUN:" not in content
    assert "TOP ERRORS:" not in content
    assert "DETAIL FILES:" not in content


def test_write_ai_brief_sorts_failures_by_file_path(tmp_path: Path) -> None:
    result_b = _make_file_result(
        file_path="lib/src/albanian/ZetaSqi.gf",
        status="FAIL",
        diagnostic_class="direct",
        compile_summary=_make_compile_summary(error_kind="OTHER", first_error="zeta error"),
        scan_log_path=tmp_path / "details" / "ZetaSqi.scan.txt",
    )
    result_a = _make_file_result(
        file_path="lib/src/albanian/AlphaSqi.gf",
        status="FAIL",
        diagnostic_class="direct",
        compile_summary=_make_compile_summary(error_kind="OTHER", first_error="alpha error"),
        scan_log_path=tmp_path / "details" / "AlphaSqi.scan.txt",
    )

    run_result = _make_run_result(tmp_path, [result_b, result_a])

    content = write_ai_brief(run_result).read_text(encoding="utf-8")

    alpha_index = content.index("1. lib/src/albanian/AlphaSqi.gf")
    zeta_index = content.index("2. lib/src/albanian/ZetaSqi.gf")
    assert alpha_index < zeta_index

