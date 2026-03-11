from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from subprocess import Popen, TimeoutExpired
from time import perf_counter
from typing import Mapping, Sequence
import os


PROCESS_TIMEOUT_EXIT_CODE = 997


@dataclass(slots=True, frozen=True)
class ProcessRunResult:
    exit_code: int
    timed_out: bool
    stdout_path: str
    stderr_path: str
    duration_ms: int


def run_process_with_timeout(
    executable: str | Path,
    args: Sequence[str | Path],
    cwd: str | Path | None,
    stdout_path: str | Path,
    stderr_path: str | Path,
    timeout_sec: int,
    env: Mapping[str, str] | None = None,
) -> ProcessRunResult:
    executable_path = Path(executable)
    stdout_file_path = Path(stdout_path)
    stderr_file_path = Path(stderr_path)
    working_dir = Path(cwd) if cwd is not None else None

    if timeout_sec <= 0:
        raise ValueError("timeout_sec must be > 0")

    if not executable_path.exists():
        raise FileNotFoundError(f"Executable not found: {executable_path}")

    if working_dir is not None and not working_dir.exists():
        raise FileNotFoundError(f"Working directory not found: {working_dir}")

    stdout_file_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_file_path.parent.mkdir(parents=True, exist_ok=True)

    command = [str(executable_path), *[str(arg) for arg in args]]
    process_env = _build_process_env(env)

    started_clock = perf_counter()
    process: Popen[str] | None = None
    timed_out = False

    with stdout_file_path.open("w", encoding="utf-8", newline="") as stdout_handle, stderr_file_path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as stderr_handle:
        try:
            process = Popen(
                command,
                cwd=str(working_dir) if working_dir is not None else None,
                env=process_env,
                stdout=stdout_handle,
                stderr=stderr_handle,
                text=True,
            )
            exit_code = process.wait(timeout=timeout_sec)
        except TimeoutExpired:
            timed_out = True
            if process is not None:
                try:
                    process.kill()
                finally:
                    try:
                        process.wait(timeout=5)
                    except Exception:
                        pass
            exit_code = PROCESS_TIMEOUT_EXIT_CODE

        stdout_handle.flush()
        stderr_handle.flush()

    duration_ms = int((perf_counter() - started_clock) * 1000)

    return ProcessRunResult(
        exit_code=exit_code,
        timed_out=timed_out,
        stdout_path=str(stdout_file_path),
        stderr_path=str(stderr_file_path),
        duration_ms=duration_ms,
    )


def _build_process_env(env: Mapping[str, str] | None) -> dict[str, str]:
    process_env = dict(os.environ)
    if env:
        process_env.update({str(key): str(value) for key, value in env.items()})
    return process_env