from __future__ import annotations

from collections import Counter
from collections.abc import Iterable as IterableABC
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.models import RunResult


UTF8 = "utf-8"
SECTION_RULE = "=" * 78


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _as_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value

    text = str(value).strip()
    if not text:
        return None

    return Path(text)


def _ensure_parent_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _read_text(path: str | Path | None) -> str:
    source_path = _as_path(path)
    if source_path is None or not source_path.exists() or not source_path.is_file():
        return ""
    return source_path.read_text(encoding=UTF8, errors="replace")


def _write_text(path: str | Path, content: str) -> Path:
    output_path = _as_path(path)
    if output_path is None:
        raise ValueError("Output path cannot be None")
    _ensure_parent_dir(output_path)
    output_path.write_text(content, encoding=UTF8)
    return output_path


def _append_text(path: str | Path, content: str) -> Path:
    output_path = _as_path(path)
    if output_path is None:
        raise ValueError("Output path cannot be None")
    _ensure_parent_dir(output_path)
    with output_path.open("a", encoding=UTF8, newline="") as handle:
        handle.write(content)
    return output_path


def _utc_now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _local_now_log() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def _iter_file_results(run_result: RunResult) -> list[Any]:
    return list(_get(run_result, "file_results", []) or [])


def _iter_top_errors(run_result: RunResult) -> list[tuple[str, int]]:
    top_errors = _get(run_result, "top_errors")
    if isinstance(top_errors, dict):
        return sorted(
            ((str(key), int(value)) for key, value in top_errors.items()),
            key=lambda item: (-item[1], item[0]),
        )

    if isinstance(top_errors, list):
        normalized: list[tuple[str, int]] = []
        for item in top_errors:
            if isinstance(item, tuple) and len(item) == 2:
                normalized.append((str(item[0]), int(item[1])))
                continue
            if isinstance(item, dict):
                message = str(item.get("message", ""))
                count = int(item.get("count", 0))
                if message:
                    normalized.append((message, count))
        if normalized:
            return sorted(normalized, key=lambda item: (-item[1], item[0]))

    counter: Counter[str] = Counter()
    for file_result in _iter_file_results(run_result):
        compile_summary = _get(file_result, "compile_summary")
        error_kind = _get(compile_summary, "error_kind", "OK")
        first_error = (_get(compile_summary, "first_error", "") or "").strip()
        status = _get(file_result, "status", "")
        if status == "FAIL" and error_kind != "OK" and first_error:
            counter[f"[{error_kind}] {first_error}"] += 1

    return sorted(counter.items(), key=lambda item: (-item[1], item[0]))


def _artifact_section_title(source_path: str | Path | None, fallback: str) -> str:
    resolved_path = _as_path(source_path)
    if resolved_path is None:
        return fallback
    return resolved_path.name or fallback


def _build_section(title: str, source_path: str | Path | None) -> str:
    resolved_path = _as_path(source_path)
    path_text = str(resolved_path) if resolved_path is not None else "[MISSING]"
    body = _read_text(resolved_path)

    if not body:
        if resolved_path is None or not resolved_path.exists() or not resolved_path.is_file():
            body = "[MISSING]"
        else:
            body = ""

    if body and not body.endswith("\n"):
        body += "\n"

    return (
        f"\n{SECTION_RULE}\n"
        f"BEGIN: {title}\n"
        f"PATH: {path_text}\n"
        f"{SECTION_RULE}\n"
        f"{body}"
        f"{SECTION_RULE}\n"
        f"END: {title}\n"
        f"{SECTION_RULE}\n"
    )


def _build_master_header(run_result: RunResult) -> str:
    run_config = _get(run_result, "run_config")
    run_paths = _get(run_result, "run_paths")

    lines = [
        f"{_local_now_log()}  Run started",
        f"{_local_now_log()}  run_id={_get(run_paths, 'run_id', '')}",
        f"{_local_now_log()}  run_dir={_get(run_paths, 'run_dir', '')}",
        f"{_local_now_log()}  project_root={_get(run_config, 'project_root', '')}",
        f"{_local_now_log()}  rgl_root={_get(run_config, 'rgl_root', '')}",
        f"{_local_now_log()}  gf_exe={_get(run_config, 'gf_exe', '')}",
        f"{_local_now_log()}  out_root={_get(run_config, 'out_root', '')}",
        f"{_local_now_log()}  scan_dir={_get(run_config, 'scan_dir', '')}",
        f"{_local_now_log()}  scan_glob={_get(run_config, 'scan_glob', '')}",
        f"{_local_now_log()}  gf_path={_get(run_config, 'gf_path', '')}",
        f"{_local_now_log()}  timeout_sec={_get(run_config, 'timeout_sec', '')}",
        f"{_local_now_log()}  mode={_get(run_config, 'mode', '')}",
        f"{_local_now_log()}  target_file={_get(run_config, 'target_file', '')}",
        f"{_local_now_log()}  no_compile={_get(run_config, 'no_compile', '')}",
        f"{_local_now_log()}  emit_cpu_stats={_get(run_config, 'emit_cpu_stats', '')}",
        f"{_local_now_log()}  keep_ok_details={_get(run_config, 'keep_ok_details', '')}",
        f"{_local_now_log()}  diff_previous={_get(run_config, 'diff_previous', '')}",
        f"{_local_now_log()}  skip_version_probe={_get(run_config, 'skip_version_probe', '')}",
        f"{_local_now_log()}  include_regex={_get(run_config, 'include_regex', '')}",
        f"{_local_now_log()}  exclude_regex={_get(run_config, 'exclude_regex', '')}",
        f"{_local_now_log()}  gf_version={_get(run_result, 'gf_version', '')}",
        f"{_local_now_log()}  started_at={_get(run_result, 'started_at', '')}",
        f"{_local_now_log()}  finished_at={_get(run_result, 'finished_at', '')}",
        f"{_local_now_log()}  duration_ms={_get(run_result, 'duration_ms', '')}",
        f"{_local_now_log()}  files_seen={_get(run_result, 'files_seen', 0)}",
        f"{_local_now_log()}  files_included={_get(run_result, 'files_included', 0)}",
        f"{_local_now_log()}  files_excluded={_get(run_result, 'files_excluded', 0)}",
        f"{_local_now_log()}  ok_count={_get(run_result, 'ok_count', 0)}",
        f"{_local_now_log()}  fail_count={_get(run_result, 'fail_count', 0)}",
        f"{_local_now_log()}  direct_fail_count={_get(run_result, 'direct_fail_count', 0)}",
        f"{_local_now_log()}  downstream_fail_count={_get(run_result, 'downstream_fail_count', 0)}",
        f"{_local_now_log()}  ambiguous_fail_count={_get(run_result, 'ambiguous_fail_count', 0)}",
        f"{_local_now_log()}  excluded_noise_count={_get(run_result, 'excluded_noise_count', 0)}",
    ]
    return "\n".join(lines) + "\n"


def _iter_existing_detail_paths(run_result: RunResult) -> Iterable[tuple[str, Path]]:
    seen: set[Path] = set()

    for file_result in _iter_file_results(run_result):
        file_path = _get(file_result, "file_path", "")

        scan_log_path = _as_path(_get(file_result, "scan_log_path"))
        if scan_log_path and scan_log_path.exists() and scan_log_path.is_file() and scan_log_path not in seen:
            seen.add(scan_log_path)
            yield (f"scan: {file_path or scan_log_path.name}", scan_log_path)

        compile_summary = _get(file_result, "compile_summary")
        stdout_path = _as_path(_get(compile_summary, "stdout_path"))
        stderr_path = _as_path(_get(compile_summary, "stderr_path"))

        if stdout_path and stdout_path.exists() and stdout_path.is_file() and stdout_path not in seen:
            seen.add(stdout_path)
            yield (f"compile stdout: {file_path or stdout_path.name}", stdout_path)

        if stderr_path and stderr_path.exists() and stderr_path.is_file() and stderr_path not in seen:
            seen.add(stderr_path)
            yield (f"compile stderr: {file_path or stderr_path.name}", stderr_path)


def _iter_log_messages(messages: Any) -> Iterable[str]:
    if messages is None:
        return

    if isinstance(messages, str):
        yield messages
        return

    if isinstance(messages, (bytes, bytearray)):
        yield messages.decode(UTF8, errors="replace")
        return

    if isinstance(messages, IterableABC) and not isinstance(messages, dict):
        for item in messages:
            yield from _iter_log_messages(item)
        return

    yield str(messages)


def write_master_log(master_log_path: str | Path, messages: Any) -> Path:
    output_path = _as_path(master_log_path)
    if output_path is None:
        raise ValueError("master_log_path cannot be None")

    rendered = "".join(
        f"{_local_now_log()}  {message.rstrip()}\n"
        for message in _iter_log_messages(messages)
        if message is not None and str(message).strip() != ""
    )

    return _append_text(output_path, rendered)


def append_scan_log(
    all_scan_logs_path: str | Path,
    file_path: str | Path,
    scan_log_path: str | Path,
) -> Path:
    title = f"scan: {file_path}"
    section = _build_section(title=title, source_path=scan_log_path)
    return _append_text(all_scan_logs_path, section)


def write_all_scan_logs(run_result: RunResult) -> Path:
    run_paths = _get(run_result, "run_paths")
    all_scan_logs_path = _as_path(_get(run_paths, "all_scan_logs_path"))
    if all_scan_logs_path is None:
        raise ValueError("run_result.run_paths.all_scan_logs_path is required")

    _write_text(all_scan_logs_path, "")

    for file_result in _iter_file_results(run_result):
        scan_log_path = _as_path(_get(file_result, "scan_log_path"))
        file_path = _get(file_result, "file_path", "")
        if scan_log_path is not None:
            append_scan_log(
                all_scan_logs_path=all_scan_logs_path,
                file_path=file_path,
                scan_log_path=scan_log_path,
            )

    return all_scan_logs_path


def write_top_errors(run_result: RunResult) -> Path:
    run_paths = _get(run_result, "run_paths")
    top_errors_path = _as_path(_get(run_paths, "top_errors_path"))
    if top_errors_path is None:
        raise ValueError("run_result.run_paths.top_errors_path is required")

    lines = [
        "TOP ERRORS (bucketed by [error_kind] first_error)",
        "===============================================",
        "",
    ]

    for message, count in _iter_top_errors(run_result):
        lines.append(f"{count:4d}  {message}")

    if len(lines) == 3:
        lines.append("No errors.")

    lines.append("")
    return _write_text(top_errors_path, "\n".join(lines))


def write_all_logs(run_result: RunResult) -> Path:
    run_paths = _get(run_result, "run_paths")
    all_logs_path = _as_path(_get(run_paths, "all_logs_path"))
    if all_logs_path is None:
        raise ValueError("run_result.run_paths.all_logs_path is required")

    master_log_path = _as_path(_get(run_paths, "master_log_path"))
    all_scan_logs_path = _as_path(_get(run_paths, "all_scan_logs_path"))
    summary_json_path = _as_path(_get(run_paths, "summary_json_path"))
    summary_md_path = _as_path(_get(run_paths, "summary_md_path"))
    ai_ready_path = _as_path(_get(run_paths, "ai_ready_path"))
    top_errors_path = _as_path(_get(run_paths, "top_errors_path"))

    _write_text(all_logs_path, "")

    if master_log_path is not None:
        _append_text(
            all_logs_path,
            _build_section(
                title=_artifact_section_title(master_log_path, "master.log"),
                source_path=master_log_path,
            ),
        )

    if all_scan_logs_path is not None:
        _append_text(
            all_logs_path,
            _build_section(
                title=_artifact_section_title(all_scan_logs_path, "ALL_SCAN_LOGS.TXT"),
                source_path=all_scan_logs_path,
            ),
        )

    if top_errors_path is not None:
        _append_text(
            all_logs_path,
            _build_section(
                title=_artifact_section_title(top_errors_path, "top_errors.txt"),
                source_path=top_errors_path,
            ),
        )

    if ai_ready_path is not None:
        _append_text(
            all_logs_path,
            _build_section(
                title=_artifact_section_title(ai_ready_path, "AI_READY.md"),
                source_path=ai_ready_path,
            ),
        )

    if summary_md_path is not None:
        _append_text(
            all_logs_path,
            _build_section(
                title=_artifact_section_title(summary_md_path, "summary.md"),
                source_path=summary_md_path,
            ),
        )

    if summary_json_path is not None:
        _append_text(
            all_logs_path,
            _build_section(
                title=_artifact_section_title(summary_json_path, "summary.json"),
                source_path=summary_json_path,
            ),
        )

    for title, detail_path in _iter_existing_detail_paths(run_result):
        _append_text(all_logs_path, _build_section(title, detail_path))

    return all_logs_path


__all__ = [
    "append_scan_log",
    "write_all_logs",
    "write_all_scan_logs",
    "write_master_log",
    "write_top_errors",
]