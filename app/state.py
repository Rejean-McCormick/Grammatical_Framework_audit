from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from app.models import RunConfig, RunResult


@dataclass(slots=True)
class AppState:
    selected_mode: str = "all"
    selected_target_file: str = ""
    selected_project_root: Optional[Path] = None
    selected_rgl_root: Optional[Path] = None
    selected_gf_exe: Optional[Path] = None
    selected_out_root: Optional[Path] = None

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

    def to_dict(self) -> dict:
        return {
            "selected_mode": self.selected_mode,
            "selected_target_file": self.selected_target_file,
            "selected_project_root": str(self.selected_project_root) if self.selected_project_root else None,
            "selected_rgl_root": str(self.selected_rgl_root) if self.selected_rgl_root else None,
            "selected_gf_exe": str(self.selected_gf_exe) if self.selected_gf_exe else None,
            "selected_out_root": str(self.selected_out_root) if self.selected_out_root else None,
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
            is_running=bool(data.get("is_running", False)),
            last_run_dir=_optional_path(data.get("last_run_dir")),
            last_summary_path=_optional_path(data.get("last_summary_path")),
            status_message=str(data.get("status_message") or ""),
        )


def _optional_path(value: object) -> Optional[Path]:
    if value is None:
        return None
    text = str(value).strip()
    return Path(text) if text else None


app_state = AppState()