from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from ..models import RunConfig


_VALID_MODES = {"all", "file"}


class ValidationError(ValueError):
    """Raised when a user-provided value is invalid."""


def validate_existing_directory(
    path_value: str | Path,
    *,
    field_name: str = "directory",
) -> Path:
    path = _normalize_path(path_value, field_name=field_name)
    if not path.exists():
        raise ValidationError(f"{field_name} does not exist: {path}")
    if not path.is_dir():
        raise ValidationError(f"{field_name} is not a directory: {path}")
    return path.resolve()


def validate_existing_file(
    path_value: str | Path,
    *,
    field_name: str = "file",
) -> Path:
    path = _normalize_path(path_value, field_name=field_name)
    if not path.exists():
        raise ValidationError(f"{field_name} does not exist: {path}")
    if not path.is_file():
        raise ValidationError(f"{field_name} is not a file: {path}")
    return path.resolve()


def validate_mode(mode: str) -> str:
    normalized_mode = (mode or "").strip().lower()
    if normalized_mode not in _VALID_MODES:
        allowed = ", ".join(sorted(_VALID_MODES))
        raise ValidationError(f"mode must be one of: {allowed}")
    return normalized_mode


def validate_regex(
    pattern: str | None,
    *,
    field_name: str = "regex",
    allow_empty: bool = True,
) -> str:
    normalized_pattern = "" if pattern is None else str(pattern).strip()

    if not normalized_pattern:
        if allow_empty:
            return ""
        raise ValidationError(f"{field_name} cannot be empty")

    try:
        re.compile(normalized_pattern)
    except re.error as exc:
        raise ValidationError(f"{field_name} is not a valid regex: {exc}") from exc

    return normalized_pattern


def validate_timeout_sec(
    timeout_sec: int | str,
    *,
    min_value: int = 1,
    max_value: int = 3600,
) -> int:
    if timeout_sec is None or str(timeout_sec).strip() == "":
        raise ValidationError("timeout_sec cannot be empty")

    try:
        normalized_timeout = int(timeout_sec)
    except (TypeError, ValueError) as exc:
        raise ValidationError("timeout_sec must be an integer") from exc

    if normalized_timeout < min_value:
        raise ValidationError(f"timeout_sec must be >= {min_value}")
    if normalized_timeout > max_value:
        raise ValidationError(f"timeout_sec must be <= {max_value}")

    return normalized_timeout


def validate_run_config(run_config: RunConfig) -> list[str]:
    errors: list[str] = []

    try:
        project_root = validate_existing_directory(
            run_config.project_root,
            field_name="project_root",
        )
    except ValidationError as exc:
        errors.append(str(exc))
        project_root = None

    try:
        validate_existing_directory(
            run_config.rgl_root,
            field_name="rgl_root",
        )
    except ValidationError as exc:
        errors.append(str(exc))

    try:
        _validate_executable(
            run_config.gf_exe,
            field_name="gf_exe",
        )
    except ValidationError as exc:
        errors.append(str(exc))

    try:
        normalized_mode = validate_mode(run_config.mode)
    except ValidationError as exc:
        errors.append(str(exc))
        normalized_mode = ""

    try:
        validate_timeout_sec(run_config.timeout_sec)
    except ValidationError as exc:
        errors.append(str(exc))

    try:
        validate_regex(
            run_config.include_regex,
            field_name="include_regex",
            allow_empty=False,
        )
    except ValidationError as exc:
        errors.append(str(exc))

    try:
        validate_regex(
            run_config.exclude_regex,
            field_name="exclude_regex",
            allow_empty=True,
        )
    except ValidationError as exc:
        errors.append(str(exc))

    scan_root: Path | None = None
    if project_root is not None:
        try:
            scan_root = _resolve_scan_root(project_root, run_config.scan_dir)
        except ValidationError as exc:
            errors.append(str(exc))

    try:
        _validate_out_root(
            run_config.out_root,
            field_name="out_root",
        )
    except ValidationError as exc:
        errors.append(str(exc))

    scan_glob = (run_config.scan_glob or "").strip()
    if not scan_glob:
        errors.append("scan_glob cannot be empty")

    max_files = _coerce_int(getattr(run_config, "max_files", 0), default=0)
    if max_files < 0:
        errors.append("max_files must be >= 0")

    if normalized_mode == "file":
        try:
            _resolve_target_file(
                target_file=getattr(run_config, "target_file", ""),
                project_root=project_root,
                scan_root=scan_root,
            )
        except ValidationError as exc:
            errors.append(str(exc))

    return errors


def _normalize_path(path_value: str | Path, *, field_name: str) -> Path:
    if path_value is None:
        raise ValidationError(f"{field_name} cannot be empty")

    text = str(path_value).strip()
    if not text:
        raise ValidationError(f"{field_name} cannot be empty")

    return Path(text).expanduser()


def _validate_executable(
    executable_value: str | Path,
    *,
    field_name: str,
) -> Path | str:
    if executable_value is None or str(executable_value).strip() == "":
        raise ValidationError(f"{field_name} cannot be empty")

    raw_value = str(executable_value).strip()

    looks_like_path = (
        any(sep in raw_value for sep in ("/", "\\"))
        or Path(raw_value).suffix != ""
    )

    if looks_like_path:
        return validate_existing_file(raw_value, field_name=field_name)

    resolved = shutil.which(raw_value)
    if resolved:
        return resolved

    raise ValidationError(
        f"{field_name} was not found as a file or command: {raw_value}"
    )


def _resolve_scan_root(project_root: Path, scan_dir: str | Path) -> Path:
    if scan_dir is None or str(scan_dir).strip() == "":
        return project_root.resolve()

    scan_dir_path = Path(str(scan_dir).strip())
    candidate = (
        scan_dir_path
        if scan_dir_path.is_absolute()
        else project_root / scan_dir_path
    )

    if not candidate.exists():
        raise ValidationError(f"scan_dir does not exist: {candidate}")
    if not candidate.is_dir():
        raise ValidationError(f"scan_dir is not a directory: {candidate}")

    return candidate.resolve()


def _validate_out_root(out_root: str | Path, *, field_name: str) -> Path:
    path = _normalize_path(out_root, field_name=field_name)

    if path.exists() and not path.is_dir():
        raise ValidationError(f"{field_name} exists but is not a directory: {path}")

    parent = path.parent
    if not parent.exists():
        raise ValidationError(f"{field_name} parent directory does not exist: {parent}")
    if not parent.is_dir():
        raise ValidationError(f"{field_name} parent is not a directory: {parent}")

    return path.resolve(strict=False)


def _resolve_target_file(
    *,
    target_file: str | Path,
    project_root: Path | None,
    scan_root: Path | None,
) -> Path:
    if target_file is None or str(target_file).strip() == "":
        raise ValidationError("target_file is required when mode='file'")

    raw_target = Path(str(target_file).strip()).expanduser()
    candidates: list[Path] = []

    if raw_target.is_absolute():
        candidates.append(raw_target)
    else:
        if scan_root is not None:
            candidates.append(scan_root / raw_target)
        if project_root is not None:
            candidates.append(project_root / raw_target)
        candidates.append(raw_target)

    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            return candidate.resolve()

    rendered_candidates = ", ".join(str(candidate) for candidate in candidates)
    raise ValidationError(
        f"target_file was not found. Tried: {rendered_candidates}"
    )


def _coerce_int(value: Any, *, default: int) -> int:
    if value is None or str(value).strip() == "":
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


__all__ = [
    "ValidationError",
    "validate_existing_directory",
    "validate_existing_file",
    "validate_mode",
    "validate_regex",
    "validate_run_config",
    "validate_timeout_sec",
]