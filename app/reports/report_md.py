from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Iterable

from ..models import DiffEntry, FileResult, RunResult
from ..utils.io_utils import write_text


def write_summary_md(run_result: RunResult) -> Path:
    summary_md_path = Path(run_result.run_paths.summary_md_path)
    content = build_summary_md(run_result)
    write_text(summary_md_path, content)
    return summary_md_path


def build_summary_md(run_result: RunResult) -> str:
    file_results = list(run_result.file_results or [])
    diff_entries = list(run_result.diff_entries or [])
    top_errors = dict(run_result.top_errors or {})

    direct_failures = _filter_by_diagnostic_class(file_results, "direct")
    downstream_failures = _filter_by_diagnostic_class(file_results, "downstream")
    ambiguous_failures = _filter_by_diagnostic_class(file_results, "ambiguous")
    ok_results = [result for result in file_results if _safe_str(result.status) == "OK"]
    noise_results = _filter_by_diagnostic_class(file_results, "noise")
    skipped_results = [result for result in file_results if _safe_str(result.status) == "SKIPPED"]

    sections: list[str] = []

    sections.append("# GF Audit Summary")
    sections.append("")
    sections.append("## Run")
    sections.append("")
    sections.extend(_build_run_metadata(run_result))
    sections.append("")

    sections.append("## Totals")
    sections.append("")
    sections.extend(_build_totals(run_result))
    sections.append("")

    sections.append("## Direct failures")
    sections.append("")
    sections.extend(_build_failure_list(direct_failures, show_blocked_by=False))
    sections.append("")

    sections.append("## Downstream failures")
    sections.append("")
    sections.extend(_build_failure_list(downstream_failures, show_blocked_by=True))
    sections.append("")

    sections.append("## Ambiguous failures")
    sections.append("")
    sections.extend(_build_failure_list(ambiguous_failures, show_blocked_by=True))
    sections.append("")

    sections.append("## Successful files")
    sections.append("")
    sections.extend(_build_ok_list(ok_results))
    sections.append("")

    if skipped_results:
        sections.append("## Skipped files")
        sections.append("")
        sections.extend(_build_skipped_list(skipped_results))
        sections.append("")

    if noise_results:
        sections.append("## Excluded or noise files")
        sections.append("")
        sections.extend(_build_noise_list(noise_results))
        sections.append("")

    sections.append("## Top errors")
    sections.append("")
    sections.extend(_build_top_errors(top_errors))
    sections.append("")

    sections.append("## Heuristic scan notes")
    sections.append("")
    sections.extend(_build_scan_notes(file_results))
    sections.append("")

    if diff_entries:
        sections.append("## Changes since previous run")
        sections.append("")
        sections.extend(_build_diff_entries(diff_entries))
        sections.append("")

    sections.append("## Detail files")
    sections.append("")
    sections.extend(_build_detail_files(file_results))
    sections.append("")

    return "\n".join(sections).rstrip() + "\n"


def _build_run_metadata(run_result: RunResult) -> list[str]:
    run_config = run_result.run_config
    run_paths = run_result.run_paths

    # Current field name is ai_ready_path.
    # Fall back to legacy ai_brief_path for older serialized runs.
    ai_ready_path = getattr(run_paths, "ai_ready_path", None)
    if ai_ready_path is None:
        ai_ready_path = getattr(run_paths, "ai_brief_path", None)

    lines = [
        f"- run_id: `{_safe_str(run_paths.run_id)}`",
        f"- started_at: `{_safe_str(run_result.started_at)}`",
        f"- finished_at: `{_safe_str(run_result.finished_at)}`",
        f"- duration_ms: `{_safe_int(run_result.duration_ms)}`",
        f"- mode: `{_safe_str(run_config.mode)}`",
        f"- target_file: `{_safe_str(run_config.target_file) or '-'} `".rstrip(),
        f"- project_root: `{_safe_str(run_config.project_root)}`",
        f"- rgl_root: `{_safe_str(run_config.rgl_root)}`",
        f"- gf_exe: `{_safe_str(run_config.gf_exe)}`",
        f"- gf_version: `{_safe_str(run_result.gf_version) or 'unknown'}`",
        f"- summary_json_path: `{_safe_str(run_paths.summary_json_path)}`",
        f"- ai_ready_path: `{_safe_str(ai_ready_path)}`",
    ]
    return lines


def _build_totals(run_result: RunResult) -> list[str]:
    return [
        f"- files_seen: `{_safe_int(run_result.files_seen)}`",
        f"- files_included: `{_safe_int(run_result.files_included)}`",
        f"- files_excluded: `{_safe_int(run_result.files_excluded)}`",
        f"- ok_count: `{_safe_int(run_result.ok_count)}`",
        f"- fail_count: `{_safe_int(run_result.fail_count)}`",
        f"- direct_fail_count: `{_safe_int(run_result.direct_fail_count)}`",
        f"- downstream_fail_count: `{_safe_int(run_result.downstream_fail_count)}`",
        f"- ambiguous_fail_count: `{_safe_int(run_result.ambiguous_fail_count)}`",
        f"- excluded_noise_count: `{_safe_int(run_result.excluded_noise_count)}`",
    ]


def _build_failure_list(
    file_results: Iterable[FileResult],
    *,
    show_blocked_by: bool,
) -> list[str]:
    results = list(file_results)
    if not results:
        return ["- none"]

    lines: list[str] = []
    for result in _sort_file_results(results):
        compile_summary = result.compile_summary
        blocked_by = list(result.blocked_by or [])

        lines.append(f"- `{result.file_path}`")
        lines.append(f"  - module_name: `{_safe_str(result.module_name)}`")
        lines.append(f"  - status: `{_safe_str(result.status)}`")
        lines.append(f"  - diagnostic_class: `{_safe_str(result.diagnostic_class)}`")
        lines.append(f"  - error_kind: `{_safe_str(compile_summary.error_kind)}`")
        lines.append(f"  - first_error: `{_safe_str(compile_summary.first_error) or '-'} `".rstrip())
        lines.append(f"  - duration_ms: `{_safe_int(compile_summary.duration_ms)}`")
        lines.append(f"  - timed_out: `{_safe_bool(compile_summary.timed_out)}`")
        if show_blocked_by:
            if blocked_by:
                lines.append(f"  - blocked_by: {', '.join(f'`{item}`' for item in blocked_by)}")
            else:
                lines.append("  - blocked_by: -")
        lines.extend(_build_artifact_lines(result, indent="  "))
    return lines


def _build_ok_list(file_results: Iterable[FileResult]) -> list[str]:
    results = list(file_results)
    if not results:
        return ["- none"]

    lines: list[str] = []
    for result in _sort_file_results(results):
        scan_counts = result.scan_counts
        scan_hit_total = _scan_hit_total(scan_counts)
        lines.append(
            f"- `{result.file_path}` "
            f"(duration_ms={_safe_int(result.compile_summary.duration_ms)}, "
            f"scan_hits={scan_hit_total})"
        )
    return lines


def _build_skipped_list(file_results: Iterable[FileResult]) -> list[str]:
    results = list(file_results)
    if not results:
        return ["- none"]

    lines: list[str] = []
    for result in _sort_file_results(results):
        lines.append(f"- `{result.file_path}`")
    return lines


def _build_noise_list(file_results: Iterable[FileResult]) -> list[str]:
    results = list(file_results)
    if not results:
        return ["- none"]

    lines: list[str] = []
    for result in _sort_file_results(results):
        lines.append(f"- `{result.file_path}`")
    return lines


def _build_top_errors(top_errors: dict[str, int]) -> list[str]:
    if not top_errors:
        return ["- none"]

    ranked = sorted(top_errors.items(), key=lambda item: (-item[1], item[0]))
    return [f"- {count:>4}  `{message}`" for message, count in ranked[:20]]


def _build_scan_notes(file_results: Iterable[FileResult]) -> list[str]:
    results = [
        result
        for result in file_results
        if _scan_hit_total(result.scan_counts) > 0
    ]
    if not results:
        return ["- none"]

    grouped: dict[str, list[str]] = defaultdict(list)
    for result in _sort_file_results(results):
        counts = result.scan_counts
        hit_parts = []
        if _safe_int(counts.single_slash_eq) > 0:
            hit_parts.append(f"single_slash_eq={_safe_int(counts.single_slash_eq)}")
        if _safe_int(counts.double_slash_dash) > 0:
            hit_parts.append(f"double_slash_dash={_safe_int(counts.double_slash_dash)}")
        if _safe_int(counts.runtime_str_match) > 0:
            hit_parts.append(f"runtime_str_match={_safe_int(counts.runtime_str_match)}")
        if _safe_int(counts.untyped_case_str_pat) > 0:
            hit_parts.append(f"untyped_case_str_pat={_safe_int(counts.untyped_case_str_pat)}")
        if _safe_int(counts.untyped_table_str_pat) > 0:
            hit_parts.append(f"untyped_table_str_pat={_safe_int(counts.untyped_table_str_pat)}")
        if _safe_int(counts.trailing_spaces) > 0:
            hit_parts.append(f"trailing_spaces={_safe_int(counts.trailing_spaces)}")

        grouped[_safe_str(result.status)].append(
            f"- `{result.file_path}` ({', '.join(hit_parts)})"
        )

    lines: list[str] = []
    for status in ("FAIL", "OK", "SKIPPED"):
        entries = grouped.get(status)
        if not entries:
            continue
        lines.append(f"### {status}")
        lines.append("")
        lines.extend(entries)
        lines.append("")

    return lines or ["- none"]


def _build_diff_entries(diff_entries: Iterable[DiffEntry]) -> list[str]:
    entries = list(diff_entries)
    if not entries:
        return ["- none"]

    ranked = sorted(
        entries,
        key=lambda entry: (
            _diff_rank(_safe_str(entry.change_kind)),
            _safe_str(entry.file_path),
        ),
    )

    lines: list[str] = []
    for entry in ranked:
        previous_status = _safe_str(entry.previous_status) or "-"
        current_status = _safe_str(entry.current_status) or "-"
        message = _safe_str(entry.message)
        lines.append(
            f"- `{entry.file_path}`: `{previous_status}` -> `{current_status}` "
            f"({_safe_str(entry.change_kind)})"
        )
        if message:
            lines.append(f"  - {message}")
    return lines


def _build_detail_files(file_results: Iterable[FileResult]) -> list[str]:
    lines: list[str] = []
    for result in _sort_file_results(file_results):
        if _safe_str(result.status) != "FAIL":
            continue

        lines.append(f"- `{result.file_path}`")
        lines.extend(_build_artifact_lines(result, indent="  "))

    return lines or ["- none"]


def _build_artifact_lines(result: FileResult, *, indent: str) -> list[str]:
    lines: list[str] = []
    scan_log_path = _safe_str(result.scan_log_path)
    stdout_path = _safe_str(result.compile_summary.stdout_path)
    stderr_path = _safe_str(result.compile_summary.stderr_path)

    if scan_log_path:
        lines.append(f"{indent}- scan_log_path: `{scan_log_path}`")
    if stdout_path:
        lines.append(f"{indent}- stdout_path: `{stdout_path}`")
    if stderr_path:
        lines.append(f"{indent}- stderr_path: `{stderr_path}`")

    return lines


def _filter_by_diagnostic_class(
    file_results: Iterable[FileResult],
    diagnostic_class: str,
) -> list[FileResult]:
    return [
        result
        for result in file_results
        if _safe_str(result.diagnostic_class) == diagnostic_class
    ]


def _scan_hit_total(scan_counts: object) -> int:
    return (
        _safe_int(getattr(scan_counts, "single_slash_eq", 0))
        + _safe_int(getattr(scan_counts, "double_slash_dash", 0))
        + _safe_int(getattr(scan_counts, "runtime_str_match", 0))
        + _safe_int(getattr(scan_counts, "untyped_case_str_pat", 0))
        + _safe_int(getattr(scan_counts, "untyped_table_str_pat", 0))
        + _safe_int(getattr(scan_counts, "trailing_spaces", 0))
    )


def _sort_file_results(file_results: Iterable[FileResult]) -> list[FileResult]:
    return sorted(file_results, key=lambda result: _safe_str(result.file_path))


def _diff_rank(change_kind: str) -> int:
    order = {
        "regressed": 0,
        "new": 1,
        "improved": 2,
        "removed": 3,
        "unchanged": 4,
    }
    return order.get(change_kind, 99)


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _safe_int(value: object) -> int:
    try:
        return int(value) if value is not None else 0
    except (TypeError, ValueError):
        return 0


def _safe_bool(value: object) -> str:
    return "true" if bool(value) else "false"


__all__ = [
    "build_summary_md",
    "write_summary_md",
]