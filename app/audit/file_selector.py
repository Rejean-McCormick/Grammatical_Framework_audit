from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.models import RunConfig


@dataclass(frozen=True, slots=True)
class ExcludedFileEntry:
    file_path: Path
    excluded_reason: str


def select_files(run_config: RunConfig) -> tuple[list[Path], list[ExcludedFileEntry]]:
    """
    Select files according to run mode and filter rules.

    Returns:
        (selected_files, excluded_files)

    Notes:
        - selected_files are absolute Path objects
        - excluded_files contains files discovered during enumeration but not selected
        - in single-file mode, the target file must resolve to exactly one file
    """
    project_root = Path(run_config.project_root).resolve()
    scan_root = _build_scan_root(project_root, run_config.scan_dir)

    if run_config.mode == "file":
        target_path = _resolve_target_file(
            project_root=project_root,
            scan_root=scan_root,
            target_file=run_config.target_file,
        )
        selected_files, excluded_files = filter_candidate_files(
            candidate_files=[target_path],
            run_config=run_config,
        )
        if not selected_files:
            reason = excluded_files[0].excluded_reason if excluded_files else "target file was excluded"
            raise ValueError(f"Target file was not selected: {target_path} ({reason})")
        return selected_files, excluded_files

    candidate_files = _enumerate_candidate_files(
        scan_root=scan_root,
        scan_glob=run_config.scan_glob,
        max_files=run_config.max_files,
    )

    return filter_candidate_files(
        candidate_files=candidate_files,
        run_config=run_config,
    )


def filter_candidate_files(
    candidate_files: Iterable[Path],
    run_config: RunConfig,
) -> tuple[list[Path], list[ExcludedFileEntry]]:
    """
    Apply include/exclude rules to candidate files.

    Rules are evaluated against:
        - file name, e.g. GrammarSqi.gf
        - relative path from project root, normalized with forward slashes

    Returns:
        (selected_files, excluded_files)
    """
    project_root = Path(run_config.project_root).resolve()
    include_rx = _compile_optional_regex(run_config.include_regex)
    exclude_rx = _compile_optional_regex(run_config.exclude_regex)

    selected_files: list[Path] = []
    excluded_files: list[ExcludedFileEntry] = []

    seen: set[Path] = set()

    for file_path in sorted((Path(p).resolve() for p in candidate_files), key=lambda p: str(p).lower()):
        if file_path in seen:
            continue
        seen.add(file_path)

        is_allowed, excluded_reason = is_included_file(
            file_path=file_path,
            project_root=project_root,
            include_rx=include_rx,
            exclude_rx=exclude_rx,
        )

        if is_allowed:
            selected_files.append(file_path)
        else:
            excluded_files.append(
                ExcludedFileEntry(
                    file_path=file_path,
                    excluded_reason=excluded_reason,
                )
            )

    return selected_files, excluded_files


def is_included_file(
    file_path: Path,
    project_root: Path,
    include_rx: re.Pattern[str] | None,
    exclude_rx: re.Pattern[str] | None,
) -> tuple[bool, str]:
    """
    Decide whether a file should be included.

    Returns:
        (is_included, excluded_reason)

    Exclusion reasons are stable strings intended for reporting.
    """
    resolved_file_path = Path(file_path).resolve()

    if not resolved_file_path.exists():
        return False, "missing_file"

    if not resolved_file_path.is_file():
        return False, "not_a_file"

    if resolved_file_path.suffix.lower() != ".gf":
        return False, "not_gf_file"

    try:
        relative_path = resolved_file_path.relative_to(project_root).as_posix()
    except ValueError:
        relative_path = resolved_file_path.as_posix()

    file_name = resolved_file_path.name

    if exclude_rx and (exclude_rx.search(file_name) or exclude_rx.search(relative_path)):
        return False, "excluded_by_regex"

    if include_rx and not (include_rx.search(file_name) or include_rx.search(relative_path)):
        return False, "not_matched_by_include_regex"

    return True, ""


def extract_module_name(file_path: Path) -> str:
    """
    Extract the GF module name from a file path.

    Example:
        GrammarSqi.gf -> GrammarSqi
    """
    return Path(file_path).stem


def _build_scan_root(project_root: Path, scan_dir: str) -> Path:
    if not scan_dir:
        return project_root

    scan_root = (project_root / scan_dir).resolve()
    if not scan_root.exists():
        raise FileNotFoundError(f"Scan directory does not exist: {scan_root}")
    if not scan_root.is_dir():
        raise NotADirectoryError(f"Scan directory is not a directory: {scan_root}")
    return scan_root


def _enumerate_candidate_files(
    scan_root: Path,
    scan_glob: str,
    max_files: int,
) -> list[Path]:
    if not scan_glob:
        scan_glob = "*.gf"

    candidate_files = [
        path.resolve()
        for path in scan_root.rglob(scan_glob)
        if path.is_file()
    ]

    candidate_files.sort(key=lambda p: str(p).lower())

    if max_files and max_files > 0:
        candidate_files = candidate_files[:max_files]

    return candidate_files


def _resolve_target_file(
    project_root: Path,
    scan_root: Path,
    target_file: str | Path | None,
) -> Path:
    if target_file is None:
        raise ValueError("Single-file mode requires target_file")

    target_text = str(target_file).strip()
    if not target_text:
        raise ValueError("Single-file mode requires a non-empty target_file")

    target_path = Path(target_text)

    direct_candidates: list[Path] = []

    if target_path.is_absolute():
        direct_candidates.append(target_path)
    else:
        direct_candidates.append(project_root / target_path)
        direct_candidates.append(scan_root / target_path)

    for candidate in direct_candidates:
        resolved = candidate.resolve()
        if resolved.exists() and resolved.is_file():
            return resolved

    basename = target_path.name
    basename_matches = [
        path.resolve()
        for path in scan_root.rglob("*.gf")
        if path.is_file() and path.name == basename
    ]

    if len(basename_matches) == 1:
        return basename_matches[0]

    if len(basename_matches) > 1:
        raise ValueError(
            "Target file is ambiguous. Multiple matches found for "
            f"'{basename}': {[str(p) for p in sorted(basename_matches)]}"
        )

    raise FileNotFoundError(f"Target file not found: {target_text}")


def _compile_optional_regex(pattern: str | None) -> re.Pattern[str] | None:
    if pattern is None:
        return None

    normalized = pattern.strip()
    if not normalized:
        return None

    return re.compile(normalized)

