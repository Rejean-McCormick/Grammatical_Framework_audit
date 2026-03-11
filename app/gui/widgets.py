from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFontDatabase
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QPlainTextEdit,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


@dataclass(slots=True)
class PathDialogOptions:
    caption: str
    file_filter: str = "All Files (*)"
    initial_path: str = ""


class SectionBox(QGroupBox):
    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)
        self.setObjectName("section_box")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)


class StatusBanner(QFrame):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setObjectName("status_banner")

        self._label = QLabel("Ready.", self)
        self._label.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.addWidget(self._label)

        self.set_state("info", "Ready.")

    def set_state(self, state: str, message: str) -> None:
        state_key = (state or "info").strip().lower()

        palette = {
            "info": ("#D6EAF8", "#1B4F72"),
            "success": ("#D5F5E3", "#145A32"),
            "warning": ("#FCF3CF", "#7D6608"),
            "error": ("#F5B7B1", "#7B241C"),
        }
        bg, fg = palette.get(state_key, palette["info"])
        self.setStyleSheet(
            f"""
            QFrame#status_banner {{
                background-color: {bg};
                border: 1px solid {fg};
                border-radius: 4px;
            }}
            QLabel {{
                color: {fg};
                font-weight: 600;
            }}
            """
        )
        self._label.setText(message or "")

    def text(self) -> str:
        return self._label.text()


class LogViewer(QPlainTextEdit):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        self.setPlaceholderText("Logs will appear here...")

        fixed_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.setFont(fixed_font)

    def append_line(self, text: str) -> None:
        if not text:
            return

        cursor = self.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)
        if self.toPlainText():
            cursor.insertText("\n")
        cursor.insertText(text)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def append_lines(self, lines: list[str]) -> None:
        for line in lines:
            self.append_line(line)

    def replace_text(self, text: str) -> None:
        self.setPlainText(text or "")


class PathSelector(QWidget):
    path_changed = Signal(str)
    browse_clicked = Signal()

    def __init__(
        self,
        label_text: str,
        button_text: str = "Browse...",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        self._label = QLabel(label_text, self)
        self._label.setMinimumWidth(110)

        self._line_edit = QLineEdit(self)
        self._line_edit.setClearButtonEnabled(True)
        self._line_edit.textChanged.connect(self.path_changed.emit)

        self._button = QPushButton(button_text, self)
        self._button.clicked.connect(self._on_browse_clicked)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._label)
        layout.addWidget(self._line_edit, 1)
        layout.addWidget(self._button)

    def _on_browse_clicked(self) -> None:
        self.browse_clicked.emit()

    def set_label_width(self, width: int) -> None:
        self._label.setMinimumWidth(max(0, width))

    def set_placeholder_text(self, text: str) -> None:
        self._line_edit.setPlaceholderText(text)

    def set_button_text(self, text: str) -> None:
        self._button.setText(text)

    def set_path(self, value: str | Path) -> None:
        self._line_edit.setText(str(value) if value is not None else "")

    def path(self) -> str:
        return self._line_edit.text().strip()

    def line_edit(self) -> QLineEdit:
        return self._line_edit

    def button(self) -> QPushButton:
        return self._button

    def label(self) -> QLabel:
        return self._label


class DirectorySelector(PathSelector):
    def __init__(
        self,
        label_text: str,
        dialog_options: Optional[PathDialogOptions] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(label_text=label_text, button_text="Browse...", parent=parent)
        self._dialog_options = dialog_options or PathDialogOptions(caption=label_text)
        self.browse_clicked.connect(self._browse_for_directory)

    def _browse_for_directory(self) -> None:
        start_dir = self.path() or self._dialog_options.initial_path or str(Path.home())
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            self._dialog_options.caption,
            start_dir,
        )
        if selected_dir:
            self.set_path(selected_dir)


class FileSelector(PathSelector):
    def __init__(
        self,
        label_text: str,
        dialog_options: Optional[PathDialogOptions] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(label_text=label_text, button_text="Browse...", parent=parent)
        self._dialog_options = dialog_options or PathDialogOptions(caption=label_text)
        self.browse_clicked.connect(self._browse_for_file)

    def _browse_for_file(self) -> None:
        start_dir = self.path() or self._dialog_options.initial_path or str(Path.home())
        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            self._dialog_options.caption,
            start_dir,
            self._dialog_options.file_filter,
        )
        if selected_file:
            self.set_path(selected_file)


class OutputPathSelector(PathSelector):
    """
    Lets the user choose either a directory or type a custom path.
    Useful for out_root.
    """

    def __init__(
        self,
        label_text: str,
        dialog_options: Optional[PathDialogOptions] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(label_text=label_text, button_text="Browse...", parent=parent)
        self._dialog_options = dialog_options or PathDialogOptions(caption=label_text)
        self.browse_clicked.connect(self._browse_for_directory)

    def _browse_for_directory(self) -> None:
        start_dir = self.path() or self._dialog_options.initial_path or str(Path.home())
        selected_dir = QFileDialog.getExistingDirectory(
            self,
            self._dialog_options.caption,
            start_dir,
        )
        if selected_dir:
            self.set_path(selected_dir)


def make_info_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return label


def make_spacer() -> QWidget:
    spacer = QWidget()
    spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    return spacer


def show_exception_message(
    parent: Optional[QWidget],
    title: str,
    message: str,
    details: str = "",
) -> None:
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Critical)
    box.setWindowTitle(title)
    box.setText(message)
    if details:
        box.setDetailedText(details)
    box.exec()


def show_info_message(parent: Optional[QWidget], title: str, message: str) -> None:
    QMessageBox.information(parent, title, message)


def show_warning_message(parent: Optional[QWidget], title: str, message: str) -> None:
    QMessageBox.warning(parent, title, message)


def show_confirmation_message(
    parent: Optional[QWidget],
    title: str,
    message: str,
) -> bool:
    result = QMessageBox.question(
        parent,
        title,
        message,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    return result == QMessageBox.StandardButton.Yes

