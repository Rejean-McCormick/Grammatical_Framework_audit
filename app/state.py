from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from app.models import RunConfig, RunResult


_DEFAULT_SCAN_DIR = "lib/src/albanian"
_DEFAULT_SCAN_GLOB = "*.gf"
_DEFAULT_TIMEOUT_SEC = 60
_DEFAULT_MAX_FILES = 0
_DEFAULT_INCLUDE_REGEX = r"^[A-Z][A-Za-z0-9_]*\.gf$"
_DEFAULT_EXCLUDE_REGEX = r"( - Copie\.gf$|\.bak\.gf$|\.tmp\.gf$|\.disabled\.gf$|\s)"


@dataclass(slots=True)
class AppState:
    selected_mode: str = "all"
    selected_target_file: str = ""

    selected_project_root: Optional[Path] = None
    selected_rgl_root: Optional[Path] = None
    selected_gf_exe: Optional[Path] = None
    selected_out_root: Optional[Path] = None

    selected_scan_dir: str = _DEFAULT_SCAN_DIR
    selected_scan_glob: str = _DEFAULT_SCAN_GLOB
    selected_gf_path: str = ""
    selected_timeout_sec: int = _DEFAULT_TIMEOUT_SEC
    selected_max_files: int = _DEFAULT_MAX_FILES
    selected_include_regex: str = _DEFAULT_INCLUDE_REGEX
    selected_exclude_regex: str = _DEFAULT_EXCLUDE_REGEX

    selected_keep_ok_details: bool = False
    selected_diff_previous: bool = True
    selected_skip_version_probe: bool = False
    selected_no_compile: bool = False
    selected_emit_cpu_stats: bool = False

    is_running: bool = False
    last_run_dir: Optional[Path] = None
    last_summary_path: Optional[Path] = None
    status_message: str = ""

    current_run_config: Optional[RunConfig] = None
    current_run_result: Optional[RunResult] = None

    def reset_run_state(self) -> None:
        self.is_running = False
        self.last_run_dir = None
        self.last_summary_path = None
        self.status_message = ""
        self.current_run_config = None
        self.current_run_result = None

    def begin_run(self, run_config: RunConfig, status_message: str = "Running audit...") -> None:
        self.is_running = True
        self.status_message = status_message
        self.current_run_config = run_config
        self.current_run_result = None
        self.last_run_dir = None
        self.last_summary_path = None

    def finish_run(self, run_result: RunResult, status_message: str = "Audit completed.") -> None:
        self.is_running = False
        self.current_run_result = run_result
        self.last_run_dir = run_result.run_paths.run_dir
        self.last_summary_path = run_result.run_paths.summary_json_path
        self.status_message = status_message

    def fail_run(self, status_message: str) -> None:
        self.is_running = False
        self.status_message = status_message

    def apply_run_config_defaults(self, run_config: RunConfig) -> None:
        self.selected_mode = run_config.mode
        self.selected_target_file = run_config.target_file
        self.selected_project_root = run_config.project_root
        self.selected_rgl_root = run_config.rgl_root
        self.selected_gf_exe = run_config.gf_exe
        self.selected_out_root = run_config.out_root

        self.selected_scan_dir = run_config.scan_dir
        self.selected_scan_glob = run_config.scan_glob
        self.selected_gf_path = run_config.gf_path
        self.selected_timeout_sec = run_config.timeout_sec
        self.selected_max_files = run_config.max_files
        self.selected_include_regex = run_config.include_regex
        self.selected_exclude_regex = run_config.exclude_regex

        self.selected_keep_ok_details = run_config.keep_ok_details
        self.selected_diff_previous = run_config.diff_previous
        self.selected_skip_version_probe = run_config.skip_version_probe
        self.selected_no_compile = run_config.no_compile
        self.selected_emit_cpu_stats = run_config.emit_cpu_stats

    def to_dict(self) -> dict:
        return {
            "selected_mode": self.selected_mode,
            "selected_target_file": self.selected_target_file,
            "selected_project_root": str(self.selected_project_root) if self.selected_project_root else None,
            "selected_rgl_root": str(self.selected_rgl_root) if self.selected_rgl_root else None,
            "selected_gf_exe": str(self.selected_gf_exe) if self.selected_gf_exe else None,
            "selected_out_root": str(self.selected_out_root) if self.selected_out_root else None,
            "selected_scan_dir": self.selected_scan_dir,
            "selected_scan_glob": self.selected_scan_glob,
            "selected_gf_path": self.selected_gf_path,
            "selected_timeout_sec": self.selected_timeout_sec,
            "selected_max_files": self.selected_max_files,
            "selected_include_regex": self.selected_include_regex,
            "selected_exclude_regex": self.selected_exclude_regex,
            "selected_keep_ok_details": self.selected_keep_ok_details,
            "selected_diff_previous": self.selected_diff_previous,
            "selected_skip_version_probe": self.selected_skip_version_probe,
            "selected_no_compile": self.selected_no_compile,
            "selected_emit_cpu_stats": self.selected_emit_cpu_stats,
            "is_running": self.is_running,
            "last_run_dir": str(self.last_run_dir) if self.last_run_dir else None,
            "last_summary_path": str(self.last_summary_path) if self.last_summary_path else None,
            "status_message": self.status_message,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AppState":
        return cls(
            selected_mode=str(data.get("selected_mode") or "all"),
            selected_target_file=str(data.get("selected_target_file") or ""),
            selected_project_root=_optional_path(data.get("selected_project_root")),
            selected_rgl_root=_optional_path(data.get("selected_rgl_root")),
            selected_gf_exe=_optional_path(data.get("selected_gf_exe")),
            selected_out_root=_optional_path(data.get("selected_out_root")),
            selected_scan_dir=str(data.get("selected_scan_dir") or _DEFAULT_SCAN_DIR),
            selected_scan_glob=str(data.get("selected_scan_glob") or _DEFAULT_SCAN_GLOB),
            selected_gf_path=str(data.get("selected_gf_path") or ""),
            selected_timeout_sec=_coerce_int(data.get("selected_timeout_sec"), _DEFAULT_TIMEOUT_SEC, minimum=1),
            selected_max_files=_coerce_int(data.get("selected_max_files"), _DEFAULT_MAX_FILES, minimum=0),
            selected_include_regex=str(data.get("selected_include_regex") or _DEFAULT_INCLUDE_REGEX),
            selected_exclude_regex=str(data.get("selected_exclude_regex") or _DEFAULT_EXCLUDE_REGEX),
            selected_keep_ok_details=_coerce_bool(data.get("selected_keep_ok_details"), False),
            selected_diff_previous=_coerce_bool(data.get("selected_diff_previous"), True),
            selected_skip_version_probe=_coerce_bool(data.get("selected_skip_version_probe"), False),
            selected_no_compile=_coerce_bool(data.get("selected_no_compile"), False),
            selected_emit_cpu_stats=_coerce_bool(data.get("selected_emit_cpu_stats"), False),
            is_running=_coerce_bool(data.get("is_running"), False),
            last_run_dir=_optional_path(data.get("last_run_dir")),
            last_summary_path=_optional_path(data.get("last_summary_path")),
            status_message=str(data.get("status_message") or ""),
        )


def _optional_path(value: object) -> Optional[Path]:
    if value is None:
        return None
    text = str(value).strip()
    return Path(text) if text else None


def _coerce_bool(value: object, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on"}:
            return True
        if text in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _coerce_int(value: object, default: int, *, minimum: int | None = None) -> int:
    try:
        result = int(value) if value is not None else default
    except (TypeError, ValueError):
        result = default
    if minimum is not None and result < minimum:
        return minimum
    return result


app_state = AppState()