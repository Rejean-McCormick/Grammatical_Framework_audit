from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

try:
    from ..models import RunResult
except ImportError:  # pragma: no cover
    from models import RunResult  # type: ignore


def _to_json_value(value: Any) -> Any:
    if is_dataclass(value):
        return _to_json_value(asdict(value))

    if isinstance(value, Path):
        return str(value)

    if isinstance(value, datetime):
        return value.isoformat()

    if isinstance(value, date):
        return value.isoformat()

    if isinstance(value, Mapping):
        return {str(k): _to_json_value(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_to_json_value(item) for item in value]

    return value


def _build_totals(run_result: RunResult) -> dict[str, Any]:
    return {
        "files_seen": run_result.files_seen,
        "files_included": run_result.files_included,
        "files_excluded": run_result.files_excluded,
        "ok": run_result.ok_count,
        "fail": run_result.fail_count,
        "direct_fail": run_result.direct_fail_count,
        "downstream_fail": run_result.downstream_fail_count,
        "ambiguous_fail": run_result.ambiguous_fail_count,
        "excluded_noise": run_result.excluded_noise_count,
    }


def _build_metadata(run_result: RunResult) -> dict[str, Any]:
    run_config = run_result.run_config
    run_paths = run_result.run_paths

    return {
        "run_id": run_paths.run_id,
        "run_dir": str(run_paths.run_dir),
        "started_at": _to_json_value(run_result.started_at),
        "finished_at": _to_json_value(run_result.finished_at),
        "duration_ms": run_result.duration_ms,
        "gf_version": run_result.gf_version,
        "mode": run_config.mode,
        "target_file": run_config.target_file,
        "project_root": str(run_config.project_root),
        "rgl_root": str(run_config.rgl_root),
        "gf_exe": str(run_config.gf_exe),
        "out_root": str(run_config.out_root),
        "scan_dir": run_config.scan_dir,
        "scan_glob": run_config.scan_glob,
        "gf_path": run_config.gf_path,
        "timeout_sec": run_config.timeout_sec,
        "max_files": run_config.max_files,
        "skip_version_probe": run_config.skip_version_probe,
        "no_compile": run_config.no_compile,
        "emit_cpu_stats": run_config.emit_cpu_stats,
        "include_regex": run_config.include_regex,
        "exclude_regex": run_config.exclude_regex,
        "keep_ok_details": run_config.keep_ok_details,
        "diff_previous": run_config.diff_previous,
    }


def _build_artifact_paths(run_result: RunResult) -> dict[str, Any]:
    run_paths = run_result.run_paths

    return {
        "summary_json_path": str(run_paths.summary_json_path),
        "summary_md_path": str(run_paths.summary_md_path),
        "ai_ready_path": str(run_paths.ai_ready_path),
        "top_errors_path": str(run_paths.top_errors_path),
        "master_log_path": str(run_paths.master_log_path),
        "all_scan_logs_path": str(run_paths.all_scan_logs_path),
        "all_logs_path": str(run_paths.all_logs_path),
        "details_dir": str(run_paths.details_dir),
        "raw_dir": str(run_paths.raw_dir),
        "compile_logs_dir": str(run_paths.compile_logs_dir),
        "scan_logs_dir": str(run_paths.scan_logs_dir),
        "artifacts_dir": str(run_paths.artifacts_dir),
        "gfo_dir": str(run_paths.gfo_dir),
        "out_dir": str(run_paths.out_dir),
    }


def _build_summary_payload(run_result: RunResult) -> dict[str, Any]:
    return {
        "metadata": _build_metadata(run_result),
        "totals": _build_totals(run_result),
        "artifacts": _build_artifact_paths(run_result),
        "file_results": _to_json_value(run_result.file_results),
        "diff_entries": _to_json_value(run_result.diff_entries),
        "top_errors": _to_json_value(run_result.top_errors),
    }


def write_summary_json(run_result: RunResult) -> Path:
    summary_json_path = run_result.run_paths.summary_json_path
    summary_json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = _build_summary_payload(run_result)
    summary_json_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return summary_json_path


__all__: Sequence[str] = [
    "write_summary_json",
]