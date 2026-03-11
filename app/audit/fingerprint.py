from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from app.models import SourceFingerprint


DEFAULT_SHA1_LENGTH = 7
DEFAULT_READ_CHUNK_SIZE = 1024 * 1024


def _coerce_file_path(file_path: str | Path) -> Path:
    path = Path(file_path).expanduser().resolve()

    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    if not path.is_file():
        raise ValueError(f"Expected a file path, got: {path}")

    return path


def _format_utc_timestamp(timestamp: float) -> str:
    return (
        datetime.fromtimestamp(timestamp, tz=timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def sha1_short(
    file_path: str | Path,
    length: int = DEFAULT_SHA1_LENGTH,
    chunk_size: int = DEFAULT_READ_CHUNK_SIZE,
) -> str:
    if length <= 0:
        raise ValueError("length must be greater than 0")

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    path = _coerce_file_path(file_path)

    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()[:length]


def build_source_fingerprint(file_path: str | Path) -> SourceFingerprint:
    path = _coerce_file_path(file_path)
    stat_result = path.stat()

    return SourceFingerprint(
        size_bytes=stat_result.st_size,
        sha1_short=sha1_short(path),
        last_modified_utc=_format_utc_timestamp(stat_result.st_mtime),
    )


__all__ = [
    "build_source_fingerprint",
    "sha1_short",
]