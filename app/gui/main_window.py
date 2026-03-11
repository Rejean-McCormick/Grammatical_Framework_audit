from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import traceback

from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
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
from .dialogs import (
    confirm_run,
    pick_gf_exe,
    pick_out_root,
    pick_project_root,
    pick_rgl_root,
    pick_target_file,
    show_error_dialog,
    show_info_dialog,
)
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

        self.worker_thread: Optional[QThread] = None
        self.worker: Optional[AuditWorker] = None

        self.setWindowTitle(f"{self.app_config.app_name} {self.app_config.app_version}")
        self.resize(1100, 760)

        self._build_ui()
        self._load_state_into_widgets()
        self._connect_signals()
        self._on_mode_changed(self.mode_var.currentText())
        self._update_status("Ready.")

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
        paths_layout.setLabelAlignment(Qt.AlignRight)

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
        options_layout.setLabelAlignment(Qt.AlignRight)

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
        self.status_message_var.setTextInteractionFlags(Qt.TextSelectableByMouse)

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

    def _with_button(self, widget: QWidget, button: QPushButton) -> QWidget:
        container = QWidget(self)
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(widget, 1)
        layout.addWidget(button)
        return container

    def _load_state_into_widgets(self) -> None:
        self.project_root_var.setText(
            self._state_get("selected_project_root", "")
            or ""
        )
        self.rgl_root_var.setText(
            self._state_get("selected_rgl_root", "")
            or ""
        )
        self.gf_exe_var.setText(
            self._state_get("selected_gf_exe", "")
            or ""
        )
        self.out_root_var.setText(
            self._state_get("selected_out_root", "")
            or ""
        )

        self.scan_dir_var.setText(getattr(self.app_config, "default_scan_dir", "lib/src/albanian"))
        self.scan_glob_var.setText(getattr(self.app_config, "default_scan_glob", "*.gf"))

        self.mode_var.setCurrentText(self._state_get("selected_mode", "all") or "all")
        self.target_file_var.setText(self._state_get("selected_target_file", "") or "")
        self.timeout_sec_var.setValue(int(getattr(self.app_config, "default_timeout_sec", 60)))
        self.include_regex_var.setText(getattr(self.app_config, "default_include_regex", "^[A-Z][A-Za-z0-9_]*\\.gf$"))
        self.exclude_regex_var.setText(getattr(self.app_config, "default_exclude_regex", "( - Copie\\.gf$|\\.bak\\.gf$|\\.tmp\\.gf$|\\.disabled\\.gf$|\\s)"))
        self.keep_ok_details_var.setChecked(bool(getattr(self.app_config, "default_keep_ok_details", False)))
        self.diff_previous_var.setChecked(bool(getattr(self.app_config, "default_diff_previous", True)))
        self.skip_version_probe_var.setChecked(bool(getattr(self.app_config, "default_skip_version_probe", False)))
        self.no_compile_var.setChecked(bool(getattr(self.app_config, "default_no_compile", False)))
        self.emit_cpu_stats_var.setChecked(bool(getattr(self.app_config, "default_emit_cpu_stats", False)))

    def _state_get(self, key: str, default: Any = None) -> Any:
        if isinstance(self.app_state, dict):
            return self.app_state.get(key, default)
        return getattr(self.app_state, key, default)

    def _state_set(self, key: str, value: Any) -> None:
        if isinstance(self.app_state, dict):
            self.app_state[key] = value
        else:
            setattr(self.app_state, key, value)

    @Slot(str)
    def _on_mode_changed(self, mode: str) -> None:
        is_file_mode = mode == "file"
        self.target_file_var.setEnabled(is_file_mode)
        self.target_file_browse_button.setEnabled(is_file_mode)
        self._state_set("selected_mode", mode)

    @Slot()
    def _browse_project_root(self) -> None:
        value = pick_project_root(parent=self, start_dir=self.project_root_var.text().strip() or None)
        if value:
            self.project_root_var.setText(str(value))
            self._state_set("selected_project_root", str(value))

    @Slot()
    def _browse_rgl_root(self) -> None:
        value = pick_rgl_root(parent=self, start_dir=self.rgl_root_var.text().strip() or None)
        if value:
            self.rgl_root_var.setText(str(value))
            self._state_set("selected_rgl_root", str(value))

    @Slot()
    def _browse_gf_exe(self) -> None:
        value = pick_gf_exe(parent=self, start_dir=self.gf_exe_var.text().strip() or None)
        if value:
            self.gf_exe_var.setText(str(value))
            self._state_set("selected_gf_exe", str(value))

    @Slot()
    def _browse_out_root(self) -> None:
        value = pick_out_root(parent=self, start_dir=self.out_root_var.text().strip() or None)
        if value:
            self.out_root_var.setText(str(value))
            self._state_set("selected_out_root", str(value))

    @Slot()
    def _browse_target_file(self) -> None:
        start_dir = self.project_root_var.text().strip() or None
        value = pick_target_file(parent=self, start_dir=start_dir)
        if value:
            self.target_file_var.setText(str(value))
            self._state_set("selected_target_file", str(value))

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
        )

    def _sync_state_from_widgets(self) -> None:
        self._state_set("selected_mode", self.mode_var.currentText().strip())
        self._state_set("selected_target_file", self.target_file_var.text().strip())
        self._state_set("selected_project_root", self.project_root_var.text().strip())
        self._state_set("selected_rgl_root", self.rgl_root_var.text().strip())
        self._state_set("selected_gf_exe", self.gf_exe_var.text().strip())
        self._state_set("selected_out_root", self.out_root_var.text().strip())

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
            show_error_dialog(self, "Invalid configuration", str(exc))
            return

        if validation_errors:
            show_error_dialog(self, "Validation failed", "\n".join(validation_errors))
            return

        if not confirm_run(self, run_config):
            return

        self._start_audit(run_config)

    def _start_audit(self, run_config: RunConfig) -> None:
        self._set_running_ui(True)
        self._update_status("Running audit…")
        self._append_log("Starting audit run.")
        self._state_set("current_run_config", run_config)

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

        show_info_dialog(
            self,
            "Run completed",
            f"Audit completed.\n\nFiles seen: {files_seen}\nOK: {ok_count}\nFAIL: {fail_count}",
        )

    @Slot(str)
    def _on_audit_failed(self, error_text: str) -> None:
        self._set_running_ui(False)
        self._update_status("Audit failed.")
        self._append_log("Audit failed.")
        self._append_log(error_text)
        show_error_dialog(self, "Audit failed", error_text)

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
            show_error_dialog(self, "Missing directory", f"Run directory not found:\n{path}")
            return

        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    @Slot()
    def _open_last_summary(self) -> None:
        last_summary_path = self._state_get("last_summary_path", "")
        if not last_summary_path:
            QMessageBox.information(self, "No summary", "No summary file is available yet.")
            return

        path = Path(last_summary_path)
        if not path.exists():
            show_error_dialog(self, "Missing file", f"Summary file not found:\n{path}")
            return

        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl

        QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

