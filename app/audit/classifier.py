from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, Mapping

from app.models import FileResult


STATUS_OK = "OK"
STATUS_FAIL = "FAIL"
STATUS_SKIPPED = "SKIPPED"

DIAG_OK = "ok"
DIAG_DIRECT = "direct"
DIAG_DOWNSTREAM = "downstream"
DIAG_AMBIGUOUS = "ambiguous"
DIAG_NOISE = "noise"
DIAG_SKIPPED = "skipped"

ERROR_KIND_OK = "OK"
OBVIOUS_DIRECT_ERROR_KINDS = {"INTERNAL", "TIMEOUT", "SCRIPT"}
LIKELY_DIRECT_ERROR_KINDS = {"TYPE", "SYNTAX"}

_GF_FILE_REF_RE = re.compile(r"([A-Za-z0-9_./\\-]+\.gf)\b", re.IGNORECASE)


def classify_file_results(file_results: list[FileResult]) -> list[FileResult]:
    if not file_results:
        return file_results

    all_results_by_file = {_path_key(result.file_path): result for result in file_results}
    all_results_by_module = {
        _module_key(result.module_name or _module_name_from_path(result.file_path)): result
        for result in file_results
    }

    for file_result in file_results:
        _initialize_status(file_result)

    failing_results = [result for result in file_results if result.status == STATUS_FAIL]
    failing_results_by_file = {_path_key(result.file_path): result for result in failing_results}
    failing_results_by_module = {
        _module_key(result.module_name or _module_name_from_path(result.file_path)): result
        for result in failing_results
    }

    for file_result in file_results:
        classify_single_result(
            file_result=file_result,
            all_results_by_file=all_results_by_file,
            all_results_by_module=all_results_by_module,
            failing_results_by_file=failing_results_by_file,
            failing_results_by_module=failing_results_by_module,
        )

    for file_result in file_results:
        if file_result.diagnostic_class != DIAG_DOWNSTREAM:
            continue
        file_result.blocked_by = _collapse_blocked_by_to_roots(
            blocked_by=file_result.blocked_by,
            failing_results_by_file=failing_results_by_file,
        )

    return file_results


def classify_single_result(
    file_result: FileResult,
    all_results_by_file: Mapping[str, FileResult],
    all_results_by_module: Mapping[str, FileResult],
    failing_results_by_file: Mapping[str, FileResult],
    failing_results_by_module: Mapping[str, FileResult],
) -> FileResult:
    _initialize_status(file_result)

    if file_result.status == STATUS_OK:
        file_result.diagnostic_class = DIAG_OK
        file_result.is_direct = False
        file_result.blocked_by = []
        return file_result

    if file_result.status == STATUS_SKIPPED:
        file_result.diagnostic_class = DIAG_SKIPPED
        file_result.is_direct = False
        file_result.blocked_by = []
        return file_result

    all_referenced_results = _resolve_referenced_results(
        file_result=file_result,
        results_by_file=all_results_by_file,
        results_by_module=all_results_by_module,
    )
    blocked_by = resolve_blocked_by(
        file_result=file_result,
        failing_results_by_file=failing_results_by_file,
        failing_results_by_module=failing_results_by_module,
    )

    self_path_key = _path_key(file_result.file_path)
    self_module_key = _module_key(file_result.module_name or _module_name_from_path(file_result.file_path))
    self_referenced = any(
        _path_key(result.file_path) == self_path_key
        or _module_key(result.module_name or _module_name_from_path(result.file_path)) == self_module_key
        for result in all_referenced_results
    )

    error_kind = _get_error_kind(file_result)

    if error_kind in OBVIOUS_DIRECT_ERROR_KINDS or self_referenced:
        file_result.diagnostic_class = DIAG_DIRECT
        file_result.is_direct = True
        file_result.blocked_by = []
        return file_result

    if blocked_by:
        file_result.diagnostic_class = DIAG_DOWNSTREAM
        file_result.is_direct = False
        file_result.blocked_by = blocked_by
        return file_result

    if all_referenced_results:
        file_result.diagnostic_class = DIAG_AMBIGUOUS
        file_result.is_direct = False
        file_result.blocked_by = []
        return file_result

    if error_kind in LIKELY_DIRECT_ERROR_KINDS:
        file_result.diagnostic_class = DIAG_DIRECT
        file_result.is_direct = True
        file_result.blocked_by = []
        return file_result

    file_result.diagnostic_class = DIAG_AMBIGUOUS
    file_result.is_direct = False
    file_result.blocked_by = []
    return file_result


def resolve_blocked_by(
    file_result: FileResult,
    failing_results_by_file: Mapping[str, FileResult],
    failing_results_by_module: Mapping[str, FileResult],
) -> list[str]:
    first_error = _get_first_error(file_result)
    if not first_error:
        return []

    self_path_key = _path_key(file_result.file_path)
    self_module_key = _module_key(file_result.module_name or _module_name_from_path(file_result.file_path))

    blocked_by: list[str] = []
    seen: set[str] = set()

    for file_ref in _extract_file_refs(first_error):
        referenced_result = failing_results_by_file.get(_path_key(file_ref))
        if referenced_result is None:
            referenced_result = failing_results_by_module.get(_module_key(Path(file_ref).stem))
        if referenced_result is None:
            continue

        ref_path_key = _path_key(referenced_result.file_path)
        ref_module_key = _module_key(
            referenced_result.module_name or _module_name_from_path(referenced_result.file_path)
        )

        if ref_path_key == self_path_key or ref_module_key == self_module_key:
            continue

        canonical_path = _display_path(referenced_result.file_path)
        if canonical_path in seen:
            continue

        seen.add(canonical_path)
        blocked_by.append(canonical_path)

    return blocked_by


def _initialize_status(file_result: FileResult) -> None:
    compile_summary = getattr(file_result, "compile_summary", None)
    if compile_summary is None:
        file_result.status = STATUS_SKIPPED
        file_result.diagnostic_class = DIAG_SKIPPED
        file_result.is_direct = False
        file_result.blocked_by = []
        return

    error_kind = _get_error_kind(file_result)
    exit_code = int(getattr(compile_summary, "exit_code", 0) or 0)

    if error_kind == ERROR_KIND_OK and exit_code == 0:
        file_result.status = STATUS_OK
        file_result.diagnostic_class = DIAG_OK
        file_result.is_direct = False
        file_result.blocked_by = []
        return

    file_result.status = STATUS_FAIL
    file_result.diagnostic_class = ""
    file_result.is_direct = False
    file_result.blocked_by = []


def _resolve_referenced_results(
    file_result: FileResult,
    results_by_file: Mapping[str, FileResult],
    results_by_module: Mapping[str, FileResult],
) -> list[FileResult]:
    first_error = _get_first_error(file_result)
    if not first_error:
        return []

    resolved: list[FileResult] = []
    seen: set[str] = set()

    for file_ref in _extract_file_refs(first_error):
        referenced_result = results_by_file.get(_path_key(file_ref))
        if referenced_result is None:
            referenced_result = results_by_module.get(_module_key(Path(file_ref).stem))
        if referenced_result is None:
            continue

        result_key = _path_key(referenced_result.file_path)
        if result_key in seen:
            continue

        seen.add(result_key)
        resolved.append(referenced_result)

    return resolved


def _collapse_blocked_by_to_roots(
    blocked_by: Iterable[str],
    failing_results_by_file: Mapping[str, FileResult],
) -> list[str]:
    roots: list[str] = []
    seen: set[str] = set()

    for file_path in blocked_by:
        for root_path in _collect_direct_roots(file_path, failing_results_by_file, visited=set()):
            if root_path in seen:
                continue
            seen.add(root_path)
            roots.append(root_path)

    return roots


def _collect_direct_roots(
    file_path: str,
    failing_results_by_file: Mapping[str, FileResult],
    visited: set[str],
) -> list[str]:
    normalized = _path_key(file_path)
    if not normalized or normalized in visited:
        return []

    visited.add(normalized)
    file_result = failing_results_by_file.get(normalized)
    if file_result is None:
        return [_display_path(file_path)]

    if file_result.diagnostic_class == DIAG_DIRECT:
        return [_display_path(file_result.file_path)]

    if file_result.diagnostic_class != DIAG_DOWNSTREAM or not getattr(file_result, "blocked_by", None):
        return [_display_path(file_result.file_path)]

    roots: list[str] = []
    seen: set[str] = set()
    for blocked_path in file_result.blocked_by:
        for root_path in _collect_direct_roots(blocked_path, failing_results_by_file, visited):
            if root_path in seen:
                continue
            seen.add(root_path)
            roots.append(root_path)
    return roots


def _extract_file_refs(text: str) -> list[str]:
    refs: list[str] = []
    seen: set[str] = set()

    for match in _GF_FILE_REF_RE.finditer(text or ""):
        candidate = match.group(1).strip().rstrip(".,;:)]}")
        if not candidate:
            continue

        normalized = _path_key(candidate)
        if normalized in seen:
            continue

        seen.add(normalized)
        refs.append(candidate)

    return refs


def _get_error_kind(file_result: FileResult) -> str:
    compile_summary = getattr(file_result, "compile_summary", None)
    if compile_summary is None:
        return "SCRIPT"
    return str(getattr(compile_summary, "error_kind", "") or "").strip().upper() or "OTHER"


def _get_first_error(file_result: FileResult) -> str:
    compile_summary = getattr(file_result, "compile_summary", None)
    if compile_summary is None:
        return ""
    return str(getattr(compile_summary, "first_error", "") or "").strip()


def _display_path(value: object) -> str:
    return Path(str(value)).as_posix() if value is not None else ""


def _path_key(value: object) -> str:
    if value is None:
        return ""
    return Path(str(value)).as_posix().lower()


def _module_key(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _module_name_from_path(file_path: object) -> str:
    return Path(str(file_path)).stem if file_path is not None else ""