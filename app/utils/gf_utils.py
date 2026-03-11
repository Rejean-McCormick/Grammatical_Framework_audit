from __future__ import annotations

from typing import Pattern
import re

from app.models import CompileSummary

_RX_INTERNAL_GENERATE_PMCFG = re.compile(r"Internal error in GeneratePMCFG", re.MULTILINE)
_RX_EXPECTED = re.compile(r"^\s*expected:\s*(.*)$", re.MULTILINE)
_RX_INFERRED = re.compile(r"^\s*inferred:\s*(.*)$", re.MULTILINE)
_RX_HAPPENED_IN = re.compile(r"Happened in[^\r\n]*", re.MULTILINE)
_RX_SYNTAX = re.compile(r"^.*(Syntax error|Parse error|Unexpected token).*$", re.MULTILINE)

_RX_CASE = re.compile(r"\bcase\b")
_RX_HEAD_HAS_DOT_S = re.compile(r"\.\s*s\b")
_RX_HEAD_HAS_OF_BRACE = re.compile(r"\bof\s*\{")
_RX_LITERAL_BRANCH = re.compile(r'"[^"]*"\s*=>')
_RX_HAS_STR_PATTERN = re.compile(r'(_\s*\+\s*".+?"|".+?"\s*\+\s*_)')
_RX_TYPED_STR = re.compile(r":\s*Str\s*>")

_RX_CASE_START = re.compile(r"\bcase\b.*\bof\s*\{")
_RX_TABLE_START = re.compile(r"\btable\s*\{")


def process_gf_line(line: str | None, in_block_comment: bool) -> tuple[str, str, bool]:
    if line is None:
        line = ""

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
                keep_chars.extend((" ", " "))
                masked_chars.extend((" ", " "))
                index += 2
                continue

            keep_chars.append(" ")
            masked_chars.append(" ")
            index += 1
            continue

        if in_string:
            if ch == "\\" and next_ch != "\0":
                keep_chars.extend((ch, next_ch))
                masked_chars.extend((" ", " "))
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
            keep_chars.extend((" ", " "))
            masked_chars.extend((" ", " "))
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


def strip_comments_and_mask_strings(orig_lines: list[str]) -> tuple[list[str], list[str]]:
    in_block_comment = False
    lines_no_comments: list[str] = []
    lines_no_strings: list[str] = []

    for line in orig_lines:
        no_comments, no_comments_no_strings, in_block_comment = process_gf_line(
            line=line,
            in_block_comment=in_block_comment,
        )
        lines_no_comments.append(no_comments)
        lines_no_strings.append(no_comments_no_strings)

    return lines_no_comments, lines_no_strings


def get_brace_balanced_end_line(start_line: int, lines_no_strings: list[str] | None) -> int:
    if not lines_no_strings:
        return start_line

    depth = 0
    started = False

    for line_index in range(start_line, len(lines_no_strings)):
        line = lines_no_strings[line_index] or ""
        for ch in line:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1

        if started and depth <= 0:
            return line_index

    return start_line


def find_runtime_string_match_blocks(
    lines_no_comments: list[str] | None,
    lines_no_strings: list[str] | None,
    orig_lines: list[str] | None,
) -> list[str]:
    if lines_no_comments is None:
        lines_no_comments = []
    if lines_no_strings is None:
        lines_no_strings = []
    if orig_lines is None:
        orig_lines = []

    hits: list[str] = []
    index = 0

    while index < len(lines_no_comments):
        line = lines_no_comments[index] or ""
        if not _RX_CASE.search(line):
            index += 1
            continue

        head = line
        end_head = index
        while (
            end_head + 1 < len(lines_no_comments)
            and not _RX_HEAD_HAS_OF_BRACE.search(head)
            and len(head) < 800
        ):
            end_head += 1
            next_line = re.sub(r"\s+", " ", (lines_no_comments[end_head] or ""))
            head += " " + next_line

        if not (_RX_HEAD_HAS_OF_BRACE.search(head) and _RX_HEAD_HAS_DOT_S.search(head)):
            index += 1
            continue

        block_end = get_brace_balanced_end_line(index, lines_no_strings)
        block_text = "\n".join(lines_no_comments[index : block_end + 1])

        if _RX_LITERAL_BRANCH.search(block_text):
            first_line = orig_lines[index].strip() if index < len(orig_lines) else ""
            hits.append(f"lines {index + 1}-{block_end + 1}: {first_line}")

        index = block_end + 1

    return hits


def find_untyped_blocks_with_str_patterns(
    start_rx: Pattern[str],
    lines_no_comments: list[str] | None,
    lines_no_strings: list[str] | None,
    orig_lines: list[str] | None,
) -> list[str]:
    if lines_no_comments is None:
        lines_no_comments = []
    if lines_no_strings is None:
        lines_no_strings = []
    if orig_lines is None:
        orig_lines = []

    hits: list[str] = []
    index = 0

    while index < len(lines_no_comments):
        current_line = lines_no_comments[index] or ""
        if not start_rx.search(current_line):
            index += 1
            continue

        block_end = get_brace_balanced_end_line(index, lines_no_strings)
        block_text = "\n".join(lines_no_comments[index : block_end + 1])

        if _RX_HAS_STR_PATTERN.search(block_text) and not _RX_TYPED_STR.search(block_text):
            first_line = orig_lines[index].strip() if index < len(orig_lines) else ""
            hits.append(f"lines {index + 1}-{block_end + 1}: {first_line}")

        index = block_end + 1

    return hits


def parse_compile_summary(
    combined_text: str,
    timed_out: bool,
    exit_code: int,
    stdout_path: str | None = None,
    stderr_path: str | None = None,
    duration_ms: int = 0,
) -> CompileSummary:
    if timed_out:
        return CompileSummary(
            exit_code=997 if exit_code == 0 else exit_code,
            timed_out=True,
            duration_ms=duration_ms,
            error_kind="TIMEOUT",
            first_error="TIMEOUT (killed)",
            error_detail="",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

    if _RX_INTERNAL_GENERATE_PMCFG.search(combined_text):
        match = re.search(r"^.*Internal error in GeneratePMCFG.*$", combined_text, re.MULTILINE)
        first_error = match.group(0).strip() if match else "Internal error in GeneratePMCFG"
        return CompileSummary(
            exit_code=exit_code,
            timed_out=False,
            duration_ms=duration_ms,
            error_kind="INTERNAL",
            first_error=first_error,
            error_detail="GeneratePMCFG",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

    if _RX_EXPECTED.search(combined_text) and _RX_INFERRED.search(combined_text):
        happened_in = _RX_HAPPENED_IN.search(combined_text)
        expected = _RX_EXPECTED.search(combined_text)
        inferred = _RX_INFERRED.search(combined_text)

        first_error = happened_in.group(0).strip() if happened_in else "Type error"
        expected_text = expected.group(1).strip() if expected else ""
        inferred_text = inferred.group(1).strip() if inferred else ""
        detail = f"expected: {expected_text} | inferred: {inferred_text}"

        return CompileSummary(
            exit_code=exit_code,
            timed_out=False,
            duration_ms=duration_ms,
            error_kind="TYPE",
            first_error=first_error,
            error_detail=detail,
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

    syntax_match = _RX_SYNTAX.search(combined_text)
    if syntax_match:
        return CompileSummary(
            exit_code=exit_code,
            timed_out=False,
            duration_ms=duration_ms,
            error_kind="SYNTAX",
            first_error=syntax_match.group(0).strip(),
            error_detail="",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

    if exit_code != 0:
        for line in re.split(r"\r?\n", combined_text):
            stripped = (line or "").strip()
            if not stripped:
                continue
            if re.match(r"^- compiling\b", stripped):
                continue
            if re.match(r"^(linking|Writing)\b", stripped):
                continue

            return CompileSummary(
                exit_code=exit_code,
                timed_out=False,
                duration_ms=duration_ms,
                error_kind="OTHER",
                first_error=stripped,
                error_detail="",
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )

        return CompileSummary(
            exit_code=exit_code,
            timed_out=False,
            duration_ms=duration_ms,
            error_kind="OTHER",
            first_error="Non-zero exit (no message matched)",
            error_detail="",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

    return CompileSummary(
        exit_code=exit_code,
        timed_out=False,
        duration_ms=duration_ms,
        error_kind="OK",
        first_error="",
        error_detail="",
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


__all__ = [
    "_RX_CASE_START",
    "_RX_TABLE_START",
    "find_runtime_string_match_blocks",
    "find_untyped_blocks_with_str_patterns",
    "get_brace_balanced_end_line",
    "parse_compile_summary",
    "process_gf_line",
    "strip_comments_and_mask_strings",
]