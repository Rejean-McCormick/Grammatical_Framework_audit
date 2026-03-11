from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from app import config
from app.models import RunConfig, RunPaths


_SAFE_NAME_RX = re.compile(r'[\\/:*?"<>|\s]+')
_MULTI_UNDERSCORE_RX = re.compile(r"_+")


def safe_name(value: str | Path) -> str:
    """
    Convert an arbitrary path-like value into a filesystem-safe flat name.

    Examples:
        lib/src/albanian/GrammarSqi.gf -> lib_src_albanian_GrammarSqi.gf
        C:\\tmp\\a b.txt -> C_tmp_a_b.txt
    """
    text = str(value).strip()
    if not text:
        return "unnamed"

    sanitized = _SAFE_NAME_RX.sub("_", text)
    sanitized = _MULTI_UNDERSCORE_RX.sub("_", sanitized).strip("._")

    return sanitized or "unnamed"


def normalize_path(value: str | Path | None, *, base_dir: str | Path | None = None) -> Path:
    """
    Normalize a path to an absolute resolved Path.

    If value is relative and base_dir is provided, the path is resolved against base_dir.
    """
    if value is None:
        raise ValueError("Path value cannot be None")

    text = str(value).strip()
    if not text:
        raise ValueError("Path value cannot be empty")

    path = Path(text).expanduser()

    if not path.is_absolute() and base_dir is not None:
        path = Path(base_dir).expanduser() / path

    return path.resolve()


def make_run_id(now: datetime | None = None) -> str:
    """
    Build a canonical run identifier.

    Format:
        YYYYMMDD_HHMMSS
    """
    effective_now = now or datetime.now(timezone.utc).astimezone()
    return effective_now.strftime("%Y%m%d_%H%M%S")


def build_run_dir(out_root: str | Path, run_id: str | None = None) -> Path:
    """
    Build the run directory path.

    The directory is created if it does not already exist.
    """
    normalized_out_root = normalize_path(out_root)
    normalized_out_root.mkdir(parents=True, exist_ok=True)

    effective_run_id = (run_id or make_run_id()).strip()
    if not effective_run_id:
        raise ValueError("run_id cannot be empty")

    run_dir = normalized_out_root / f"{config.RUN_DIR_PREFIX}{effective_run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir.resolve()


def build_output_paths(run_config: RunConfig, run_id: str | None = None) -> RunPaths:
    """
    Create and return all canonical output paths for a run.

    This function also creates the directory tree required by the run.
    """
    run_dir = build_run_dir(run_config.out_root, run_id=run_id)
    effective_run_id = run_dir.name.removeprefix(config.RUN_DIR_PREFIX)

    details_dir = run_dir / config.DETAILS_DIRNAME
    raw_dir = run_dir / config.RAW_DIRNAME
    compile_logs_dir = raw_dir / config.COMPILE_LOGS_DIRNAME
    scan_logs_dir = raw_dir / config.SCAN_LOGS_DIRNAME
    artifacts_dir = raw_dir / config.ARTIFACTS_DIRNAME
    gfo_dir = artifacts_dir / config.GFO_DIRNAME
    out_dir = artifacts_dir / config.OUT_DIRNAME

    for directory in (
        details_dir,
        raw_dir,
        compile_logs_dir,
        scan_logs_dir,
        artifacts_dir,
        gfo_dir,
        out_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    return RunPaths(
        run_id=effective_run_id,
        run_dir=run_dir,
        master_log_path=raw_dir / config.MASTER_LOG_FILENAME,
        all_scan_logs_path=raw_dir / config.ALL_SCAN_LOGS_FILENAME,
        all_logs_path=raw_dir / config.ALL_LOGS_FILENAME,
        summary_json_path=run_dir / config.SUMMARY_JSON_FILENAME,
        summary_md_path=run_dir / config.SUMMARY_MD_FILENAME,
        ai_brief_path=run_dir / config.AI_BRIEF_FILENAME,
        top_errors_path=run_dir / config.TOP_ERRORS_FILENAME,
        details_dir=details_dir,
        raw_dir=raw_dir,
        compile_logs_dir=compile_logs_dir,
        scan_logs_dir=scan_logs_dir,
        artifacts_dir=artifacts_dir,
        gfo_dir=gfo_dir,
        out_dir=out_dir,
    )


def relative_to_project_root(file_path: str | Path, project_root: str | Path) -> str:
    """
    Return a normalized project-relative path using forward slashes.

    If file_path is not under project_root, return the normalized absolute path.
    """
    normalized_file_path = normalize_path(file_path)
    normalized_project_root = normalize_path(project_root)

    try:
        return normalized_file_path.relative_to(normalized_project_root).as_posix()
    except ValueError:
        return normalized_file_path.as_posix()