from __future__ import annotations

from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox


def pick_project_root(parent: Optional[tk.Misc] = None, initial_dir: Optional[Path] = None) -> Optional[Path]:
    return _pick_directory(
        title="Select GF project root",
        parent=parent,
        initial_dir=initial_dir,
    )


def pick_rgl_root(parent: Optional[tk.Misc] = None, initial_dir: Optional[Path] = None) -> Optional[Path]:
    return _pick_directory(
        title="Select RGL root",
        parent=parent,
        initial_dir=initial_dir,
    )


def pick_gf_exe(parent: Optional[tk.Misc] = None, initial_dir: Optional[Path] = None) -> Optional[Path]:
    file_path = filedialog.askopenfilename(
        parent=parent,
        title="Select gf executable",
        initialdir=_initial_dir_str(initial_dir),
        filetypes=[
            ("GF executable", "gf.exe"),
            ("Executables", "*.exe"),
            ("All files", "*.*"),
        ],
    )
    return _normalize_selected_path(file_path)


def pick_out_root(parent: Optional[tk.Misc] = None, initial_dir: Optional[Path] = None) -> Optional[Path]:
    return _pick_directory(
        title="Select output root",
        parent=parent,
        initial_dir=initial_dir,
        must_exist=False,
    )


def pick_target_file(
    parent: Optional[tk.Misc] = None,
    project_root: Optional[Path] = None,
    initial_dir: Optional[Path] = None,
) -> Optional[str]:
    effective_initial_dir = initial_dir or project_root
    file_path = filedialog.askopenfilename(
        parent=parent,
        title="Select target GF file",
        initialdir=_initial_dir_str(effective_initial_dir),
        filetypes=[
            ("GF files", "*.gf"),
            ("All files", "*.*"),
        ],
    )

    selected_path = _normalize_selected_path(file_path)
    if selected_path is None:
        return None

    if project_root is not None:
        try:
            return selected_path.resolve().relative_to(project_root.resolve()).as_posix()
        except ValueError:
            pass

    return str(selected_path)


def show_error_dialog(
    message: str,
    title: str = "Error",
    parent: Optional[tk.Misc] = None,
) -> None:
    messagebox.showerror(title=title, message=message, parent=parent)


def show_info_dialog(
    message: str,
    title: str = "Information",
    parent: Optional[tk.Misc] = None,
) -> None:
    messagebox.showinfo(title=title, message=message, parent=parent)


def confirm_run(
    parent: Optional[tk.Misc] = None,
    run_summary: str = "",
    title: str = "Confirm audit run",
) -> bool:
    message = "Start audit run?"
    if run_summary.strip():
        message = f"{message}\n\n{run_summary.strip()}"
    return bool(messagebox.askyesno(title=title, message=message, parent=parent))


def _pick_directory(
    title: str,
    parent: Optional[tk.Misc] = None,
    initial_dir: Optional[Path] = None,
    must_exist: bool = True,
) -> Optional[Path]:
    selected_dir = filedialog.askdirectory(
        parent=parent,
        title=title,
        initialdir=_initial_dir_str(initial_dir),
        mustexist=must_exist,
    )
    return _normalize_selected_path(selected_dir)


def _normalize_selected_path(value: str) -> Optional[Path]:
    text = str(value or "").strip()
    if not text:
        return None
    return Path(text).expanduser()


def _initial_dir_str(path: Optional[Path]) -> Optional[str]:
    if path is None:
        return None
    text = str(path).strip()
    return text or None