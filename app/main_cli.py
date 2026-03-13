from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

try:
    from .bootstrap import build_app_config, build_run_config
    from .audit.audit_core import run_audit
except ImportError:  # pragma: no cover
    from bootstrap import build_app_config, build_run_config
    from audit.audit_core import run_audit


EXIT_OK = 0
EXIT_AUDIT_FAILURES = 1
EXIT_INVALID_ARGS = 2
EXIT_RUNTIME_ERROR = 3


def build_argument_parser() -> argparse.ArgumentParser:
    app_config = build_app_config()

    parser = argparse.ArgumentParser(
        prog="gf-audit",
        description="Run the GF audit in all-files mode or single-file mode.",
    )

    parser.add_argument(
        "--project-root",
        required=True,
        type=Path,
        help="Path to the GF project root.",
    )
    parser.add_argument(
        "--rgl-root",
        required=True,
        type=Path,
        help="Path to the GF RGL root.",
    )
    parser.add_argument(
        "--gf-exe",
        required=True,
        type=Path,
        help="Path to gf.exe (or gf binary).",
    )
    parser.add_argument(
        "--out-root",
        required=True,
        type=Path,
        help="Path to the directory where audit runs will be written.",
    )

    parser.add_argument(
        "--scan-dir",
        default=app_config.default_scan_dir,
        help="Project-relative directory to scan for GF files.",
    )
    parser.add_argument(
        "--scan-glob",
        default=app_config.default_scan_glob,
        help="Glob used to enumerate GF source files.",
    )
    parser.add_argument(
        "--gf-path",
        default="",
        help="Explicit GF --path value. Leave empty to auto-build.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=int,
        default=app_config.default_timeout_sec,
        help="Per-file compile timeout in seconds.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=app_config.default_max_files,
        help="Maximum number of files to process. 0 means no limit.",
    )

    parser.add_argument(
        "--mode",
        choices=("all", "file"),
        default="all",
        help="Audit mode.",
    )
    parser.add_argument(
        "--target-file",
        type=Path,
        default=None,
        help="Target GF file when --mode=file.",
    )

    parser.add_argument(
        "--include-regex",
        default=app_config.default_include_regex,
        help="Regex used to include candidate files.",
    )
    parser.add_argument(
        "--exclude-regex",
        default=app_config.default_exclude_regex,
        help="Regex used to exclude candidate files.",
    )

    parser.add_argument(
        "--skip-version-probe",
        action=argparse.BooleanOptionalAction,
        default=app_config.default_skip_version_probe,
        help="Skip probing gf --version before the audit.",
    )
    parser.add_argument(
        "--no-compile",
        action=argparse.BooleanOptionalAction,
        default=app_config.default_no_compile,
        help="Only run scans, do not compile.",
    )
    parser.add_argument(
        "--emit-cpu-stats",
        action=argparse.BooleanOptionalAction,
        default=app_config.default_emit_cpu_stats,
        help="Pass GF CPU stats flags when compiling.",
    )
    parser.add_argument(
        "--keep-ok-details",
        action=argparse.BooleanOptionalAction,
        default=app_config.default_keep_ok_details,
        help="Keep per-file detail logs for OK files too.",
    )
    parser.add_argument(
        "--diff-previous",
        action=argparse.BooleanOptionalAction,
        default=app_config.default_diff_previous,
        help="Compare against the previous run if available.",
    )

    return parser


def validate_args(args: argparse.Namespace, parser: argparse.ArgumentParser) -> None:
    if args.timeout_sec <= 0:
        parser.error("--timeout-sec must be greater than 0.")

    if args.max_files < 0:
        parser.error("--max-files must be 0 or greater.")

    if args.mode == "file" and args.target_file is None:
        parser.error("--target-file is required when --mode=file.")

    if args.mode == "all" and args.target_file is not None:
        parser.error("--target-file can only be used when --mode=file.")

    if not args.project_root.exists():
        parser.error(f"--project-root does not exist: {args.project_root}")

    if not args.rgl_root.exists():
        parser.error(f"--rgl-root does not exist: {args.rgl_root}")

    if not args.gf_exe.exists():
        parser.error(f"--gf-exe does not exist: {args.gf_exe}")

    if args.mode == "file" and args.target_file is not None and not args.target_file.exists():
        parser.error(f"--target-file does not exist: {args.target_file}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    validate_args(args, parser)
    return args


def build_cli_run_config(args: argparse.Namespace):
    return build_run_config(
        project_root=args.project_root.resolve(),
        rgl_root=args.rgl_root.resolve(),
        gf_exe=args.gf_exe.resolve(),
        out_root=args.out_root.resolve(),
        scan_dir=args.scan_dir,
        scan_glob=args.scan_glob,
        gf_path=args.gf_path,
        timeout_sec=args.timeout_sec,
        max_files=args.max_files,
        skip_version_probe=args.skip_version_probe,
        no_compile=args.no_compile,
        emit_cpu_stats=args.emit_cpu_stats,
        mode=args.mode,
        target_file=args.target_file.resolve() if args.target_file else None,
        include_regex=args.include_regex,
        exclude_regex=args.exclude_regex,
        keep_ok_details=args.keep_ok_details,
        diff_previous=args.diff_previous,
    )


def print_run_summary(run_result) -> None:
    run_paths = run_result.run_paths

    print()
    print("GF Audit completed")
    print(f"run_dir: {run_paths.run_dir}")
    print(f"files_seen: {run_result.files_seen}")
    print(f"files_included: {run_result.files_included}")
    print(f"files_excluded: {run_result.files_excluded}")
    print(f"ok_count: {run_result.ok_count}")
    print(f"fail_count: {run_result.fail_count}")
    print(f"direct_fail_count: {run_result.direct_fail_count}")
    print(f"downstream_fail_count: {run_result.downstream_fail_count}")
    print(f"ambiguous_fail_count: {run_result.ambiguous_fail_count}")
    print()
    print(f"summary_json: {run_paths.summary_json_path}")
    print(f"summary_md: {run_paths.summary_md_path}")
    print(f"ai_ready: {run_paths.ai_ready_path}")
    print(f"all_scan_logs: {run_paths.all_scan_logs_path}")
    print(f"all_logs: {run_paths.all_logs_path}")
    print()


def determine_exit_code(run_result) -> int:
    return EXIT_AUDIT_FAILURES if run_result.fail_count > 0 else EXIT_OK


def main(argv: Sequence[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        run_config = build_cli_run_config(args)
        run_result = run_audit(run_config)
        print_run_summary(run_result)
        return determine_exit_code(run_result)
    except SystemExit as exc:
        code = exc.code if isinstance(exc.code, int) else EXIT_INVALID_ARGS
        return code
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}", file=sys.stderr)
        return EXIT_RUNTIME_ERROR


if __name__ == "__main__":
    raise SystemExit(main())