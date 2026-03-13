from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path

try:
    from ..models import FileResult, RunResult
    from ..utils.io_utils import ensure_dir
    from ..utils.path_utils import safe_name
except ImportError:  # pragma: no cover
    from models import FileResult, RunResult
    from utils.io_utils import ensure_dir
    from utils.path_utils import safe_name


def write_file_detail_logs(run_result: RunResult) -> None:
    details_dir = Path(run_result.run_paths.details_dir)
    ensure_dir(details_dir)

    stem_counts = Counter(_preferred_detail_stem(file_result) for file_result in run_result.file_results)

    for file_result in run_result.file_results:
        if not should_keep_detail_logs(file_result, run_result.run_config.keep_ok_details):
            continue

        detail_stem = _resolve_detail_stem(file_result, stem_counts)

        _copy_if_exists(
            src_path=_as_path(getattr(file_result, "scan_log_path", None)),
            dst_path=details_dir / f"{detail_stem}.scan.txt",
        )

        compile_summary = getattr(file_result, "compile_summary", None)
        if compile_summary is None:
            continue

        _copy_if_exists(
            src_path=_as_path(getattr(compile_summary, "stdout_path", None)),
            dst_path=details_dir / f"{detail_stem}.out.txt",
        )
        _copy_if_exists(
            src_path=_as_path(getattr(compile_summary, "stderr_path", None)),
            dst_path=details_dir / f"{detail_stem}.err.txt",
        )


def should_keep_detail_logs(file_result: FileResult, keep_ok_details: bool) -> bool:
    if getattr(file_result, "status", "") == "FAIL":
        return True
    if keep_ok_details:
        return True
    return False


def _preferred_detail_stem(file_result: FileResult) -> str:
    module_name = str(getattr(file_result, "module_name", "") or "").strip()
    if module_name:
        return module_name
    return _fallback_detail_stem(file_result)


def _resolve_detail_stem(file_result: FileResult, stem_counts: Counter[str]) -> str:
    preferred_stem = _preferred_detail_stem(file_result)
    if stem_counts[preferred_stem] == 1:
        return preferred_stem
    return _fallback_detail_stem(file_result)


def _fallback_detail_stem(file_result: FileResult) -> str:
    file_path = _as_path(getattr(file_result, "file_path", None))
    if file_path is None:
        return "unknown_file"

    if file_path.suffix:
        return safe_name(str(file_path.with_suffix("")))
    return safe_name(str(file_path))


def _copy_if_exists(src_path: Path | None, dst_path: Path) -> None:
    if src_path is None:
        return
    if not src_path.exists():
        return
    if not src_path.is_file():
        return

    ensure_dir(dst_path.parent)
    shutil.copy2(src_path, dst_path)


def _as_path(value: object) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value

    text = str(value).strip()
    if not text:
        return None

    return Path(text)