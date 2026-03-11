from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def _to_path(value: str | os.PathLike[str] | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)


def ensure_dir(path: str | os.PathLike[str] | Path) -> Path:
    path_obj = _to_path(path)
    path_obj.mkdir(parents=True, exist_ok=True)
    return path_obj


def read_text(
    path: str | os.PathLike[str] | Path,
    *,
    encoding: str = "utf-8",
    default: str = "",
) -> str:
    path_obj = _to_path(path)
    if not path_obj.exists():
        return default
    return path_obj.read_text(encoding=encoding)


def write_text(
    path: str | os.PathLike[str] | Path,
    content: str,
    *,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> Path:
    path_obj = _to_path(path)
    ensure_dir(path_obj.parent)
    with path_obj.open("w", encoding=encoding, newline=newline) as handle:
        handle.write(content)
    return path_obj


def append_text(
    path: str | os.PathLike[str] | Path,
    content: str,
    *,
    encoding: str = "utf-8",
    newline: str | None = None,
) -> Path:
    path_obj = _to_path(path)
    ensure_dir(path_obj.parent)
    with path_obj.open("a", encoding=encoding, newline=newline) as handle:
        handle.write(content)
    return path_obj


def safe_unlink(path: str | os.PathLike[str] | Path) -> bool:
    path_obj = _to_path(path)
    try:
        path_obj.unlink()
        return True
    except FileNotFoundError:
        return False


def read_json(
    path: str | os.PathLike[str] | Path,
    *,
    encoding: str = "utf-8",
    default: Any = None,
) -> Any:
    path_obj = _to_path(path)
    if not path_obj.exists():
        return {} if default is None else default

    try:
        with path_obj.open("r", encoding=encoding) as handle:
            return json.load(handle)
    except json.JSONDecodeError:
        return {} if default is None else default


def write_json(
    path: str | os.PathLike[str] | Path,
    payload: Mapping[str, Any] | list[Any],
    *,
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False,
    atomic: bool = True,
) -> Path:
    path_obj = _to_path(path)
    ensure_dir(path_obj.parent)

    serialized = json.dumps(payload, indent=indent, ensure_ascii=ensure_ascii)

    if not atomic:
        path_obj.write_text(serialized, encoding=encoding)
        return path_obj

    tmp_path = path_obj.with_suffix(path_obj.suffix + ".tmp")
    tmp_path.write_text(serialized, encoding=encoding)
    tmp_path.replace(path_obj)
    return path_obj


__all__ = [
    "read_text",
    "write_text",
    "append_text",
    "ensure_dir",
    "safe_unlink",
    "read_json",
    "write_json",
]