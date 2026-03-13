from __future__ import annotations

import traceback
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, QThread, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QCloseEvent, QDesktopServices
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..bootstrap import build_run_config
from ..models import AppConfig, RunConfig
from .validators import validate_run_config


class AuditWorker(QObject):
    started = Signal()
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, run_config: RunConfig) -> None:
        super().__init__()
        self.run_config = run_config

    @Slot()
    def run(self) -> None:
        try:
            from ..audit.audit_core import run_audit

            self.started.emit()
            run_result = run_audit(self.run_config)
            self.finished.emit(run_result)
        except Exception:
            self.failed.emit(traceback.format_exc())


class MainWindow(QMainWindow):
    def __init__(self, app_config: AppConfig, app_state: Any) -> None:
        super().__init__()
        self.app_config = app_config
        self.app_state = app_state

        self.worker_thread: QThread | None = None
        self.worker: AuditWorker | None = None

        self.setWindowTitle(f"{self.app_config.app_name} {self.app_config.app_version}")
        self.resize(1100, 760)

        self._build_ui()
        self._load_state_into_widgets()
        self._connect_signals()
        self._on_mode_changed(self.mode_var.currentText())
        self._update_status(self._state_get("status_message", "Ready.") or "Ready.")

    def _build_ui(self) -> None:
        root = QWidget(self)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(12, 12, 12, 12)
        root_layout.setSpacing(12)

        config_group = QGroupBox("Run Configuration", root)
        config_layout = QGridLayout(config_group)
        config_layout.setHorizontalSpacing(12)
        config_layout.setVerticalSpacing(8)

        paths_group = QGroupBox("Paths", config_group)
        paths_layout = QFormLayout(paths_group)
        paths_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.project_root_var = QLineEdit(paths_group)
        self.rgl_root_var = QLineEdit(paths_group)
        self.gf_exe_var = QLineEdit(paths_group)
        self.out_root_var = QLineEdit(paths_group)
        self.scan_dir_var = QLineEdit(paths_group)
        self.scan_glob_var = QLineEdit(paths_group)
        self.target_file_var = QLineEdit(paths_group)

        self.project_root_browse_button = QPushButton("Browse…", paths_group)
        self.rgl_root_browse_button = QPushButton("Browse…", paths_group)
        self.gf_exe_browse_button = QPushButton("Browse…", paths_group)
        self.out_root_browse_button = QPushButton("Browse…", paths_group)
        self.target_file_browse_button = QPushButton("Browse…", paths_group)

        paths_layout.addRow("Project root", self._with_button(self.project_root_var, self.project_root_browse_button))
        paths_layout.addRow("RGL root", self._with_button(self.rgl_root_var, self.rgl_root_browse_button))
        paths_layout.addRow("GF executable", self._with_button(self.gf_exe_var, self.gf_exe_browse_button))
        paths_layout.addRow("Output root", self._with_button(self.out_root_var, self.out_root_browse_button))
        paths_layout.addRow("Scan dir", self.scan_dir_var)
        paths_layout.addRow("Scan glob", self.scan_glob_var)
        paths_layout.addRow("Target file", self._with_button(self.target_file_var, self.target_file_browse_button))

        options_group = QGroupBox("Options", config_group)
        options_layout = QFormLayout(options_group)
        options_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.mode_var = QComboBox(options_group)
        self.mode_var.addItems(["all", "file"])

        self.timeout_sec_var = QSpinBox(options_group)
        self.timeout_sec_var.setRange(1, 3600)

        self.include_regex_var = QLineEdit(options_group)
        self.exclude_regex_var = QLineEdit(options_group)

        self.keep_ok_details_var = QCheckBox("Keep detail logs for OK files", options_group)
        self.diff_previous_var = QCheckBox("Diff against previous run", options_group)
        self.skip_version_probe_var = QCheckBox("Skip GF version probe", options_group)
        self.no_compile_var = QCheckBox("Scan only (no compile)", options_group)
        self.emit_cpu_stats_var = QCheckBox("Emit GF CPU stats", options_group)

        options_layout.addRow("Mode", self.mode_var)
        options_layout.addRow("Timeout (sec)", self.timeout_sec_var)
        options_layout.addRow("Include regex", self.include_regex_var)
        options_layout.addRow("Exclude regex", self.exclude_regex_var)
        options_layout.addRow("", self.keep_ok_details_var)
        options_layout.addRow("", self.diff_previous_var)
        options_layout.addRow("", self.skip_version_probe_var)
        options_layout.addRow("", self.no_compile_var)
        options_layout.addRow("", self.emit_cpu_stats_var)

        config_layout.addWidget(paths_group, 0, 0)
        config_layout.addWidget(options_group, 0, 1)

        actions_group = QGroupBox("Actions", root)
        actions_layout = QHBoxLayout(actions_group)

        self.run_button = QPushButton("Run Audit", actions_group)
        self.open_last_run_button = QPushButton("Open Last Run", actions_group)
        self.open_summary_button = QPushButton("Open Summary", actions_group)
        self.clear_log_button = QPushButton("Clear Log", actions_group)

        actions_layout.addWidget(self.run_button)
        actions_layout.addWidget(self.open_last_run_button)
        actions_layout.addWidget(self.open_summary_button)
        actions_layout.addStretch(1)
        actions_layout.addWidget(self.clear_log_button)

        output_group = QGroupBox("Output", root)
        output_layout = QVBoxLayout(output_group)

        self.status_message_var = QLabel(output_group)
        self.status_message_var.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.output_log = QPlainTextEdit(output_group)
        self.output_log.setReadOnly(True)

        output_layout.addWidget(self.status_message_var)
        output_layout.addWidget(self.output_log, 1)

        root_layout.addWidget(config_group)
        root_layout.addWidget(actions_group)
        root_layout.addWidget(output_group, 1)

        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self.mode_var.currentTextChanged.connect(self._on_mode_changed)

        self.project_root_browse_button.clicked.connect(self._browse_project_root)
        self.rgl_root_browse_button.clicked.connect(self._browse_rgl_root)
        self.gf_exe_browse_button.clicked.connect(self._browse_gf_exe)
        self.out_root_browse_button.clicked.connect(self._browse_out_root)
        self.target_file_browse_button.clicked.connect(self._browse_target_file)

        self.run_button.clicked.connect(self._on_run_clicked)
        self.open_last_run_button.clicked.connect(self._open_last_run)
        self.open_summary_button.clicked.connect(self._open_last_summary)
        self.clear_log_button.clicked.connect(self.output_log.clear)

        self.mode_var.currentTextChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.project_root_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.rgl_root_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.gf_exe_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.out_root_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.scan_dir_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.scan_glob_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.target_file_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.timeout_sec_var.valueChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.include_regex_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.exclude_regex_var.textChanged.connect(lambda *_: self._sync_state_from_widgets())
        self.keep_ok_details_var.toggled.connect(lambda *_: self._sync_state_from_widgets())
        self.diff_previous_var.toggled.connect(lambda *_: self._sync_state_from_widgets())
        self.skip_version_probe_var.toggled.connect(lambda *_: self._sync_state_from_widgets())
        self.no_compile_var.toggled.connect(lambda *_: self._sync_state_from_widgets())
        self.emit_cpu_stats_var.toggled.connect(lambda *_: self._sync_state_from_widgets())

    def _with_button(self, widget: QWidget, button: QPushButton) -> QWidget:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(widget, 1)
        layout.addWidget(button)
        return container

    def _load_state_into_widgets(self) -> None:
        self.project_root_var.setText(self._path_state_text("selected_project_root"))
        self.rgl_root_var.setText(self._path_state_text("selected_rgl_root"))
        self.gf_exe_var.setText(self._path_state_text("selected_gf_exe"))
        self.out_root_var.setText(self._path_state_text("selected_out_root"))

        self.scan_dir_var.setText(
            self._state_text("selected_scan_dir", getattr(self.app_config, "default_scan_dir", "lib/src/albanian"))
        )
        self.scan_glob_var.setText(
            self._state_text("selected_scan_glob", getattr(self.app_config, "default_scan_glob", "*.gf"))
        )

        self.mode_var.setCurrentText(self._state_text("selected_mode", "all") or "all")
        self.target_file_var.setText(self._state_text("selected_target_file", ""))

        self.timeout_sec_var.setValue(
            self._state_int("selected_timeout_sec", int(getattr(self.app_config, "default_timeout_sec", 60)))
        )
        self.include_regex_var.setText(
            self._state_text(
                "selected_include_regex",
                getattr(self.app_config, "default_include_regex", r"^[A-Z][A-Za-z0-9_]*\.gf$"),
            )
        )
        self.exclude_regex_var.setText(
            self._state_text(
                "selected_exclude_regex",
                getattr(
                    self.app_config,
                    "default_exclude_regex",
                    r"( - Copie\.gf$|\.bak\.gf$|\.tmp\.gf$|\.disabled\.gf$|\s)",
                ),
            )
        )
        self.keep_ok_details_var.setChecked(
            self._state_bool(
                "selected_keep_ok_details",
                bool(getattr(self.app_config, "default_keep_ok_details", False)),
            )
        )
        self.diff_previous_var.setChecked(
            self._state_bool(
                "selected_diff_previous",
                bool(getattr(self.app_config, "default_diff_previous", True)),
            )
        )
        self.skip_version_probe_var.setChecked(
            self._state_bool(
                "selected_skip_version_probe",
                bool(getattr(self.app_config, "default_skip_version_probe", False)),
            )
        )
        self.no_compile_var.setChecked(
            self._state_bool(
                "selected_no_compile",
                bool(getattr(self.app_config, "default_no_compile", False)),
            )
        )
        self.emit_cpu_stats_var.setChecked(
            self._state_bool(
                "selected_emit_cpu_stats",
                bool(getattr(self.app_config, "default_emit_cpu_stats", False)),
            )
        )

    def _state_get(self, key: str, default: Any = None) -> Any:
        if isinstance(self.app_state, dict):
            return self.app_state.get(key, default)
        return getattr(self.app_state, key, default)

    def _state_set(self, key: str, value: Any) -> None:
        if isinstance(self.app_state, dict):
            self.app_state[key] = value
            return
        setattr(self.app_state, key, value)

    def _state_text(self, key: str, default: str = "") -> str:
        value = self._state_get(key, default)
        if value is None:
            return default
        return str(value)

    def _state_int(self, key: str, default: int) -> int:
        value = self._state_get(key, default)
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    def _state_bool(self, key: str, default: bool) -> bool:
        value = self._state_get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on"}:
                return True
            if normalized in {"0", "false", "no", "off"}:
                return False
        return bool(value)

    def _path_state_text(self, key: str) -> str:
        value = self._state_get(key, None)
        return str(value) if value else ""

    def _build_run_summary(self, run_config: RunConfig) -> str:
        lines = [
            f"Mode: {run_config.mode}",
            f"Project root: {run_config.project_root}",
            f"RGL root: {run_config.rgl_root}",
            f"GF executable: {run_config.gf_exe}",
            f"Output root: {run_config.out_root}",
            f"Scan dir: {run_config.scan_dir}",
            f"Scan glob: {run_config.scan_glob}",
            f"Timeout: {run_config.timeout_sec}s",
        ]
        if run_config.mode == "file":
            lines.append(f"Target file: {run_config.target_file}")
        if run_config.no_compile:
            lines.append("Compile: disabled")
        return "\n".join(lines)

    def _resolve_initial_dir(self, raw_text: str, fallback: Path | None = None) -> str:
        text = (raw_text or "").strip()
        if text:
            candidate = Path(text).expanduser()
            if candidate.is_file():
                return str(candidate.parent)
            return str(candidate)
        if fallback is not None:
            return str(fallback)
        return str(Path.home())

    def _choose_directory(self, title: str, current_text: str, fallback: Path | None = None) -> str:
        start_dir = self._resolve_initial_dir(current_text, fallback=fallback)
        return QFileDialog.getExistingDirectory(self, title, start_dir)

    def _choose_file(self, title: str, current_text: str, file_filter: str, fallback: Path | None = None) -> str:
        start_dir = self._resolve_initial_dir(current_text, fallback=fallback)
        selected_file, _ = QFileDialog.getOpenFileName(self, title, start_dir, file_filter)
        return selected_file

    def _show_error(self, title: str, message: str, details: str = "") -> None:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Critical)
        box.setWindowTitle(title)
        box.setText(message)
        if details.strip():
            box.setDetailedText(details)
        box.exec()

    def _show_info(self, title: str, message: str) -> None:
        QMessageBox.information(self, title, message)

    def _confirm_run(self, run_summary: str) -> bool:
        message = "Start audit run?"
        if run_summary.strip():
            message = f"{message}\n\n{run_summary.strip()}"
        result = QMessageBox.question(
            self,
            "Confirm audit run",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return result == QMessageBox.StandardButton.Yes

    @Slot(str)
    def _on_mode_changed(self, mode: str) -> None:
        is_file_mode = mode == "file"
        self.target_file_var.setEnabled(is_file_mode and not self._state_get("is_running", False))
        self.target_file_browse_button.setEnabled(is_file_mode and not self._state_get("is_running", False))
        self._state_set("selected_mode", mode)

    @Slot()
    def _browse_project_root(self) -> None:
        current = self.project_root_var.text().strip()
        value = self._choose_directory("Select project root", current)
        if value:
            self.project_root_var.setText(value)
            self._state_set("selected_project_root", Path(value))

    @Slot()
    def _browse_rgl_root(self) -> None:
        current = self.rgl_root_var.text().strip()
        value = self._choose_directory("Select RGL root", current)
        if value:
            self.rgl_root_var.setText(value)
            self._state_set("selected_rgl_root", Path(value))

    @Slot()
    def _browse_gf_exe(self) -> None:
        current = self.gf_exe_var.text().strip()
        value = self._choose_file(
            "Select GF executable",
            current,
            "Executables (*.exe);;All files (*)",
        )
        if value:
            self.gf_exe_var.setText(value)
            self._state_set("selected_gf_exe", Path(value))

    @Slot()
    def _browse_out_root(self) -> None:
        current = self.out_root_var.text().strip()
        value = self._choose_directory("Select output root", current)
        if value:
            self.out_root_var.setText(value)
            self._state_set("selected_out_root", Path(value))

    @Slot()
    def _browse_target_file(self) -> None:
        project_root_text = self.project_root_var.text().strip()
        fallback = Path(project_root_text) if project_root_text else None
        current = self.target_file_var.text().strip()
        value = self._choose_file(
            "Select target GF file",
            current,
            "GF files (*.gf);;All files (*)",
            fallback=fallback,
        )
        if value:
            self.target_file_var.setText(value)
            self._state_set("selected_target_file", value)

    def _collect_run_config(self) -> RunConfig:
        self._sync_state_from_widgets()

        return build_run_config(
            project_root=Path(self.project_root_var.text().strip()),
            rgl_root=Path(self.rgl_root_var.text().strip()),
            gf_exe=Path(self.gf_exe_var.text().strip()),
            out_root=Path(self.out_root_var.text().strip()),
            scan_dir=self.scan_dir_var.text().strip(),
            scan_glob=self.scan_glob_var.text().strip(),
            gf_path="",
            timeout_sec=int(self.timeout_sec_var.value()),
            max_files=int(getattr(self.app_config, "default_max_files", 0)),
            skip_version_probe=bool(self.skip_version_probe_var.isChecked()),
            no_compile=bool(self.no_compile_var.isChecked()),
            emit_cpu_stats=bool(self.emit_cpu_stats_var.isChecked()),
            mode=self.mode_var.currentText().strip(),
            target_file=self.target_file_var.text().strip(),
            include_regex=self.include_regex_var.text().strip(),
            exclude_regex=self.exclude_regex_var.text().strip(),
            keep_ok_details=bool(self.keep_ok_details_var.isChecked()),
            diff_previous=bool(self.diff_previous_var.isChecked()),
            app_config=self.app_config,
        )

    def _sync_state_from_widgets(self) -> None:
        self._state_set("selected_mode", self.mode_var.currentText().strip())
        self._state_set("selected_target_file", self.target_file_var.text().strip())
        self._state_set(
            "selected_project_root",
            Path(self.project_root_var.text().strip()) if self.project_root_var.text().strip() else None,
        )
        self._state_set(
            "selected_rgl_root",
            Path(self.rgl_root_var.text().strip()) if self.rgl_root_var.text().strip() else None,
        )
        self._state_set(
            "selected_gf_exe",
            Path(self.gf_exe_var.text().strip()) if self.gf_exe_var.text().strip() else None,
        )
        self._state_set(
            "selected_out_root",
            Path(self.out_root_var.text().strip()) if self.out_root_var.text().strip() else None,
        )

        self._state_set("selected_scan_dir", self.scan_dir_var.text().strip())
        self._state_set("selected_scan_glob", self.scan_glob_var.text().strip())
        self._state_set("selected_timeout_sec", int(self.timeout_sec_var.value()))
        self._state_set("selected_include_regex", self.include_regex_var.text().strip())
        self._state_set("selected_exclude_regex", self.exclude_regex_var.text().strip())
        self._state_set("selected_keep_ok_details", bool(self.keep_ok_details_var.isChecked()))
        self._state_set("selected_diff_previous", bool(self.diff_previous_var.isChecked()))
        self._state_set("selected_skip_version_probe", bool(self.skip_version_probe_var.isChecked()))
        self._state_set("selected_no_compile", bool(self.no_compile_var.isChecked()))
        self._state_set("selected_emit_cpu_stats", bool(self.emit_cpu_stats_var.isChecked()))

    def _set_running_ui(self, is_running: bool) -> None:
        self.run_button.setEnabled(not is_running)
        self.project_root_browse_button.setEnabled(not is_running)
        self.rgl_root_browse_button.setEnabled(not is_running)
        self.gf_exe_browse_button.setEnabled(not is_running)
        self.out_root_browse_button.setEnabled(not is_running)
        self.target_file_browse_button.setEnabled(not is_running and self.mode_var.currentText() == "file")
        self.mode_var.setEnabled(not is_running)
        self.project_root_var.setEnabled(not is_running)
        self.rgl_root_var.setEnabled(not is_running)
        self.gf_exe_var.setEnabled(not is_running)
        self.out_root_var.setEnabled(not is_running)
        self.scan_dir_var.setEnabled(not is_running)
        self.scan_glob_var.setEnabled(not is_running)
        self.target_file_var.setEnabled(not is_running and self.mode_var.currentText() == "file")
        self.timeout_sec_var.setEnabled(not is_running)
        self.include_regex_var.setEnabled(not is_running)
        self.exclude_regex_var.setEnabled(not is_running)
        self.keep_ok_details_var.setEnabled(not is_running)
        self.diff_previous_var.setEnabled(not is_running)
        self.skip_version_probe_var.setEnabled(not is_running)
        self.no_compile_var.setEnabled(not is_running)
        self.emit_cpu_stats_var.setEnabled(not is_running)
        self._state_set("is_running", is_running)

    def _append_log(self, message: str) -> None:
        self.output_log.appendPlainText(message)

    def _update_status(self, message: str) -> None:
        self.status_message_var.setText(message)
        self._state_set("status_message", message)

    @Slot()
    def _on_run_clicked(self) -> None:
        try:
            run_config = self._collect_run_config()
            validation_errors = validate_run_config(run_config)
        except Exception as exc:
            self._show_error("Invalid configuration", str(exc))
            return

        if validation_errors:
            self._show_error("Validation failed", "\n".join(validation_errors))
            return

        run_summary = self._build_run_summary(run_config)
        if not self._confirm_run(run_summary):
            return

        self._start_audit(run_config)

    def _start_audit(self, run_config: RunConfig) -> None:
        self._set_running_ui(True)
        self._update_status("Running audit…")
        self._append_log("Starting audit run.")

        if hasattr(self.app_state, "begin_run"):
            self.app_state.begin_run(run_config, status_message="Running audit…")
        else:
            self._state_set("current_run_config", run_config)
            self._state_set("current_run_result", None)
            self._state_set("last_run_dir", None)
            self._state_set("last_summary_path", None)

        self.worker_thread = QThread(self)
        self.worker = AuditWorker(run_config)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.started.connect(lambda: self._append_log("Audit worker started."))
        self.worker.finished.connect(self._on_audit_finished)
        self.worker.failed.connect(self._on_audit_failed)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.failed.connect(self.worker_thread.quit)
        self.worker_thread.finished.connect(self._cleanup_worker)

        self.worker_thread.start()

    @Slot(object)
    def _on_audit_finished(self, run_result: Any) -> None:
        if hasattr(self.app_state, "finish_run"):
            self.app_state.finish_run(run_result, status_message="Audit completed.")
        else:
            self._state_set("current_run_result", run_result)
            run_paths = getattr(run_result, "run_paths", None)
            last_run_dir = str(getattr(run_paths, "run_dir", "")) if run_paths else ""
            last_summary_path = str(getattr(run_paths, "summary_json_path", "")) if run_paths else ""
            self._state_set("last_run_dir", last_run_dir)
            self._state_set("last_summary_path", last_summary_path)

        self._set_running_ui(False)
        self._update_status("Audit completed.")
        self._append_log("Audit completed successfully.")

        files_seen = getattr(run_result, "files_seen", "?")
        fail_count = getattr(run_result, "fail_count", "?")
        ok_count = getattr(run_result, "ok_count", "?")
        self._append_log(f"Files seen: {files_seen}")
        self._append_log(f"OK: {ok_count} | FAIL: {fail_count}")

        self._show_info(
            "Run completed",
            f"Audit completed.\n\nFiles seen: {files_seen}\nOK: {ok_count}\nFAIL: {fail_count}",
        )

    @Slot(str)
    def _on_audit_failed(self, error_text: str) -> None:
        if hasattr(self.app_state, "fail_run"):
            self.app_state.fail_run("Audit failed.")
        else:
            self._state_set("is_running", False)

        self._set_running_ui(False)
        self._update_status("Audit failed.")
        self._append_log("Audit failed.")
        self._append_log(error_text)
        self._show_error("Audit failed", "The audit run failed.", details=error_text)

    @Slot()
    def _cleanup_worker(self) -> None:
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

        if self.worker_thread is not None:
            self.worker_thread.deleteLater()
            self.worker_thread = None

    @Slot()
    def _open_last_run(self) -> None:
        last_run_dir = self._state_get("last_run_dir", "")
        if not last_run_dir:
            QMessageBox.information(self, "No run directory", "No run directory is available yet.")
            return

        path = Path(last_run_dir)
        if not path.exists():
            self._show_error("Missing directory", f"Run directory not found:\n{path}")
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot()
    def _open_last_summary(self) -> None:
        last_summary_path = self._state_get("last_summary_path", "")
        if not last_summary_path:
            QMessageBox.information(self, "No summary", "No summary file is available yet.")
            return

        path = Path(last_summary_path)
        if not path.exists():
            self._show_error("Missing file", f"Summary file not found:\n{path}")
            return

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    def closeEvent(self, event: QCloseEvent) -> None:
        self._sync_state_from_widgets()
        super().closeEvent(event)