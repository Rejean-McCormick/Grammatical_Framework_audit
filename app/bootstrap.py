from __future__ import annotations

import json
import os
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from . import config as cfg
    from .models import AppConfig, RunConfig, RunPaths
except ImportError:  # pragma: no cover
    import config as cfg  # type: ignore
    from models import AppConfig, RunConfig, RunPaths  # type: ignore


# ---------------------------------------------------------------------------
# Defaults / fallbacks
# ---------------------------------------------------------------------------

_STATE_FILENAME_FALLBACK = ".gf_audit_state.json"
_MODE_ALL = "all"
_MODE_FILE = "file"
_ALLOWED_MODES = {_MODE_ALL, _MODE_FILE}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cfg(name: str, default: Any) -> Any:
    return getattr(cfg, name, default)


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_run_id() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _normalize_path(value: str | os.PathLike[str] | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    try:
        return path.resolve(strict=False)
    except OSError:
        return path.absolute()


def _normalize_str(value: str | None) -> str:
    return (value or "").strip()


def _normalize_optional_str(value: str | None) -> str | None:
    text = _normalize_str(value)
    return text or None


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _serialize_path(value: Path | None) -> str | None:
    return str(value) if value is not None else None


def _serialize_dataclass(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    return value


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> Path:
    _ensure_dir(path.parent)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp_path.replace(path)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _discover_rgl_folders(rgl_root: Path) -> list[str]:
    candidates = ["present", "alltenses", "common", "abstract", "prelude", "compat", "api"]
    found: list[str] = []
    for folder_name in candidates:
        if (rgl_root / folder_name).exists():
            found.append(folder_name)
    return found


def _build_default_gf_path(scan_dir: str, rgl_root: Path) -> str:
    parts: list[str] = ["lib/src"]

    normalized_scan_dir = scan_dir.replace("\\", "/").strip("/")
    if normalized_scan_dir and normalized_scan_dir not in parts:
        parts.append(normalized_scan_dir)

    for folder_name in _discover_rgl_folders(rgl_root):
        if folder_name not in parts:
            parts.append(folder_name)

    return ":".join(parts)


def _coerce_target_file(value: str | os.PathLike[str] | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _build_default_state() -> dict[str, Any]:
    return {
        "selected_mode": _MODE_ALL,
        "selected_target_file": None,
        "selected_project_root": None,
        "selected_rgl_root": None,
        "selected_gf_exe": None,
        "selected_out_root": None,
        "is_running": False,
        "last_run_dir": None,
        "last_summary_path": None,
        "status_message": "",
        "current_run_config": None,
        "current_run_result": None,
    }


def _get_state_path(
    state_path: str | os.PathLike[str] | Path | None = None,
    *,
    app_config: AppConfig | None = None,
) -> Path:
    explicit = _normalize_path(state_path)
    if explicit is not None:
        return explicit

    filename = _cfg("STATE_FILENAME", _STATE_FILENAME_FALLBACK)

    if app_config is not None:
        out_root = _normalize_path(getattr(app_config, "default_out_root", None))
        if out_root is not None:
            return out_root / filename

    return Path.cwd() / filename


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------

def build_app_config() -> AppConfig:
    """
    Build the immutable application-level configuration from app.config.
    """

    return AppConfig(
        app_name=_cfg("APP_NAME", "gf-audit"),
        app_version=_cfg("APP_VERSION", "1.0.0"),
        default_scan_dir=_cfg("DEFAULT_SCAN_DIR", "lib/src/albanian"),
        default_scan_glob=_cfg("DEFAULT_SCAN_GLOB", "*.gf"),
        default_timeout_sec=int(_cfg("DEFAULT_TIMEOUT_SEC", 60)),
        default_max_files=int(_cfg("DEFAULT_MAX_FILES", 0)),
        default_include_regex=_cfg("DEFAULT_INCLUDE_REGEX", r"^[A-Z][A-Za-z0-9_]*\.gf$"),
        default_exclude_regex=_cfg(
            "DEFAULT_EXCLUDE_REGEX",
            r"( - Copie\.gf$|\.bak\.gf$|\.tmp\.gf$|\.disabled\.gf$|\s)",
        ),
        default_keep_ok_details=bool(_cfg("DEFAULT_KEEP_OK_DETAILS", False)),
        default_diff_previous=bool(_cfg("DEFAULT_DIFF_PREVIOUS", True)),
        default_skip_version_probe=bool(_cfg("DEFAULT_SKIP_VERSION_PROBE", False)),
        default_no_compile=bool(_cfg("DEFAULT_NO_COMPILE", False)),
        default_emit_cpu_stats=bool(_cfg("DEFAULT_EMIT_CPU_STATS", False)),
    )


def build_run_config(
    *,
    project_root: str | os.PathLike[str] | Path,
    rgl_root: str | os.PathLike[str] | Path,
    gf_exe: str | os.PathLike[str] | Path,
    out_root: str | os.PathLike[str] | Path | None = None,
    scan_dir: str | None = None,
    scan_glob: str | None = None,
    gf_path: str | None = None,
    timeout_sec: int | None = None,
    max_files: int | None = None,
    skip_version_probe: bool | None = None,
    no_compile: bool | None = None,
    emit_cpu_stats: bool | None = None,
    mode: str = _MODE_ALL,
    target_file: str | os.PathLike[str] | Path | None = None,
    include_regex: str | None = None,
    exclude_regex: str | None = None,
    keep_ok_details: bool | None = None,
    diff_previous: bool | None = None,
    app_config: AppConfig | None = None,
) -> RunConfig:
    """
    Build a validated run configuration shared by CLI and GUI entry points.
    """
    app_config = app_config or build_app_config()

    normalized_mode = _normalize_str(mode).lower() or _MODE_ALL
    if normalized_mode not in _ALLOWED_MODES:
        raise ValueError(
            f"Invalid mode '{mode}'. Allowed values: {sorted(_ALLOWED_MODES)}"
        )

    normalized_project_root = _normalize_path(project_root)
    normalized_rgl_root = _normalize_path(rgl_root)
    normalized_out_root = _normalize_path(out_root) or (Path.cwd() / "_gf_audit")
    normalized_gf_exe = _normalize_path(gf_exe)

    if normalized_project_root is None:
        raise ValueError("project_root is required.")
    if normalized_rgl_root is None:
        raise ValueError("rgl_root is required.")
    if normalized_gf_exe is None:
        raise ValueError("gf_exe is required.")

    normalized_target_file = _coerce_target_file(target_file)
    if normalized_mode == _MODE_FILE and not normalized_target_file:
        raise ValueError("target_file is required when mode='file'.")

    effective_scan_dir = _normalize_str(scan_dir) or app_config.default_scan_dir
    effective_scan_glob = _normalize_str(scan_glob) or app_config.default_scan_glob
    effective_timeout_sec = int(
        app_config.default_timeout_sec if timeout_sec is None else timeout_sec
    )
    effective_max_files = int(app_config.default_max_files if max_files is None else max_files)
    effective_skip_version_probe = bool(
        app_config.default_skip_version_probe
        if skip_version_probe is None
        else skip_version_probe
    )
    effective_no_compile = bool(
        app_config.default_no_compile if no_compile is None else no_compile
    )
    effective_emit_cpu_stats = bool(
        app_config.default_emit_cpu_stats if emit_cpu_stats is None else emit_cpu_stats
    )
    effective_include_regex = (
        _normalize_str(include_regex) or app_config.default_include_regex
    )
    effective_exclude_regex = (
        _normalize_str(exclude_regex) or app_config.default_exclude_regex
    )
    effective_keep_ok_details = bool(
        app_config.default_keep_ok_details
        if keep_ok_details is None
        else keep_ok_details
    )
    effective_diff_previous = bool(
        app_config.default_diff_previous if diff_previous is None else diff_previous
    )

    effective_gf_path = _normalize_optional_str(gf_path)
    if not effective_gf_path:
        effective_gf_path = _build_default_gf_path(
            scan_dir=effective_scan_dir,
            rgl_root=normalized_rgl_root,
        )

    return RunConfig(
        project_root=normalized_project_root,
        rgl_root=normalized_rgl_root,
        gf_exe=normalized_gf_exe,
        out_root=normalized_out_root,
        scan_dir=effective_scan_dir,
        scan_glob=effective_scan_glob,
        gf_path=effective_gf_path,
        timeout_sec=effective_timeout_sec,
        max_files=effective_max_files,
        skip_version_probe=effective_skip_version_probe,
        no_compile=effective_no_compile,
        emit_cpu_stats=effective_emit_cpu_stats,
        mode=normalized_mode,
        target_file=normalized_target_file,
        include_regex=effective_include_regex,
        exclude_regex=effective_exclude_regex,
        keep_ok_details=effective_keep_ok_details,
        diff_previous=effective_diff_previous,
    )


def build_run_paths(run_config: RunConfig) -> RunPaths:
    """
    Build and materialize the directory structure for a run.

    Layout:
        run_<id>/
          summary.json
          summary.md
          ai_brief.txt
          top_errors.txt
          details/
          raw/
            master.log
            ALL_SCAN_LOGS.TXT
            ALL_LOGS.TXT
            logs/compile/
            logs/scan/
            artifacts/gfo/
            artifacts/out/
    """
    run_dir_prefix = _cfg("RUN_DIR_PREFIX", "run_")

    master_log_filename = _cfg("MASTER_LOG_FILENAME", "master.log")
    all_scan_logs_filename = _cfg("ALL_SCAN_LOGS_FILENAME", "ALL_SCAN_LOGS.TXT")
    all_logs_filename = _cfg("ALL_LOGS_FILENAME", "ALL_LOGS.TXT")
    summary_json_filename = _cfg("SUMMARY_JSON_FILENAME", "summary.json")
    summary_md_filename = _cfg("SUMMARY_MD_FILENAME", "summary.md")
    ai_brief_filename = _cfg("AI_BRIEF_FILENAME", "ai_brief.txt")
    top_errors_filename = _cfg("TOP_ERRORS_FILENAME", "top_errors.txt")

    details_dirname = _cfg("DETAILS_DIRNAME", "details")
    raw_dirname = _cfg("RAW_DIRNAME", "raw")
    compile_logs_dirname = _cfg("COMPILE_LOGS_DIRNAME", "compile")
    scan_logs_dirname = _cfg("SCAN_LOGS_DIRNAME", "scan")
    artifacts_dirname = _cfg("ARTIFACTS_DIRNAME", "artifacts")
    gfo_dirname = _cfg("GFO_DIRNAME", "gfo")
    out_dirname = _cfg("OUT_DIRNAME", "out")

    run_id = _make_run_id()
    run_dir = _ensure_dir(Path(run_config.out_root) / f"{run_dir_prefix}{run_id}")

    details_dir = _ensure_dir(run_dir / details_dirname)
    raw_dir = _ensure_dir(run_dir / raw_dirname)

    logs_root = _ensure_dir(raw_dir / "logs")
    compile_logs_dir = _ensure_dir(logs_root / compile_logs_dirname)
    scan_logs_dir = _ensure_dir(logs_root / scan_logs_dirname)

    artifacts_dir = _ensure_dir(raw_dir / artifacts_dirname)
    gfo_dir = _ensure_dir(artifacts_dir / gfo_dirname)
    out_dir = _ensure_dir(artifacts_dir / out_dirname)

    master_log_path = raw_dir / master_log_filename
    all_scan_logs_path = raw_dir / all_scan_logs_filename
    all_logs_path = raw_dir / all_logs_filename
    summary_json_path = run_dir / summary_json_filename
    summary_md_path = run_dir / summary_md_filename
    ai_brief_path = run_dir / ai_brief_filename
    top_errors_path = run_dir / top_errors_filename

    # Touch critical aggregate files early so they exist even on partial runs.
    for bootstrap_file in (master_log_path, all_scan_logs_path, all_logs_path):
        if not bootstrap_file.exists():
            bootstrap_file.write_text("", encoding="utf-8")

    return RunPaths(
        run_id=run_id,
        run_dir=run_dir,
        master_log_path=master_log_path,
        all_scan_logs_path=all_scan_logs_path,
        all_logs_path=all_logs_path,
        summary_json_path=summary_json_path,
        summary_md_path=summary_md_path,
        ai_brief_path=ai_brief_path,
        top_errors_path=top_errors_path,
        details_dir=details_dir,
        raw_dir=raw_dir,
        compile_logs_dir=compile_logs_dir,
        scan_logs_dir=scan_logs_dir,
        artifacts_dir=artifacts_dir,
        gfo_dir=gfo_dir,
        out_dir=out_dir,
    )


# ---------------------------------------------------------------------------
# GUI state persistence
# ---------------------------------------------------------------------------

def load_app_state(
    state_path: str | os.PathLike[str] | Path | None = None,
    *,
    app_config: AppConfig | None = None,
) -> dict[str, Any]:
    """
    Load persisted GUI/application state.

    Only simple scalar/path fields are persisted. Runtime-only objects such as
    current_run_config and current_run_result are reset on load.
    """
    path = _get_state_path(state_path, app_config=app_config)
    payload = _read_json(path)

    state = _build_default_state()
    state.update(
        {
            "selected_mode": payload.get("selected_mode", state["selected_mode"]),
            "selected_target_file": payload.get("selected_target_file"),
            "selected_project_root": payload.get("selected_project_root"),
            "selected_rgl_root": payload.get("selected_rgl_root"),
            "selected_gf_exe": payload.get("selected_gf_exe"),
            "selected_out_root": payload.get("selected_out_root"),
            "is_running": False,
            "last_run_dir": payload.get("last_run_dir"),
            "last_summary_path": payload.get("last_summary_path"),
            "status_message": payload.get("status_message", ""),
            "current_run_config": None,
            "current_run_result": None,
        }
    )
    return state


def save_app_state(
    app_state: Mapping[str, Any],
    state_path: str | os.PathLike[str] | Path | None = None,
    *,
    app_config: AppConfig | None = None,
) -> Path:
    """
    Persist GUI/application state in JSON form.
    """
    path = _get_state_path(state_path, app_config=app_config)

    payload = {
        "selected_mode": app_state.get("selected_mode", _MODE_ALL),
        "selected_target_file": app_state.get("selected_target_file"),
        "selected_project_root": app_state.get("selected_project_root"),
        "selected_rgl_root": app_state.get("selected_rgl_root"),
        "selected_gf_exe": app_state.get("selected_gf_exe"),
        "selected_out_root": app_state.get("selected_out_root"),
        "is_running": False,
        "last_run_dir": app_state.get("last_run_dir"),
        "last_summary_path": app_state.get("last_summary_path"),
        "status_message": app_state.get("status_message", ""),
    }

    return _write_json_atomic(path, payload)


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------

def serialize_run_config(run_config: RunConfig) -> dict[str, Any]:
    data = _serialize_dataclass(run_config)
    for key, value in list(data.items()):
        if isinstance(value, Path):
            data[key] = str(value)
    return data


def serialize_run_paths(run_paths: RunPaths) -> dict[str, Any]:
    data = _serialize_dataclass(run_paths)
    for key, value in list(data.items()):
        if isinstance(value, Path):
            data[key] = str(value)
    return data


def build_run_metadata(run_config: RunConfig, run_paths: RunPaths) -> dict[str, Any]:
    """
    Small helper useful for early logging/bootstrap diagnostics.
    """
    return {
        "run_id": run_paths.run_id,
        "run_dir": _serialize_path(run_paths.run_dir),
        "started_at": _now_utc_iso(),
        "project_root": _serialize_path(run_config.project_root),
        "rgl_root": _serialize_path(run_config.rgl_root),
        "gf_exe": _serialize_path(run_config.gf_exe),
        "out_root": _serialize_path(run_config.out_root),
        "scan_dir": run_config.scan_dir,
        "scan_glob": run_config.scan_glob,
        "gf_path": run_config.gf_path,
        "timeout_sec": run_config.timeout_sec,
        "max_files": run_config.max_files,
        "skip_version_probe": run_config.skip_version_probe,
        "no_compile": run_config.no_compile,
        "emit_cpu_stats": run_config.emit_cpu_stats,
        "mode": run_config.mode,
        "target_file": run_config.target_file,
        "include_regex": run_config.include_regex,
        "exclude_regex": run_config.exclude_regex,
        "keep_ok_details": run_config.keep_ok_details,
        "diff_previous": run_config.diff_previous,
    }


__all__ = [
    "build_app_config",
    "build_run_config",
    "build_run_paths",
    "build_run_metadata",
    "load_app_state",
    "save_app_state",
    "serialize_run_config",
    "serialize_run_paths",
]

