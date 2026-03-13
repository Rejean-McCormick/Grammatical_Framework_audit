from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget


def pick_project_root(
    parent: QWidget | None = None,
    initial_dir: Path | None = None,
) -> Path | None:
    return _pick_directory(
        title="Select GF project root",
        parent=parent,
        initial_dir=initial_dir,
    )


def pick_rgl_root(
    parent: QWidget | None = None,
    initial_dir: Path | None = None,
) -> Path | None:
    return _pick_directory(
        title="Select RGL root",
        parent=parent,
        initial_dir=initial_dir,
    )


def pick_gf_exe(
    parent: QWidget | None = None,
    initial_dir: Path | None = None,
) -> Path | None:
    file_path, _ = QFileDialog.getOpenFileName(
        parent,
        "Select gf executable",
        _initial_dir_str(initial_dir),
        "GF executable (gf.exe);;Executables (*.exe);;All files (*.*)",
    )
    return _normalize_selected_path(file_path)


def pick_out_root(
    parent: QWidget | None = None,
    initial_dir: Path | None = None,
) -> Path | None:
    return _pick_directory(
        title="Select output root",
        parent=parent,
        initial_dir=initial_dir,
    )


def pick_target_file(
    parent: QWidget | None = None,
    project_root: Path | None = None,
    initial_dir: Path | None = None,
) -> str | None:
    effective_initial_dir = initial_dir or project_root

    file_path, _ = QFileDialog.getOpenFileName(
        parent,
        "Select target GF file",
        _initial_dir_str(effective_initial_dir),
        "GF files (*.gf);;All files (*.*)",
    )

    selected_path = _normalize_selected_path(file_path)
    if selected_path is None:
        return None

    if project_root is not None:
        try:
            return selected_path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            return str(selected_path)

    return str(selected_path)


def show_error_dialog(
    parent: QWidget | None,
    title: str,
    message: str,
) -> None:
    QMessageBox.critical(parent, title, message)


def show_info_dialog(
    parent: QWidget | None,
    title: str,
    message: str,
) -> None:
    QMessageBox.information(parent, title, message)


def confirm_run(
    parent: QWidget | None = None,
    run_summary: str = "",
    title: str = "Confirm audit run",
) -> bool:
    message = "Start audit run?"
    if run_summary.strip():
        message = f"{message}\n\n{run_summary.strip()}"

    result = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return result == QMessageBox.StandardButton.Yes


def _pick_directory(
    title: str,
    parent: QWidget | None = None,
    initial_dir: Path | None = None,
) -> Path | None:
    selected_dir = QFileDialog.getExistingDirectory(
        parent,
        title,
        _initial_dir_str(initial_dir),
        QFileDialog.Option.ShowDirsOnly,
    )
    return _normalize_selected_path(selected_dir)


def _normalize_selected_path(value: str) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def _initial_dir_str(path: Path | None) -> str:
    if path is None:
        return ""
    text = str(path).strip()
    return text or ""