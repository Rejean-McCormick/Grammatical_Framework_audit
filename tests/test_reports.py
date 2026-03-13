from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.reports.report_ai_ready import write_ai_ready


def _write_text(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


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
    stdout_path: str | Path | None = None,
    stderr_path: str | Path | None = None,
    error_detail: str = "",
    exit_code: int | None = None,
    duration_ms: int = 12,
) -> SimpleNamespace:
    resolved_exit_code = exit_code if exit_code is not None else (0 if error_kind == "OK" else 1)
    return SimpleNamespace(
        exit_code=resolved_exit_code,
        timed_out=False,
        duration_ms=duration_ms,
        error_kind=error_kind,
        first_error=first_error,
        error_detail=error_detail,
        stdout_path=Path(stdout_path) if stdout_path else None,
        stderr_path=Path(stderr_path) if stderr_path else None,
    )


def _make_file_result(
    file_path: str,
    status: str,
    diagnostic_class: str,
    blocked_by: list[str] | None = None,
    scan_counts: SimpleNamespace | None = None,
    compile_summary: SimpleNamespace | None = None,
    scan_log_path: str | Path | None = None,
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
        scan_log_path=Path(scan_log_path) if scan_log_path else None,
    )


def _make_run_result(
    tmp_path: Path,
    file_results: list[SimpleNamespace],
    *,
    mode: str = "all",
    target_file: str = "",
    no_compile: bool = False,
) -> SimpleNamespace:
    run_dir = tmp_path / "run_20260311_163720"
    ai_ready_path = run_dir / "AI_READY.md"
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
        run_config=SimpleNamespace(
            mode=mode,
            target_file=target_file,
            project_root=str(tmp_path / "project_root"),
            no_compile=no_compile,
        ),
        run_paths=SimpleNamespace(
            run_id="20260311_163720",
            run_dir=run_dir,
            ai_ready_path=ai_ready_path,
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


def test_write_ai_ready_writes_ai_ready_packet_with_inline_evidence(tmp_path: Path) -> None:
    grammar_scan = _write_text(
        tmp_path / "details" / "GrammarSqi.scan.txt",
        (
            "SCAN SUMMARY:\n"
            "SingleSlashThenEq hits: 0\n"
            "DoubleSlashThenDash hits: 0\n"
            "RuntimeStringMatch hits: 2\n"
            "UntypedCaseWithStrPatterns hits: 0\n"
            "UntypedTableWithStrPatterns hits: 0\n"
            "TrailingSpaces hits: 1\n"
        ),
    )
    grammar_out = _write_text(
        tmp_path / "details" / "GrammarSqi.out.txt",
        (
            "- compiling C:\\gf-rgl\\src\\abstract\\Common.gf...   write file Common.gfo\n"
            "- compiling lib\\src\\albanian\\CatSqi.gf...   write file CatSqi.gfo\n"
            "- compiling lib\\src\\albanian\\GrammarSqi.gf...\n"
        ),
    )
    grammar_err = _write_text(
        tmp_path / "details" / "GrammarSqi.err.txt",
        (
            "lib\\src\\albanian\\CatSqi.gf:\n"
            "   Warning: no linearization type for DAP, inserting default {s : Str}\n"
            "gf.exe: Internal error in GeneratePMCFG:\n"
            "    evalTerm (Predef.error \"Cannot find an inflection rule\")\n"
        ),
    )

    lang_scan = _write_text(
        tmp_path / "details" / "LangSqi.scan.txt",
        "SCAN SUMMARY:\nRuntimeStringMatch hits: 0\nTrailingSpaces hits: 0\n",
    )
    lang_out = _write_text(
        tmp_path / "details" / "LangSqi.out.txt",
        "- compiling lib\\src\\albanian\\LangSqi.gf...\n",
    )
    lang_err = _write_text(
        tmp_path / "details" / "LangSqi.err.txt",
        "blocked by failed dependency GrammarSqi.gf\n",
    )

    all_scan = _write_text(
        tmp_path / "details" / "AllSqi.scan.txt",
        "SCAN SUMMARY:\nRuntimeStringMatch hits: 0\nTrailingSpaces hits: 0\n",
    )
    all_out = _write_text(
        tmp_path / "details" / "AllSqi.out.txt",
        "- compiling lib\\src\\albanian\\AllSqi.gf...\n",
    )
    all_err = _write_text(
        tmp_path / "details" / "AllSqi.err.txt",
        "first error points to NounSqi.gf\n",
    )

    direct = _make_file_result(
        file_path="lib/src/albanian/GrammarSqi.gf",
        status="FAIL",
        diagnostic_class="direct",
        scan_counts=_make_scan_counts(runtime_str_match=2, trailing_spaces=1),
        compile_summary=_make_compile_summary(
            error_kind="OTHER",
            first_error="cannot unify the information oper sep : Str",
            stdout_path=grammar_out,
            stderr_path=grammar_err,
            error_detail="Unification",
            duration_ms=125,
        ),
        scan_log_path=grammar_scan,
    )

    downstream = _make_file_result(
        file_path="lib/src/albanian/LangSqi.gf",
        status="FAIL",
        diagnostic_class="downstream",
        blocked_by=["lib/src/albanian/GrammarSqi.gf"],
        compile_summary=_make_compile_summary(
            error_kind="OTHER",
            first_error="blocked by failed dependency GrammarSqi.gf",
            stdout_path=lang_out,
            stderr_path=lang_err,
        ),
        scan_log_path=lang_scan,
    )

    ambiguous = _make_file_result(
        file_path="lib/src/albanian/AllSqi.gf",
        status="FAIL",
        diagnostic_class="ambiguous",
        blocked_by=["lib/src/albanian/NounSqi.gf"],
        compile_summary=_make_compile_summary(
            error_kind="OTHER",
            first_error="first error points to NounSqi.gf",
            stdout_path=all_out,
            stderr_path=all_err,
        ),
        scan_log_path=all_scan,
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
        mode="all",
    )

    written_path = write_ai_ready(run_result)
    assert written_path == run_result.run_paths.ai_ready_path
    assert written_path.name == "AI_READY.md"
    assert written_path.exists()

    content = written_path.read_text(encoding="utf-8")

    assert "# AI Ready Packet" in content
    assert "## Run Summary" in content
    assert "## Outcome" in content
    assert "## Diagnosis Snapshot" in content
    assert "## Failing Files" in content
    assert "## Artifact Paths" in content
    assert "## Ready Prompt For AI" in content

    assert "20260311_163720" in content
    assert "3.12.0" in content
    assert "all" in content

    assert "GrammarSqi.gf" in content
    assert "LangSqi.gf" in content
    assert "AllSqi.gf" in content

    assert "cannot unify the information oper sep : Str" in content
    assert "blocked by failed dependency GrammarSqi.gf" in content
    assert "first error points to NounSqi.gf" in content

    assert "runtime_str_match=2" in content
    assert "trailing_spaces=1" in content
    assert "- `lib/src/albanian/MorphoSqi.gf`: compile OK, scan hits ->" in content
    assert "lib/src/albanian/NounSqi.gf" not in content

    assert "FAIL -> OK" in content
    assert "still FAIL" not in content

    assert "[OTHER] cannot unify the information" in content
    assert "[INTERNAL] Internal error in GeneratePMCFG" in content

    assert str(run_result.run_paths.summary_json_path) in content
    assert str(run_result.run_paths.summary_md_path) in content
    assert str(run_result.run_paths.ai_ready_path) in content
    assert str(run_result.run_paths.all_logs_path) in content

    assert "- compiling C:\\gf-rgl\\src\\abstract\\Common.gf..." in content
    assert "- compiling lib\\src\\albanian\\GrammarSqi.gf..." in content

    assert "Warning: no linearization type for DAP" in content
    assert "gf.exe: Internal error in GeneratePMCFG:" in content
    assert 'evalTerm (Predef.error "Cannot find an inflection rule")' in content

    assert str(grammar_scan) in content
    assert str(grammar_out) in content
    assert str(grammar_err) in content
    assert str(lang_scan) in content
    assert str(all_err) in content

    assert "What is the most likely root cause of the failing compile?" in content


def test_write_ai_ready_single_failure_is_not_duplicated(tmp_path: Path) -> None:
    single_out = _write_text(
        tmp_path / "details" / "StructuralSqi.out.txt",
        (
            "- compiling C:\\gf-rgl\\src\\abstract\\Common.gf...\n"
            "- compiling lib\\src\\albanian\\StructuralSqi.gf...\n"
        ),
    )
    single_err = _write_text(
        tmp_path / "details" / "StructuralSqi.err.txt",
        (
            "lib\\src\\albanian\\CatSqi.gf:\n"
            "   Warning: no linearization type for DAP, inserting default {s : Str}\n"
            "gf.exe: Internal error in GeneratePMCFG:\n"
            "    evalTerm (Predef.error \"Cannot find an inflection rule\")\n"
        ),
    )
    single_scan = _write_text(
        tmp_path / "details" / "StructuralSqi.scan.txt",
        "SCAN SUMMARY:\nRuntimeStringMatch hits: 0\nTrailingSpaces hits: 0\n",
    )

    single_fail = _make_file_result(
        file_path="lib/src/albanian/StructuralSqi.gf",
        status="FAIL",
        diagnostic_class="direct",
        compile_summary=_make_compile_summary(
            error_kind="INTERNAL",
            first_error="gf.exe: Internal error in GeneratePMCFG:",
            stdout_path=single_out,
            stderr_path=single_err,
            error_detail="GeneratePMCFG",
            duration_ms=819,
        ),
        scan_log_path=single_scan,
    )

    run_result = _make_run_result(
        tmp_path,
        [single_fail],
        mode="file",
        target_file="lib/src/albanian/StructuralSqi.gf",
    )
    run_result.top_errors = [("[INTERNAL] gf.exe: Internal error in GeneratePMCFG:", 1)]

    content = write_ai_ready(run_result).read_text(encoding="utf-8")

    assert written_name := run_result.run_paths.ai_ready_path.name
    assert written_name == "AI_READY.md"

    assert "## Diagnosis Snapshot" in content
    assert "## Failing File" in content
    assert "## Primary Failure" not in content

    assert "- Target file: `lib/src/albanian/StructuralSqi.gf`" in content
    assert "gf.exe: Internal error in GeneratePMCFG:" in content
    assert 'evalTerm (Predef.error "Cannot find an inflection rule")' in content

    assert content.count("### `lib/src/albanian/StructuralSqi.gf`") == 1


def test_write_ai_ready_handles_empty_sections(tmp_path: Path) -> None:
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

    written_path = write_ai_ready(run_result)
    content = written_path.read_text(encoding="utf-8")

    assert written_path.name == "AI_READY.md"
    assert "# AI Ready Packet" in content

    assert "GF version" not in content
    assert "## Diagnosis Snapshot" not in content
    assert "## Failing File" not in content
    assert "## Failing Files" not in content
    assert "## Heuristic Scan Notes" not in content

    assert "No failing files and no scan-hit notes were found in this run." in content

    assert "FAIL -> OK" not in content
    assert "[INTERNAL]" not in content


def test_write_ai_ready_sorts_failures_by_file_path(tmp_path: Path) -> None:
    alpha_scan = _write_text(
        tmp_path / "details" / "AlphaSqi.scan.txt",
        "SCAN SUMMARY:\nRuntimeStringMatch hits: 0\nTrailingSpaces hits: 0\n",
    )
    alpha_out = _write_text(
        tmp_path / "details" / "AlphaSqi.out.txt",
        "- compiling lib\\src\\albanian\\AlphaSqi.gf...\n",
    )
    alpha_err = _write_text(
        tmp_path / "details" / "AlphaSqi.err.txt",
        "alpha error\n",
    )
    zeta_scan = _write_text(
        tmp_path / "details" / "ZetaSqi.scan.txt",
        "SCAN SUMMARY:\nRuntimeStringMatch hits: 0\nTrailingSpaces hits: 0\n",
    )
    zeta_out = _write_text(
        tmp_path / "details" / "ZetaSqi.out.txt",
        "- compiling lib\\src\\albanian\\ZetaSqi.gf...\n",
    )
    zeta_err = _write_text(
        tmp_path / "details" / "ZetaSqi.err.txt",
        "zeta error\n",
    )

    result_b = _make_file_result(
        file_path="lib/src/albanian/ZetaSqi.gf",
        status="FAIL",
        diagnostic_class="direct",
        compile_summary=_make_compile_summary(
            error_kind="OTHER",
            first_error="zeta error",
            stdout_path=zeta_out,
            stderr_path=zeta_err,
        ),
        scan_log_path=zeta_scan,
    )
    result_a = _make_file_result(
        file_path="lib/src/albanian/AlphaSqi.gf",
        status="FAIL",
        diagnostic_class="direct",
        compile_summary=_make_compile_summary(
            error_kind="OTHER",
            first_error="alpha error",
            stdout_path=alpha_out,
            stderr_path=alpha_err,
        ),
        scan_log_path=alpha_scan,
    )

    run_result = _make_run_result(tmp_path, [result_b, result_a])

    content = write_ai_ready(run_result).read_text(encoding="utf-8")

    alpha_index = content.index("### 1. `lib/src/albanian/AlphaSqi.gf`")
    zeta_index = content.index("### 2. `lib/src/albanian/ZetaSqi.gf`")
    assert alpha_index < zeta_index