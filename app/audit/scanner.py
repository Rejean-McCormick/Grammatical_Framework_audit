from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.models import RunConfig, RunPaths, ScanCounts

_RX_SINGLE_SLASH_THEN_EQ = re.compile(r"(?<!\\)\\(?!\\)(?:(?!->)[^;])*=>")
_RX_DOUBLE_SLASH_THEN_DASH = re.compile(r"\\\\(?:(?!=>)[^;])*->")
_RX_CASE_START = re.compile(r"\bcase\b.*\bof\s*\{")
_RX_TABLE_START = re.compile(r"\btable\s*\{")
_RX_TRAILING_SPACES = re.compile(r"[ \t]+$")


@dataclass(slots=True)
class _ScanDetails:
    bad_single: list[str]
    bad_double: list[str]
    bad_runtime: list[str]
    bad_untyped_case: list[str]
    bad_untyped_table: list[str]
    trailing_spaces: int


def scan_file(file_path: Path, run_config: RunConfig, run_paths: RunPaths) -> tuple[ScanCounts, Path]:
    file_path = Path(file_path)
    rel_path = _relative_to_project_root(file_path, run_config.project_root)
    scan_log_path = run_paths.scan_logs_dir / f"{_safe_name(rel_path)}.scan.txt"
    scan_log_path.parent.mkdir(parents=True, exist_ok=True)

    raw_text = _read_text(file_path)
    orig_lines = raw_text.splitlines()

    lines_no_comments, lines_no_strings = _strip_comments_and_mask_strings(orig_lines)

    bad_single = _find_single_slash_eq_hits(orig_lines, lines_no_strings)
    bad_double = _find_double_slash_dash_hits(orig_lines, lines_no_strings)
    bad_runtime = _find_runtime_string_match_blocks(lines_no_comments, lines_no_strings, orig_lines)
    bad_untyped_case = _find_untyped_blocks_with_str_patterns(
        start_rx=_RX_CASE_START,
        lines_no_comments=lines_no_comments,
        lines_no_strings=lines_no_strings,
        orig_lines=orig_lines,
    )
    bad_untyped_table = _find_untyped_blocks_with_str_patterns(
        start_rx=_RX_TABLE_START,
        lines_no_comments=lines_no_comments,
        lines_no_strings=lines_no_strings,
        orig_lines=orig_lines,
    )
    trailing_spaces = _count_trailing_spaces(orig_lines)

    scan_counts = ScanCounts(
        single_slash_eq=len(bad_single),
        double_slash_dash=len(bad_double),
        runtime_str_match=len(bad_runtime),
        untyped_case_str_pat=len(bad_untyped_case),
        untyped_table_str_pat=len(bad_untyped_table),
        trailing_spaces=trailing_spaces,
    )

    details = _ScanDetails(
        bad_single=bad_single,
        bad_double=bad_double,
        bad_runtime=bad_runtime,
        bad_untyped_case=bad_untyped_case,
        bad_untyped_table=bad_untyped_table,
        trailing_spaces=trailing_spaces,
    )

    scan_log_text = build_scan_log(
        file_path=file_path,
        rel_path=rel_path,
        scan_counts=scan_counts,
        details=details,
    )
    scan_log_path.write_text(scan_log_text, encoding="utf-8")

    return scan_counts, scan_log_path


def build_scan_log(
    file_path: Path,
    rel_path: str,
    scan_counts: ScanCounts,
    details: _ScanDetails,
) -> str:
    return "\n".join(
        [
            f"FILE: {file_path}",
            f"REL:  {rel_path}",
            "",
            "SCAN SUMMARY:",
            f"SingleSlashThenEq hits: {scan_counts.single_slash_eq}",
            f"DoubleSlashThenDash hits: {scan_counts.double_slash_dash}",
            f"RuntimeStringMatch hits: {scan_counts.runtime_str_match}",
            f"UntypedCaseWithStrPatterns hits: {scan_counts.untyped_case_str_pat}",
            f"UntypedTableWithStrPatterns hits: {scan_counts.untyped_table_str_pat}",
            f"TrailingSpaces hits: {scan_counts.trailing_spaces}",
            "",
            "DETAILS:",
            "",
            "SingleSlashThenEq (only if no '->' before '=>'):",
            _format_detail_lines(details.bad_single),
            "",
            "DoubleSlashThenDash (only if no '=>' before '->'):",
            _format_detail_lines(details.bad_double),
            "",
            'RuntimeStringMatch (case <expr>.s of { "..." => ... }):',
            _format_detail_lines(details.bad_runtime),
            "",
            "UntypedCaseWithStrPatterns (string-pattern rules but missing ': Str>'):",
            _format_detail_lines(details.bad_untyped_case),
            "",
            "UntypedTableWithStrPatterns (string-pattern rules but missing ': Str>'):",
            _format_detail_lines(details.bad_untyped_table),
            "",
        ]
    )


def _format_detail_lines(lines: list[str]) -> str:
    return "\n".join(lines) if lines else "None."


def _read_text(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return file_path.read_text(encoding="utf-8-sig", errors="replace")


def _safe_name(path_like: str) -> str:
    return re.sub(r'[\\/:*?"<>| ]', "_", path_like)


def _relative_to_project_root(file_path: Path, project_root: Path) -> str:
    try:
        return str(file_path.resolve().relative_to(project_root.resolve()))
    except ValueError:
        return str(file_path.name)


def _count_trailing_spaces(orig_lines: list[str]) -> int:
    return sum(1 for line in orig_lines if _RX_TRAILING_SPACES.search(line) is not None)


def _find_single_slash_eq_hits(orig_lines: list[str], lines_no_strings: list[str]) -> list[str]:
    hits: list[str] = []
    for index, line in enumerate(lines_no_strings):
        if _RX_SINGLE_SLASH_THEN_EQ.search(line):
            source_line = orig_lines[index].strip() if index < len(orig_lines) else ""
            hits.append(f"line {index + 1}: {source_line}")
    return hits


def _find_double_slash_dash_hits(orig_lines: list[str], lines_no_strings: list[str]) -> list[str]:
    hits: list[str] = []
    for index, line in enumerate(lines_no_strings):
        if _RX_DOUBLE_SLASH_THEN_DASH.search(line):
            source_line = orig_lines[index].strip() if index < len(orig_lines) else ""
            hits.append(f"line {index + 1}: {source_line}")
    return hits


def _process_gf_line(line: str, in_block_comment: bool) -> tuple[str, str, bool]:
    keep_chars: list[str] = []
    masked_chars: list[str] = []

    in_string = False
    index = 0

    while index < len(line):
        ch = line[index]
        next_ch = line[index + 1] if index + 1 < len(line) else "\0"

        if in_block_comment:
            if ch == "-" and next_ch == "}":
                in_block_comment = False
                keep_chars.extend([" ", " "])
                masked_chars.extend([" ", " "])
                index += 2
                continue

            keep_chars.append(" ")
            masked_chars.append(" ")
            index += 1
            continue

        if in_string:
            if ch == "\\" and next_ch != "\0":
                keep_chars.extend([ch, next_ch])
                masked_chars.extend([" ", " "])
                index += 2
                continue

            if ch == '"':
                in_string = False
                keep_chars.append('"')
                masked_chars.append('"')
                index += 1
                continue

            keep_chars.append(ch)
            masked_chars.append(" ")
            index += 1
            continue

        if ch == "{" and next_ch == "-":
            in_block_comment = True
            keep_chars.extend([" ", " "])
            masked_chars.extend([" ", " "])
            index += 2
            continue

        if ch == "-" and next_ch == "-":
            remaining = len(line) - index
            keep_chars.extend(" " * remaining)
            masked_chars.extend(" " * remaining)
            break

        if ch == '"':
            in_string = True
            keep_chars.append('"')
            masked_chars.append('"')
            index += 1
            continue

        keep_chars.append(ch)
        masked_chars.append(ch)
        index += 1

    return "".join(keep_chars), "".join(masked_chars), in_block_comment


def _strip_comments_and_mask_strings(orig_lines: list[str]) -> tuple[list[str], list[str]]:
    in_block_comment = False
    lines_no_comments: list[str] = []
    lines_no_strings: list[str] = []

    for line in orig_lines:
        no_comments, no_comments_no_strings, in_block_comment = _process_gf_line(
            line=line,
            in_block_comment=in_block_comment,
        )
        lines_no_comments.append(no_comments)
        lines_no_strings.append(no_comments_no_strings)

    return lines_no_comments, lines_no_strings


def _get_brace_balanced_end_line(start_line: int, lines_no_strings: list[str]) -> int:
    depth = 0
    started = False

    for line_index in range(start_line, len(lines_no_strings)):
        line = lines_no_strings[line_index]
        for ch in line:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1

        if started and depth <= 0:
            return line_index

    return start_line


def _find_runtime_string_match_blocks(
    lines_no_comments: list[str],
    lines_no_strings: list[str],
    orig_lines: list[str],
) -> list[str]:
    rx_case = re.compile(r"\bcase\b")
    rx_head_has_dot_s = re.compile(r"\.\s*s\b")
    rx_head_has_of_brace = re.compile(r"\bof\s*\{")
    rx_literal_branch = re.compile(r'"[^"]*"\s*=>')

    hits: list[str] = []
    index = 0

    while index < len(lines_no_comments):
        line = lines_no_comments[index]
        if not rx_case.search(line):
            index += 1
            continue

        head = line
        end_head = index
        while end_head + 1 < len(lines_no_comments) and not rx_head_has_of_brace.search(head) and len(head) < 800:
            end_head += 1
            head += " " + re.sub(r"\s+", " ", lines_no_comments[end_head])

        if not (rx_head_has_of_brace.search(head) and rx_head_has_dot_s.search(head)):
            index += 1
            continue

        block_end = _get_brace_balanced_end_line(index, lines_no_strings)
        block_text = "\n".join(lines_no_comments[index : block_end + 1])

        if rx_literal_branch.search(block_text):
            first_line = orig_lines[index].strip() if index < len(orig_lines) else ""
            hits.append(f"lines {index + 1}-{block_end + 1}: {first_line}")

        index = block_end + 1

    return hits


def _find_untyped_blocks_with_str_patterns(
    start_rx: re.Pattern[str],
    lines_no_comments: list[str],
    lines_no_strings: list[str],
    orig_lines: list[str],
) -> list[str]:
    rx_has_str_pat = re.compile(r'(_\s*\+\s*".+?"|".+?"\s*\+\s*_)')
    rx_typed_str = re.compile(r":\s*Str\s*>")

    hits: list[str] = []
    index = 0

    while index < len(lines_no_comments):
        if not start_rx.search(lines_no_comments[index]):
            index += 1
            continue

        block_end = _get_brace_balanced_end_line(index, lines_no_strings)
        block_text = "\n".join(lines_no_comments[index : block_end + 1])

        if rx_has_str_pat.search(block_text) and not rx_typed_str.search(block_text):
            first_line = orig_lines[index].strip() if index < len(orig_lines) else ""
            hits.append(f"lines {index + 1}-{block_end + 1}: {first_line}")

        index = block_end + 1

    return hits