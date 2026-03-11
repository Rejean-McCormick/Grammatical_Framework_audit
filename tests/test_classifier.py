from __future__ import annotations

from pathlib import Path

import pytest

from app.audit.classifier import (
    classify_file_results,
    classify_single_result,
    resolve_blocked_by,
)
from app.models import CompileSummary, FileResult, ScanCounts, SourceFingerprint


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


def _make_compile_summary(
    *,
    exit_code: int = 0,
    timed_out: bool = False,
    duration_ms: int = 10,
    error_kind: str = "OK",
    first_error: str = "",
    error_detail: str = "",
    stdout_name: str = "stdout.txt",
    stderr_name: str = "stderr.txt",
) -> CompileSummary:
    return CompileSummary(
        exit_code=exit_code,
        timed_out=timed_out,
        duration_ms=duration_ms,
        error_kind=error_kind,
        first_error=first_error,
        error_detail=error_detail,
        stdout_path=Path(stdout_name),
        stderr_path=Path(stderr_name),
    )


def _make_file_result(
    *,
    file_path: str,
    module_name: str | None = None,
    status: str = "SKIPPED",
    diagnostic_class: str = "skipped",
    is_direct: bool = False,
    blocked_by: list[str] | None = None,
    error_kind: str = "OK",
    first_error: str = "",
    exit_code: int = 0,
    timed_out: bool = False,
) -> FileResult:
    module_name = module_name or Path(file_path).stem
    blocked_by = blocked_by or []

    return FileResult(
        file_path=file_path,
        module_name=module_name,
        status=status,
        diagnostic_class=diagnostic_class,
        is_direct=is_direct,
        blocked_by=blocked_by,
        scan_counts=_make_scan_counts(),
        fingerprint=_make_fingerprint(),
        compile_summary=_make_compile_summary(
            exit_code=exit_code,
            timed_out=timed_out,
            error_kind=error_kind,
            first_error=first_error,
            stdout_name=f"{module_name}.out.txt",
            stderr_name=f"{module_name}.err.txt",
        ),
        scan_log_path=Path(f"{module_name}.scan.txt"),
    )


def _classify(file_results: list[FileResult]) -> list[FileResult]:
    classified = classify_file_results(file_results)
    return file_results if classified is None else classified


def _classify_one(
    file_result: FileResult,
    file_results: list[FileResult],
) -> FileResult:
    classified = classify_single_result(file_result, file_results)
    return file_result if classified is None else classified


def test_ok_file_is_classified_as_ok() -> None:
    ok_result = _make_file_result(
        file_path="lib/src/albanian/NounSqi.gf",
        status="SKIPPED",
        diagnostic_class="skipped",
        error_kind="OK",
        exit_code=0,
    )

    classified = _classify([ok_result])[0]

    assert classified.status == "OK"
    assert classified.diagnostic_class == "ok"
    assert classified.is_direct is False
    assert classified.blocked_by == []


def test_self_referenced_failure_is_direct() -> None:
    grammar_result = _make_file_result(
        file_path="lib/src/albanian/GrammarSqi.gf",
        status="SKIPPED",
        diagnostic_class="skipped",
        error_kind="OTHER",
        exit_code=1,
        first_error="lib/src/albanian/GrammarSqi.gf: cannot unify the information ...",
    )

    classified = _classify([grammar_result])[0]

    assert classified.status == "FAIL"
    assert classified.diagnostic_class == "direct"
    assert classified.is_direct is True
    assert classified.blocked_by == []


@pytest.mark.parametrize("error_kind", ["INTERNAL", "TIMEOUT", "SCRIPT"])
def test_internal_timeout_or_script_failures_are_direct(error_kind: str) -> None:
    structural_result = _make_file_result(
        file_path="lib/src/albanian/StructuralSqi.gf",
        status="SKIPPED",
        diagnostic_class="skipped",
        error_kind=error_kind,
        exit_code=997 if error_kind == "TIMEOUT" else 1,
        timed_out=(error_kind == "TIMEOUT"),
        first_error="gf.exe: Internal error in GeneratePMCFG:",
    )

    classified = _classify([structural_result])[0]

    assert classified.status == "FAIL"
    assert classified.diagnostic_class == "direct"
    assert classified.is_direct is True
    assert classified.blocked_by == []


def test_failure_blocked_by_direct_failure_is_downstream() -> None:
    grammar_result = _make_file_result(
        file_path="lib/src/albanian/GrammarSqi.gf",
        error_kind="OTHER",
        exit_code=1,
        first_error="lib/src/albanian/GrammarSqi.gf: cannot unify the information ...",
    )
    lang_result = _make_file_result(
        file_path="lib/src/albanian/LangSqi.gf",
        error_kind="OTHER",
        exit_code=1,
        first_error="lib/src/albanian/GrammarSqi.gf: cannot unify the information ...",
    )

    classified = _classify([grammar_result, lang_result])
    grammar = next(item for item in classified if item.module_name == "GrammarSqi")
    lang = next(item for item in classified if item.module_name == "LangSqi")

    assert grammar.status == "FAIL"
    assert grammar.diagnostic_class == "direct"
    assert grammar.is_direct is True

    assert lang.status == "FAIL"
    assert lang.diagnostic_class == "downstream"
    assert lang.is_direct is False
    assert lang.blocked_by == ["lib/src/albanian/GrammarSqi.gf"]


def test_failure_pointing_to_ok_file_is_ambiguous() -> None:
    noun_result = _make_file_result(
        file_path="lib/src/albanian/NounSqi.gf",
        error_kind="OK",
        exit_code=0,
    )
    all_result = _make_file_result(
        file_path="lib/src/albanian/AllSqi.gf",
        error_kind="OTHER",
        exit_code=1,
        first_error="lib/src/albanian/NounSqi.gf: some propagated error text",
    )

    classified = _classify([noun_result, all_result])
    noun = next(item for item in classified if item.module_name == "NounSqi")
    all_sqi = next(item for item in classified if item.module_name == "AllSqi")

    assert noun.status == "OK"
    assert noun.diagnostic_class == "ok"

    assert all_sqi.status == "FAIL"
    assert all_sqi.diagnostic_class == "ambiguous"
    assert all_sqi.is_direct is False
    assert all_sqi.blocked_by == []


def test_resolve_blocked_by_returns_matching_failed_dependency_path() -> None:
    grammar_result = _make_file_result(
        file_path="lib/src/albanian/GrammarSqi.gf",
        error_kind="OTHER",
        exit_code=1,
        first_error="lib/src/albanian/GrammarSqi.gf: cannot unify the information ...",
        is_direct=True,
        status="FAIL",
        diagnostic_class="direct",
    )
    extend_result = _make_file_result(
        file_path="lib/src/albanian/ExtendSqi.gf",
        error_kind="OTHER",
        exit_code=1,
        first_error="lib/src/albanian/GrammarSqi.gf: inherited failure",
        status="FAIL",
        diagnostic_class="ambiguous",
    )

    blocked_by = resolve_blocked_by(extend_result, [grammar_result, extend_result])

    assert blocked_by == ["lib/src/albanian/GrammarSqi.gf"]


def test_classify_single_result_sets_ok_when_exit_code_is_zero() -> None:
    adverb_result = _make_file_result(
        file_path="lib/src/albanian/AdverbSqi.gf",
        error_kind="OK",
        exit_code=0,
        status="SKIPPED",
        diagnostic_class="skipped",
    )

    classified = _classify_one(adverb_result, [adverb_result])

    assert classified.status == "OK"
    assert classified.diagnostic_class == "ok"
    assert classified.is_direct is False
    assert classified.blocked_by == []


def test_classify_single_result_marks_direct_when_first_error_mentions_self() -> None:
    grammar_result = _make_file_result(
        file_path="lib/src/albanian/GrammarSqi.gf",
        error_kind="TYPE",
        exit_code=1,
        first_error="Happened in lib/src/albanian/GrammarSqi.gf",
        status="SKIPPED",
        diagnostic_class="skipped",
    )

    classified = _classify_one(grammar_result, [grammar_result])

    assert classified.status == "FAIL"
    assert classified.diagnostic_class == "direct"
    assert classified.is_direct is True
    assert classified.blocked_by == []


def test_downstream_classification_prefers_failed_dependency_over_module_name_noise() -> None:
    grammar_result = _make_file_result(
        file_path="lib/src/albanian/GrammarSqi.gf",
        error_kind="OTHER",
        exit_code=1,
        first_error="lib/src/albanian/GrammarSqi.gf: primary error",
    )
    structural_result = _make_file_result(
        file_path="lib/src/albanian/StructuralSqi.gf",
        error_kind="INTERNAL",
        exit_code=1,
        first_error="gf.exe: Internal error in GeneratePMCFG:",
    )
    lang_result = _make_file_result(
        file_path="lib/src/albanian/LangSqi.gf",
        error_kind="OTHER",
        exit_code=1,
        first_error="while compiling LangSqi, dependency failed: lib/src/albanian/GrammarSqi.gf",
    )

    classified = _classify([grammar_result, structural_result, lang_result])
    lang = next(item for item in classified if item.module_name == "LangSqi")

    assert lang.status == "FAIL"
    assert lang.diagnostic_class == "downstream"
    assert lang.is_direct is False
    assert lang.blocked_by == ["lib/src/albanian/GrammarSqi.gf"]

