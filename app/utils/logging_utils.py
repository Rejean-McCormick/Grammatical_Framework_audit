from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


LOGGER_NAME = "gf_audit"

logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO)
logger.propagate = False

if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setLevel(logging.INFO)
    _handler.setFormatter(logging.Formatter("%(asctime)s  %(levelname)s  %(message)s"))
    logger.addHandler(_handler)


def _coerce_message(message: Any) -> str:
    if message is None:
        return ""
    return str(message)


def _coerce_path(path: str | Path) -> Path:
    return path if isinstance(path, Path) else Path(path)


def _timestamp() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _write_line(path: str | Path, line: str) -> None:
    file_path = _coerce_path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"{line}\n")


def log_info(message: Any) -> str:
    text = _coerce_message(message)
    logger.info(text)
    return text


def log_warning(message: Any) -> str:
    text = _coerce_message(message)
    logger.warning(text)
    return text


def log_error(message: Any) -> str:
    text = _coerce_message(message)
    logger.error(text)
    return text


def log_master(master_log_path: str | Path, message: Any, *, level: str = "info") -> str:
    text = _coerce_message(message)
    line = f"{_timestamp()}  {text}"
    _write_line(master_log_path, line)

    level_key = (level or "info").strip().lower()
    if level_key == "warning":
        logger.warning(text)
    elif level_key == "error":
        logger.error(text)
    else:
        logger.info(text)

    return line