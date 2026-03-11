```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal, TypeVar, get_args

Status = Literal["OK", "FAIL", "SKIPPED"]
DiagnosticClass = Literal["ok", "direct", "downstream", "ambiguous", "noise", "skipped"]
ErrorKind = Literal["OK", "OTHER", "TYPE", "SYNTAX", "INTERNAL", "TIMEOUT", "SCRIPT"]
ChangeKind = Literal["unchanged", "improved", "regressed", "new", "removed"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


T = TypeVar("T")


def _coerce_path(value: Any) -> Path:
    if isinstance(value, Path):
        return value
    return Path(value)


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if is_dataclass(value):
        return {k: _serialize_value(v) for k, v in asdict(value).items()}
    if isinstance(value, dict):
        return {str(k): _serialize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_serialize_value(v) for v in value]
    return value


def _validate_literal(name: str, value: str, allowed_literal: Any) -> None:
    allowed = set(get_args(allowed_literal))
    if value not in allowed:
        raise ValueError(f"{name} must be one of {sorted(allowed)}, got {value!r}")


@dataclass(slots=True)
class AppConfig:
    app_name: str
    app_version: str
    default_scan_dir: str
    default_scan_glob: str
    default_timeout_sec: int
    default_max_files: int
    default_include_regex: str
    default_exclude_regex: str
    default_keep_ok_details: bool
    default_diff_previous: bool
    default_skip_version_probe: bool
    default_no_compile: bool
    default_emit_cpu_stats: bool

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)


@dataclass(slots=True)
class RunConfig:
    project_root: Path
    rgl_root: Path
    gf_exe: Path
    out_root: Path
    scan_dir: str
    scan_glob: str
    gf_path: str
    timeout_sec: int
    max_files: int
    skip_version_probe: bool
    no_compile: bool
    emit_cpu_stats: bool
    mode: Literal["all", "file"]
    target_file: str
    include_regex: str
    exclude_regex: str
    keep_ok_details: bool
    diff_previous: bool

    def __post_init__(self) -> None:
        self.project_root = _coerce_path(self.project_root)
        self.rgl_root = _coerce_path(self.rgl_root)
        self.gf_exe = _coerce_path(self.gf_exe)
        self.out_root = _coerce_path(self.out_root)
        _validate_literal("mode", self.mode, Literal["all", "file"])

        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be > 0")
        if self.max_files < 0:
            raise ValueError("max_files must be >= 0")
        if self.mode == "file" and not self.target_file.strip():
            raise ValueError("target_file is required when mode='file'")

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunConfig:
        return cls(
            project_root=_coerce_path(data["project_root"]),
            rgl_root=_coerce_path(data["rgl_root"]),
            gf_exe=_coerce_path(data["gf_exe"]),
            out_root=_coerce_path(data["out_root"]),
            scan_dir=data["scan_dir"],
            scan_glob=data["scan_glob"],
            gf_path=data.get("gf_path", ""),
            timeout_sec=int(data["timeout_sec"]),
            max_files=int(data.get("max_files", 0)),
            skip_version_probe=bool(data.get("skip_version_probe", False)),
            no_compile=bool(data.get("no_compile", False)),
            emit_cpu_stats=bool(data.get("emit_cpu_stats", False)),
            mode=data.get("mode", "all"),
            target_file=data.get("target_file", ""),
            include_regex=data["include_regex"],
            exclude_regex=data["exclude_regex"],
            keep_ok_details=bool(data.get("keep_ok_details", False)),
            diff_previous=bool(data.get("diff_previous", False)),
        )


@dataclass(slots=True)
class RunPaths:
    run_id: str
    run_dir: Path
    master_log_path: Path
    all_scan_logs_path: Path
    all_logs_path: Path
    summary_json_path: Path
    summary_md_path: Path
    ai_brief_path: Path
    top_errors_path: Path
    details_dir: Path
    raw_dir: Path
    compile_logs_dir: Path
    scan_logs_dir: Path
    artifacts_dir: Path
    gfo_dir: Path
    out_dir: Path

    def __post_init__(self) -> None:
        for f in fields(self):
            value = getattr(self, f.name)
            if f.name != "run_id":
                setattr(self, f.name, _coerce_path(value))

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunPaths:
        return cls(
            run_id=data["run_id"],
            run_dir=_coerce_path(data["run_dir"]),
            master_log_path=_coerce_path(data["master_log_path"]),
            all_scan_logs_path=_coerce_path(data["all_scan_logs_path"]),
            all_logs_path=_coerce_path(data["all_logs_path"]),
            summary_json_path=_coerce_path(data["summary_json_path"]),
            summary_md_path=_coerce_path(data["summary_md_path"]),
            ai_brief_path=_coerce_path(data["ai_brief_path"]),
            top_errors_path=_coerce_path(data["top_errors_path"]),
            details_dir=_coerce_path(data["details_dir"]),
            raw_dir=_coerce_path(data["raw_dir"]),
            compile_logs_dir=_coerce_path(data["compile_logs_dir"]),
            scan_logs_dir=_coerce_path(data["scan_logs_dir"]),
            artifacts_dir=_coerce_path(data["artifacts_dir"]),
            gfo_dir=_coerce_path(data["gfo_dir"]),
            out_dir=_coerce_path(data["out_dir"]),
        )


@dataclass(slots=True)
class ScanCounts:
    single_slash_eq: int = 0
    double_slash_dash: int = 0
    runtime_str_match: int = 0
    untyped_case_str_pat: int = 0
    untyped_table_str_pat: int = 0
    trailing_spaces: int = 0

    @property
    def total_hits(self) -> int:
        return (
            self.single_slash_eq
            + self.double_slash_dash
            + self.runtime_str_match
            + self.untyped_case_str_pat
            + self.untyped_table_str_pat
            + self.trailing_spaces
        )

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScanCounts:
        return cls(
            single_slash_eq=int(data.get("single_slash_eq", 0)),
            double_slash_dash=int(data.get("double_slash_dash", 0)),
            runtime_str_match=int(data.get("runtime_str_match", 0)),
            untyped_case_str_pat=int(data.get("untyped_case_str_pat", 0)),
            untyped_table_str_pat=int(data.get("untyped_table_str_pat", 0)),
            trailing_spaces=int(data.get("trailing_spaces", 0)),
        )


@dataclass(slots=True)
class SourceFingerprint:
    size_bytes: int = 0
    sha1_short: str = ""
    last_modified_utc: str = ""

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceFingerprint:
        return cls(
            size_bytes=int(data.get("size_bytes", 0)),
            sha1_short=data.get("sha1_short", ""),
            last_modified_utc=data.get("last_modified_utc", ""),
        )


@dataclass(slots=True)
class CompileSummary:
    exit_code: int = 0
    timed_out: bool = False
    duration_ms: int = 0
    error_kind: ErrorKind = "OK"
    first_error: str = ""
    error_detail: str = ""
    stdout_path: Path | None = None
    stderr_path: Path | None = None

    def __post_init__(self) -> None:
        _validate_literal("error_kind", self.error_kind, ErrorKind)
        if self.stdout_path is not None:
            self.stdout_path = _coerce_path(self.stdout_path)
        if self.stderr_path is not None:
            self.stderr_path = _coerce_path(self.stderr_path)

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CompileSummary:
        stdout_path = data.get("stdout_path")
        stderr_path = data.get("stderr_path")
        return cls(
            exit_code=int(data.get("exit_code", 0)),
            timed_out=bool(data.get("timed_out", False)),
            duration_ms=int(data.get("duration_ms", 0)),
            error_kind=data.get("error_kind", "OK"),
            first_error=data.get("first_error", ""),
            error_detail=data.get("error_detail", ""),
            stdout_path=_coerce_path(stdout_path) if stdout_path else None,
            stderr_path=_coerce_path(stderr_path) if stderr_path else None,
        )


@dataclass(slots=True)
class FileResult:
    file_path: Path
    module_name: str
    status: Status
    diagnostic_class: DiagnosticClass
    is_direct: bool
    blocked_by: list[str] = field(default_factory=list)
    scan_counts: ScanCounts = field(default_factory=ScanCounts)
    fingerprint: SourceFingerprint = field(default_factory=SourceFingerprint)
    compile_summary: CompileSummary = field(default_factory=CompileSummary)
    scan_log_path: Path | None = None

    def __post_init__(self) -> None:
        self.file_path = _coerce_path(self.file_path)
        _validate_literal("status", self.status, Status)
        _validate_literal("diagnostic_class", self.diagnostic_class, DiagnosticClass)
        if self.scan_log_path is not None:
            self.scan_log_path = _coerce_path(self.scan_log_path)

    @property
    def has_scan_hits(self) -> bool:
        return self.scan_counts.total_hits > 0

    @property
    def first_error(self) -> str:
        return self.compile_summary.first_error

    @property
    def error_kind(self) -> ErrorKind:
        return self.compile_summary.error_kind

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FileResult:
        scan_log_path = data.get("scan_log_path")
        return cls(
            file_path=_coerce_path(data["file_path"]),
            module_name=data["module_name"],
            status=data["status"],
            diagnostic_class=data["diagnostic_class"],
            is_direct=bool(data.get("is_direct", False)),
            blocked_by=list(data.get("blocked_by", [])),
            scan_counts=ScanCounts.from_dict(data.get("scan_counts", {})),
            fingerprint=SourceFingerprint.from_dict(data.get("fingerprint", {})),
            compile_summary=CompileSummary.from_dict(data.get("compile_summary", {})),
            scan_log_path=_coerce_path(scan_log_path) if scan_log_path else None,
        )


@dataclass(slots=True)
class DiffEntry:
    file_path: str
    previous_status: str
    current_status: str
    change_kind: ChangeKind
    message: str

    def __post_init__(self) -> None:
        _validate_literal("change_kind", self.change_kind, ChangeKind)

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DiffEntry:
        return cls(
            file_path=data["file_path"],
            previous_status=data.get("previous_status", ""),
            current_status=data.get("current_status", ""),
            change_kind=data["change_kind"],
            message=data.get("message", ""),
        )


@dataclass(slots=True)
class RunResult:
    run_config: RunConfig
    run_paths: RunPaths
    started_at: datetime = field(default_factory=utc_now)
    finished_at: datetime = field(default_factory=utc_now)
    duration_ms: int = 0
    gf_version: str = ""
    files_seen: int = 0
    files_included: int = 0
    files_excluded: int = 0
    ok_count: int = 0
    fail_count: int = 0
    direct_fail_count: int = 0
    downstream_fail_count: int = 0
    ambiguous_fail_count: int = 0
    excluded_noise_count: int = 0
    file_results: list[FileResult] = field(default_factory=list)
    diff_entries: list[DiffEntry] = field(default_factory=list)
    top_errors: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if isinstance(self.started_at, str):
            self.started_at = datetime.fromisoformat(self.started_at)
        if isinstance(self.finished_at, str):
            self.finished_at = datetime.fromisoformat(self.finished_at)

    @property
    def failed_files(self) -> list[FileResult]:
        return [result for result in self.file_results if result.status == "FAIL"]

    @property
    def direct_failures(self) -> list[FileResult]:
        return [result for result in self.file_results if result.diagnostic_class == "direct"]

    @property
    def downstream_failures(self) -> list[FileResult]:
        return [result for result in self.file_results if result.diagnostic_class == "downstream"]

    @property
    def ambiguous_failures(self) -> list[FileResult]:
        return [result for result in self.file_results if result.diagnostic_class == "ambiguous"]

    def recompute_counts(self) -> None:
        self.ok_count = sum(1 for item in self.file_results if item.status == "OK")
        self.fail_count = sum(1 for item in self.file_results if item.status == "FAIL")
        self.direct_fail_count = sum(
            1 for item in self.file_results if item.diagnostic_class == "direct"
        )
        self.downstream_fail_count = sum(
            1 for item in self.file_results if item.diagnostic_class == "downstream"
        )
        self.ambiguous_fail_count = sum(
            1 for item in self.file_results if item.diagnostic_class == "ambiguous"
        )

    def to_dict(self) -> dict[str, Any]:
        return _serialize_value(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunResult:
        run_result = cls(
            run_config=RunConfig.from_dict(data["run_config"]),
            run_paths=RunPaths.from_dict(data["run_paths"]),
            started_at=data.get("started_at", utc_now().isoformat()),
            finished_at=data.get("finished_at", utc_now().isoformat()),
            duration_ms=int(data.get("duration_ms", 0)),
            gf_version=data.get("gf_version", ""),
            files_seen=int(data.get("files_seen", 0)),
            files_included=int(data.get("files_included", 0)),
            files_excluded=int(data.get("files_excluded", 0)),
            ok_count=int(data.get("ok_count", 0)),
            fail_count=int(data.get("fail_count", 0)),
            direct_fail_count=int(data.get("direct_fail_count", 0)),
            downstream_fail_count=int(data.get("downstream_fail_count", 0)),
            ambiguous_fail_count=int(data.get("ambiguous_fail_count", 0)),
            excluded_noise_count=int(data.get("excluded_noise_count", 0)),
            file_results=[FileResult.from_dict(item) for item in data.get("file_results", [])],
            diff_entries=[DiffEntry.from_dict(item) for item in data.get("diff_entries", [])],
            top_errors={str(k): int(v) for k, v in data.get("top_errors", {}).items()},
        )
        return run_result
```
