from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..models import CompileSummary, RunConfig, RunPaths
from ..utils.gf_utils import parse_compile_summary
from ..utils.io_utils import ensure_dir, write_text
from ..utils.path_utils import relative_to_project_root, safe_name
from ..utils.process_utils import run_process_with_timeout


def probe_gf_version(run_config: RunConfig, run_paths: RunPaths) -> str:
    version_stdout_path = Path(run_paths.raw_dir) / "gf_version.out.txt"
    version_stderr_path = Path(run_paths.raw_dir) / "gf_version.err.txt"

    ensure_dir(version_stdout_path.parent)
    ensure_dir(version_stderr_path.parent)

    result = run_process_with_timeout(
        executable=Path(run_config.gf_exe),
        args=["--version"],
        cwd=Path(run_config.project_root),
        stdout_path=version_stdout_path,
        stderr_path=version_stderr_path,
        timeout_sec=10,
    )

    if result.timed_out:
        return "TIMEOUT"

    version_text = _read_if_exists(version_stdout_path).strip()
    if version_text:
        return version_text.splitlines()[0].strip()

    stderr_text = _read_if_exists(version_stderr_path).strip()
    if stderr_text:
        return stderr_text.splitlines()[0].strip()

    return "UNKNOWN"


def build_gf_args(file_path: Path, run_config: RunConfig, run_paths: RunPaths) -> list[str]:
    gf_path = _resolve_gf_path(run_config)

    compile_args: list[str] = [
        "--batch",
        "--make",
        f"--gf-lib-path={Path(run_config.rgl_root)}",
        f"--path={gf_path}",
        f"--gfo-dir={Path(run_paths.gfo_dir)}",
        f"--output-dir={Path(run_paths.out_dir)}",
    ]

    if bool(run_config.emit_cpu_stats):
        compile_args.append("--cpu")

    compile_args.append(str(file_path))
    return compile_args


def compile_file(file_path: Path, run_config: RunConfig, run_paths: RunPaths) -> CompileSummary:
    file_path = Path(file_path)
    compile_logs_dir = Path(run_paths.compile_logs_dir)
    ensure_dir(compile_logs_dir)
    ensure_dir(Path(run_paths.gfo_dir))
    ensure_dir(Path(run_paths.out_dir))

    safe_file_name = safe_name(_build_relative_file_key(file_path, run_config))
    stdout_path = compile_logs_dir / f"{safe_file_name}.out.txt"
    stderr_path = compile_logs_dir / f"{safe_file_name}.err.txt"

    if bool(run_config.no_compile):
        write_text(stdout_path, "", encoding="utf-8")
        write_text(stderr_path, "", encoding="utf-8")
        return CompileSummary(
            exit_code=0,
            timed_out=False,
            duration_ms=0,
            error_kind="OK",
            first_error="",
            error_detail="compile skipped (-no-compile)",
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

    compile_args = build_gf_args(file_path, run_config, run_paths)

    process_result = run_process_with_timeout(
        executable=Path(run_config.gf_exe),
        args=compile_args,
        cwd=Path(run_config.project_root),
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_sec=int(run_config.timeout_sec),
    )

    stdout_text = _read_if_exists(stdout_path)
    stderr_text = _read_if_exists(stderr_path)
    combined_text = _combine_output(stdout_text, stderr_text)

    parsed_summary = parse_compile_summary(
        combined_text=combined_text,
        timed_out=process_result.timed_out,
        exit_code=process_result.exit_code,
    )

    return CompileSummary(
        exit_code=process_result.exit_code,
        timed_out=process_result.timed_out,
        duration_ms=process_result.duration_ms,
        error_kind=parsed_summary.error_kind,
        first_error=parsed_summary.first_error,
        error_detail=parsed_summary.error_detail,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
    )


def _resolve_gf_path(run_config: RunConfig) -> str:
    configured_gf_path = str(run_config.gf_path).strip()
    if configured_gf_path:
        return configured_gf_path

    rgl_root = Path(run_config.rgl_root)
    detected_rgl_parts = _detect_existing_rgl_subdirs(
        rgl_root,
        ["present", "alltenses", "common", "abstract", "prelude", "compat", "api"],
    )

    gf_path_parts = ["lib/src", str(run_config.scan_dir).strip()]
    gf_path_parts.extend(detected_rgl_parts)

    return ":".join(_deduplicate_preserving_order(gf_path_parts))


def _detect_existing_rgl_subdirs(rgl_root: Path, candidates: list[str]) -> list[str]:
    existing_subdirs: list[str] = []
    for subdir_name in candidates:
        if (rgl_root / subdir_name).exists():
            existing_subdirs.append(subdir_name)
    return existing_subdirs


def _build_relative_file_key(file_path: Path, run_config: RunConfig) -> str:
    try:
        return str(relative_to_project_root(file_path, Path(run_config.project_root)))
    except Exception:
        return file_path.name


def _combine_output(stdout_text: str, stderr_text: str) -> str:
    if stdout_text and stderr_text:
        return f"{stdout_text}\n{stderr_text}"
    return stdout_text or stderr_text or ""


def _read_if_exists(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _deduplicate_preserving_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        normalized_value = value.strip()
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        output.append(normalized_value)
    return output