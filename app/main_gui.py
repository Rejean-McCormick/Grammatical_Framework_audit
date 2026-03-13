from __future__ import annotations

import logging
import sys
import traceback
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QApplication, QMessageBox


if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bootstrap import build_app_config, load_app_state, save_app_state
from app.gui.main_window import MainWindow
from app.state import app_state


logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _merge_app_state(target: Any, source: Any) -> Any:
    if source is None:
        return target

    if target is source:
        return target

    if isinstance(target, dict) and isinstance(source, dict):
        target.clear()
        target.update(source)
        return target

    if hasattr(target, "__dict__") and hasattr(source, "__dict__"):
        target.__dict__.clear()
        target.__dict__.update(source.__dict__)
        return target

    return source


def _show_fatal_error(title: str, message: str, details: str = "") -> None:
    app = QApplication.instance()
    if app is None:
        return

    dialog = QMessageBox()
    dialog.setIcon(QMessageBox.Icon.Critical)
    dialog.setWindowTitle(title)
    dialog.setText(message)
    if details:
        dialog.setDetailedText(details)
    dialog.exec()


def _install_excepthook() -> None:
    def _handle_exception(
        exc_type: type[BaseException],
        exc_value: BaseException,
        exc_tb: Any,
    ) -> None:
        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        logger.exception(
            "Unhandled exception in GUI",
            exc_info=(exc_type, exc_value, exc_tb),
        )
        _show_fatal_error(
            title="GF Audit - Fatal Error",
            message=str(exc_value) or exc_type.__name__,
            details=details,
        )

    sys.excepthook = _handle_exception


def _load_initial_state() -> Any:
    loaded_state = load_app_state()

    merged_state = _merge_app_state(app_state, loaded_state)
    if merged_state is not app_state:
        return merged_state

    return app_state


def _sync_window_state(main_window: Any) -> None:
    try:
        sync_method = getattr(main_window, "_sync_state_from_widgets", None)
        if callable(sync_method):
            sync_method()
    except Exception:
        logger.exception("Failed to sync GUI widget state before save")


def _save_current_state(current_app_state: Any) -> None:
    try:
        save_app_state(current_app_state)
    except Exception:
        logger.exception("Failed to save application state")


def main() -> int:
    _configure_logging()

    app_config = build_app_config()
    current_app_state = _load_initial_state()

    qt_app = QApplication(sys.argv)
    qt_app.setApplicationName(app_config.app_name)
    qt_app.setApplicationVersion(app_config.app_version)
    qt_app.setOrganizationName(app_config.app_name)

    _install_excepthook()

    main_window = MainWindow(
        app_config=app_config,
        app_state=current_app_state,
    )

    def _persist_before_quit() -> None:
        _sync_window_state(main_window)
        _save_current_state(current_app_state)

    qt_app.aboutToQuit.connect(_persist_before_quit)

    if hasattr(main_window, "show"):
        main_window.show()

    logger.info(
        "Starting GUI: app_name=%s app_version=%s",
        app_config.app_name,
        app_config.app_version,
    )

    return qt_app.exec()


if __name__ == "__main__":
    raise SystemExit(main())