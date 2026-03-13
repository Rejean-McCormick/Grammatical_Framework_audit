from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..models import FileResult, RunResult
from ..utils.io_utils import ensure_dir, write_text


def write_ai_ready(run_result: RunResult) -> Path:
    """
    Write a self-contained AI-ready packet for a completed audit run.

    Output path:
        run_result.run_paths.ai_ready_path

    Returns:
        Path to the written AI_READY.md file.
    """
    ai_ready_path = Path(run_result.run_paths.ai_ready_path)
    ensure_dir(ai_ready_path.parent)

    content = _build_ai_ready_text(run_result).rstrip() + "\n"
    write_text(ai_ready_path, content)
    return ai_ready_path


def _build_ai_ready_text(run_result: RunResult) -> str:
    direct_failures = _select_results(run_result.file_results, diagnostic_class="direct")
    downstream_failures = _select_results(run_result.file_results, diagnostic_class="downstream")
    ambiguous_failures = _select_results(run_result.file_results, diagnostic_class="ambiguous")
    skipped_results = _select_results(run_result.file_results, diagnostic_class="skipped")
    ok_with_scan_hits = _select_ok_results_with_scan_hits(run_result.file_results)

    failing_results = [*direct_failures, *downstream_failures, *ambiguous_failures]
    primary_failure = failing_results[0] if failing_results else None
    top_errors = _normalize_top_errors(getattr(run_result, "top_errors", None))
    primary_top_error_text = top_errors[0][0] if top_errors else "None"

    lines: list[str] = []

    lines.append("# AI Ready Packet")
    lines.append("")

    lines.append("## Run Summary")
    lines.append(f"- Run ID: `{run_result.run_paths.run_id}`")
    lines.append(f"- Mode: `{run_result.run_config.mode}`")
    if getattr(run_result, "gf_version", ""):
        lines.append(f"- GF version: `{run_result.gf_version}`")
    if getattr(run_result.run_config, "target_file", ""):
        lines.append(f"- Target file: `{run_result.run_config.target_file}`")
    lines.append(f"- Project root: `{run_result.run_config.project_root}`")
    lines.append(f"- no_compile: `{getattr(run_result.run_config, 'no_compile', False)}`")
    lines.append(f"- Duration: `{getattr(run_result, 'duration_ms', 0)} ms`")
    lines.append("")

    lines.append("## Outcome")
    lines.append(f"- files_seen: `{run_result.files_seen}`")
    lines.append(f"- files_included: `{run_result.files_included}`")
    lines.append(f"- files_excluded: `{run_result.files_excluded}`")
    lines.append(f"- ok_count: `{run_result.ok_count}`")
    lines.append(f"- fail_count: `{run_result.fail_count}`")
    lines.append(f"- direct_fail_count: `{run_result.direct_fail_count}`")
    lines.append(f"- downstream_fail_count: `{run_result.downstream_fail_count}`")
    lines.append(f"- ambiguous_fail_count: `{run_result.ambiguous_fail_count}`")
    lines.append(f"- excluded_noise_count: `{run_result.excluded_noise_count}`")
    lines.append(f"- top_error: `{primary_top_error_text}`")
    lines.append("")

    if primary_failure is not None:
        lines.append("## Diagnosis Snapshot")
        lines.append(_build_diagnosis_summary(primary_failure, primary_top_error_text))
        lines.append("")

    if failing_results:
        lines.append("## Failing File" if len(failing_results) == 1 else "## Failing Files")

        for index, file_result in enumerate(failing_results, start=1):
            heading = (
                f"### `{file_result.file_path}`"
                if len(failing_results) == 1
                else f"### {index}. `{file_result.file_path}`"
            )
            lines.append(heading)
            lines.extend(_format_failure_summary(file_result))
            lines.append("")

            stdout_excerpt = _read_compile_stdout_excerpt(file_result)
            if stdout_excerpt:
                lines.append("#### Compile Progression Excerpt")
                lines.append("```text")
                lines.extend(stdout_excerpt)
                lines.append("```")
                lines.append("")

            stderr_excerpt = _read_compile_stderr_excerpt(file_result)
            if stderr_excerpt:
                lines.append("#### Relevant stderr Excerpt")
                lines.append("```text")
                lines.extend(stderr_excerpt)
                lines.append("```")
                lines.append("")

            fatal_block = _read_compile_fatal_block(file_result)
            if fatal_block:
                lines.append("#### Fatal Block")
                lines.append("```text")
                lines.extend(fatal_block)
                lines.append("```")
                lines.append("")

    if ok_with_scan_hits:
        lines.append("## Heuristic Scan Notes")
        for file_result in ok_with_scan_hits:
            lines.extend(_format_scan_note(file_result))
        lines.append("")

    if skipped_results:
        lines.append("## Skipped Files")
        for file_result in skipped_results:
            lines.append(f"- `{file_result.file_path}`")
        lines.append("")

    if getattr(run_result, "diff_entries", None):
        changed_entries = [
            entry
            for entry in run_result.diff_entries
            if getattr(entry, "change_kind", "") != "unchanged"
        ]
        lines.append("## Changes Since Previous Run")
        if changed_entries:
            for entry in changed_entries:
                lines.append(f"- `{entry.file_path}`: {entry.message}")
        else:
            lines.append("- None.")
        lines.append("")

    lines.append("## Artifact Paths")
    lines.append(f"- summary_json: `{run_result.run_paths.summary_json_path}`")
    lines.append(f"- summary_md: `{run_result.run_paths.summary_md_path}`")
    lines.append(f"- ai_ready: `{run_result.run_paths.ai_ready_path}`")
    lines.append(f"- master_log: `{run_result.run_paths.master_log_path}`")
    lines.append(f"- all_scan_logs: `{run_result.run_paths.all_scan_logs_path}`")
    lines.append(f"- all_logs: `{run_result.run_paths.all_logs_path}`")

    detail_paths = _collect_detail_paths(run_result.file_results)
    for detail_path in detail_paths:
        lines.append(f"- detail: `{detail_path}`")
    lines.append("")

    lines.append("## Ready Prompt For AI")
    lines.append("Use the run summary and the inlined excerpts below to diagnose the root cause.")
    lines.append("")
    lines.append("Questions to answer:")
    lines.append("1. What is the most likely root cause of the failing compile?")
    lines.append("2. Is the failure in the target file itself, or more likely caused by an imported dependency?")
    lines.append("3. Which file, function, category, or linearization rule should be inspected first?")
    lines.append("4. Which warnings appear most relevant to the fatal error?")
    lines.append("5. Suggest the smallest concrete debugging steps or code edits to try next.")
    lines.append("")

    if not failing_results and not ok_with_scan_hits:
        lines.append("## Notes")
        lines.append("No failing files and no scan-hit notes were found in this run.")
        lines.append("")

    return "\n".join(lines)


def _build_diagnosis_summary(file_result: FileResult, primary_top_error_text: str) -> str:
    compile_summary = getattr(file_result, "compile_summary", None)
    error_kind = getattr(compile_summary, "error_kind", "UNKNOWN")
    error_detail = getattr(compile_summary, "error_detail", "") or ""
    scan_summary = _format_scan_counts(getattr(file_result, "scan_counts", None))
    module_name = getattr(file_result, "module_name", "") or "<unknown module>"

    base = (
        f"Likely {str(error_kind).lower()} failure while compiling `{module_name}`; "
        f"top error is `{primary_top_error_text}` and scan summary is `{scan_summary}`."
    )
    if error_detail:
        return f"{base} Reported detail: `{error_detail}`."
    return base


def _format_failure_summary(file_result: FileResult) -> list[str]:
    compile_summary = getattr(file_result, "compile_summary", None)
    blocked_by = _normalize_blocked_by(getattr(file_result, "blocked_by", []))

    error_kind = getattr(compile_summary, "error_kind", "UNKNOWN")
    first_error = getattr(compile_summary, "first_error", "") or "<no first_error>"
    error_detail = getattr(compile_summary, "error_detail", "") or ""
    exit_code = getattr(compile_summary, "exit_code", "")
    duration_ms = getattr(compile_summary, "duration_ms", "")
    timed_out = getattr(compile_summary, "timed_out", False)

    lines: list[str] = []
    lines.append(f"- module_name: `{getattr(file_result, 'module_name', '')}`")
    lines.append(f"- status: `{getattr(file_result, 'status', '')}`")
    lines.append(f"- diagnostic_class: `{getattr(file_result, 'diagnostic_class', '')}`")
    lines.append(f"- is_direct: `{getattr(file_result, 'is_direct', False)}`")
    lines.append(f"- error_kind: `{error_kind}`")
    lines.append(f"- first_error: `{first_error}`")
    if error_detail:
        lines.append(f"- error_detail: `{error_detail}`")
    lines.append(f"- exit_code: `{exit_code}`")
    lines.append(f"- timed_out: `{timed_out}`")
    lines.append(f"- compile_duration_ms: `{duration_ms}`")
    if blocked_by:
        lines.append(f"- blocked_by: `{', '.join(blocked_by)}`")
    lines.append(f"- scan_summary: `{_format_scan_counts(getattr(file_result, 'scan_counts', None))}`")

    scan_log_path = _as_path(getattr(file_result, "scan_log_path", None))
    stdout_path = _as_path(getattr(compile_summary, "stdout_path", None))
    stderr_path = _as_path(getattr(compile_summary, "stderr_path", None))

    if scan_log_path is not None:
        lines.append(f"- scan_log_path: `{scan_log_path}`")
    if stdout_path is not None:
        lines.append(f"- stdout_path: `{stdout_path}`")
    if stderr_path is not None:
        lines.append(f"- stderr_path: `{stderr_path}`")

    return lines


def _select_results(file_results: Iterable[FileResult], diagnostic_class: str) -> list[FileResult]:
    selected = [
        result
        for result in file_results
        if getattr(result, "diagnostic_class", "") == diagnostic_class
    ]
    return sorted(selected, key=lambda item: str(getattr(item, "file_path", "")).lower())


def _select_ok_results_with_scan_hits(file_results: Iterable[FileResult]) -> list[FileResult]:
    selected = [
        result
        for result in file_results
        if getattr(result, "status", "") == "OK" and _scan_hit_total(getattr(result, "scan_counts", None)) > 0
    ]
    return sorted(selected, key=lambda item: str(getattr(item, "file_path", "")).lower())


def _format_scan_note(file_result: FileResult) -> list[str]:
    return [
        f"- `{file_result.file_path}`: compile OK, scan hits -> "
        f"{_format_scan_counts(getattr(file_result, 'scan_counts', None))}"
    ]


def _format_scan_counts(scan_counts: object | None) -> str:
    if scan_counts is None:
        return "none"

    parts: list[str] = []

    if getattr(scan_counts, "single_slash_eq", 0) > 0:
        parts.append(f"single_slash_eq={scan_counts.single_slash_eq}")
    if getattr(scan_counts, "double_slash_dash", 0) > 0:
        parts.append(f"double_slash_dash={scan_counts.double_slash_dash}")
    if getattr(scan_counts, "runtime_str_match", 0) > 0:
        parts.append(f"runtime_str_match={scan_counts.runtime_str_match}")
    if getattr(scan_counts, "untyped_case_str_pat", 0) > 0:
        parts.append(f"untyped_case_str_pat={scan_counts.untyped_case_str_pat}")
    if getattr(scan_counts, "untyped_table_str_pat", 0) > 0:
        parts.append(f"untyped_table_str_pat={scan_counts.untyped_table_str_pat}")
    if getattr(scan_counts, "trailing_spaces", 0) > 0:
        parts.append(f"trailing_spaces={scan_counts.trailing_spaces}")

    if not parts:
        return "no scan hits"

    return ", ".join(parts)


def _scan_hit_total(scan_counts: object | None) -> int:
    if scan_counts is None:
        return 0

    return sum(
        int(getattr(scan_counts, field_name, 0) or 0)
        for field_name in (
            "single_slash_eq",
            "double_slash_dash",
            "runtime_str_match",
            "untyped_case_str_pat",
            "untyped_table_str_pat",
            "trailing_spaces",
        )
    )


def _normalize_blocked_by(blocked_by: object) -> list[str]:
    if blocked_by is None:
        return []

    if isinstance(blocked_by, str):
        value = blocked_by.strip()
        return [value] if value else []

    normalized: list[str] = []
    for item in blocked_by:
        value = str(item).strip()
        if value:
            normalized.append(value)
    return normalized


def _normalize_top_errors(top_errors: object) -> list[tuple[str, int]]:
    if not top_errors:
        return []

    normalized: list[tuple[str, int]] = []

    if isinstance(top_errors, dict):
        for message, count in top_errors.items():
            normalized.append((str(message), int(count)))
        return sorted(normalized, key=lambda item: (-item[1], item[0].lower()))

    for item in top_errors:
        if isinstance(item, tuple) and len(item) == 2:
            normalized.append((str(item[0]), int(item[1])))
            continue

        message = str(getattr(item, "message", "")).strip()
        count = int(getattr(item, "count", 0) or 0)
        if message:
            normalized.append((message, count))

    return sorted(normalized, key=lambda item: (-item[1], item[0].lower()))


def _collect_detail_paths(file_results: Iterable[FileResult]) -> list[str]:
    detail_paths: list[str] = []

    for file_result in sorted(file_results, key=lambda item: str(getattr(item, "file_path", "")).lower()):
        if getattr(file_result, "status", "") != "FAIL":
            continue

        scan_log_path = _as_path(getattr(file_result, "scan_log_path", None))
        if scan_log_path is not None:
            detail_paths.append(str(scan_log_path))

        compile_summary = getattr(file_result, "compile_summary", None)
        stdout_path = _as_path(getattr(compile_summary, "stdout_path", None))
        stderr_path = _as_path(getattr(compile_summary, "stderr_path", None))

        if stdout_path is not None:
            detail_paths.append(str(stdout_path))
        if stderr_path is not None:
            detail_paths.append(str(stderr_path))

    return detail_paths


def _read_compile_stdout_excerpt(file_result: FileResult, max_lines: int = 20) -> list[str]:
    compile_summary = getattr(file_result, "compile_summary", None)
    stdout_path = _as_path(getattr(compile_summary, "stdout_path", None))
    lines = _read_lines(stdout_path)
    if not lines:
        return []

    visible = [line for line in lines if line.strip()]
    if len(visible) <= max_lines:
        return visible

    head_count = max_lines // 2
    tail_count = max_lines - head_count
    return [*visible[:head_count], "...", *visible[-tail_count:]]


def _read_compile_stderr_excerpt(file_result: FileResult, max_lines: int = 16) -> list[str]:
    compile_summary = getattr(file_result, "compile_summary", None)
    stderr_path = _as_path(getattr(compile_summary, "stderr_path", None))
    lines = _read_lines(stderr_path)
    if not lines:
        return []

    visible = [line for line in lines if line.strip()]
    if not visible:
        return []

    warning_block = _extract_relevant_warning_block(visible, max_lines=max_lines)
    if warning_block:
        return warning_block

    fatal_block = _extract_fatal_block(visible)
    if fatal_block:
        return []

    if len(visible) <= max_lines:
        return visible

    head_count = max_lines // 2
    tail_count = max_lines - head_count
    return [*visible[:head_count], "...", *visible[-tail_count:]]


def _read_compile_fatal_block(file_result: FileResult) -> list[str]:
    compile_summary = getattr(file_result, "compile_summary", None)
    stderr_path = _as_path(getattr(compile_summary, "stderr_path", None))
    lines = _read_lines(stderr_path)
    if not lines:
        return []

    visible = [line for line in lines if line.strip()]
    return _extract_fatal_block(visible)


def _extract_relevant_warning_block(lines: list[str], max_lines: int = 12) -> list[str]:
    if not lines:
        return []

    interesting_markers = (
        "Warning:",
        "warning:",
        "missing a linearization type",
        "not qualified but could refer to",
        "must_VV",
    )

    chosen_indexes: list[int] = []
    for index, line in enumerate(lines):
        if any(marker in line for marker in interesting_markers):
            start = max(0, index - 1)
            end = min(len(lines), index + 3)
            for pos in range(start, end):
                if pos not in chosen_indexes:
                    chosen_indexes.append(pos)
            if len(chosen_indexes) >= max_lines:
                break

    if not chosen_indexes:
        return []

    chosen_indexes = sorted(chosen_indexes[:max_lines])
    excerpt: list[str] = []
    previous_index: int | None = None

    for index in chosen_indexes:
        if previous_index is not None and index > previous_index + 1:
            excerpt.append("...")
        excerpt.append(lines[index])
        previous_index = index

    return excerpt


def _extract_fatal_block(lines: list[str]) -> list[str]:
    if not lines:
        return []

    fatal_markers = (
        "Internal error",
        "Cannot find an inflection rule",
        "CallStack",
        "error:",
        "Error:",
        "Exception:",
        "Traceback",
    )

    first_index: int | None = None
    for index, line in enumerate(lines):
        if any(marker in line for marker in fatal_markers):
            first_index = index
            break

    if first_index is None:
        return []

    start = max(0, first_index - 4)
    end = min(len(lines), first_index + 14)
    return lines[start:end]


def _read_lines(path: Path | None) -> list[str]:
    if path is None:
        return []
    if not path.exists():
        return []
    if not path.is_file():
        return []

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    return [line.rstrip() for line in text.splitlines()]


def _as_path(value: object) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value

    text = str(value).strip()
    if not text:
        return None

    return Path(text)


__all__ = ["write_ai_ready"]