from __future__ import annotations

from pathlib import Path
from typing import Final


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

APP_NAME: Final[str] = "gf-audit"
APP_VERSION: Final[str] = "1.0.0"


# ---------------------------------------------------------------------------
# Repository / runtime defaults
# ---------------------------------------------------------------------------

PACKAGE_DIR: Final[Path] = Path(__file__).resolve().parent
APP_DIR: Final[Path] = PACKAGE_DIR
REPO_ROOT: Final[Path] = APP_DIR.parent
DEFAULT_OUT_ROOT: Final[Path] = REPO_ROOT / "_gf_audit"


# ---------------------------------------------------------------------------
# Scan defaults
# ---------------------------------------------------------------------------

DEFAULT_SCAN_DIR: Final[str] = r"lib\src\albanian"
DEFAULT_SCAN_GLOB: Final[str] = "*.gf"
DEFAULT_TIMEOUT_SEC: Final[int] = 60
DEFAULT_MAX_FILES: Final[int] = 0

DEFAULT_INCLUDE_REGEX: Final[str] = r"^[A-Z][A-Za-z0-9_]*\.gf$"
DEFAULT_EXCLUDE_REGEX: Final[str] = r"( - Copie\.gf$|\.bak\.gf$|\.tmp\.gf$|\.disabled\.gf$|\s)"

DEFAULT_KEEP_OK_DETAILS: Final[bool] = False
DEFAULT_DIFF_PREVIOUS: Final[bool] = True
DEFAULT_SKIP_VERSION_PROBE: Final[bool] = False
DEFAULT_NO_COMPILE: Final[bool] = False
DEFAULT_EMIT_CPU_STATS: Final[bool] = False

DEFAULT_MODE: Final[str] = "all"
DEFAULT_TARGET_FILE: Final[str] = ""
DEFAULT_GF_PATH: Final[str] = ""


# ---------------------------------------------------------------------------
# Run / output naming
# ---------------------------------------------------------------------------

RUN_DIR_PREFIX: Final[str] = "run_"

MASTER_LOG_FILENAME: Final[str] = "master.log"
ALL_SCAN_LOGS_FILENAME: Final[str] = "ALL_SCAN_LOGS.TXT"
ALL_LOGS_FILENAME: Final[str] = "ALL_LOGS.TXT"
SUMMARY_JSON_FILENAME: Final[str] = "summary.json"
SUMMARY_MD_FILENAME: Final[str] = "summary.md"
AI_BRIEF_FILENAME: Final[str] = "ai_brief.txt"
TOP_ERRORS_FILENAME: Final[str] = "top_errors.txt"

DETAILS_DIRNAME: Final[str] = "details"
RAW_DIRNAME: Final[str] = "raw"
COMPILE_LOGS_DIRNAME: Final[str] = "compile"
SCAN_LOGS_DIRNAME: Final[str] = "scan"
ARTIFACTS_DIRNAME: Final[str] = "artifacts"
GFO_DIRNAME: Final[str] = "gfo"
OUT_DIRNAME: Final[str] = "out"


# ---------------------------------------------------------------------------
# Logging / encoding
# ---------------------------------------------------------------------------

DEFAULT_TEXT_ENCODING: Final[str] = "utf-8"
DEFAULT_NEWLINE: Final[str] = "\n"


# ---------------------------------------------------------------------------
# Allowed values
# ---------------------------------------------------------------------------

ALLOWED_MODES: Final[tuple[str, ...]] = ("all", "file")

ALLOWED_STATUSES: Final[tuple[str, ...]] = (
    "OK",
    "FAIL",
    "SKIPPED",
)

ALLOWED_DIAGNOSTIC_CLASSES: Final[tuple[str, ...]] = (
    "ok",
    "direct",
    "downstream",
    "ambiguous",
    "noise",
    "skipped",
)

ALLOWED_ERROR_KINDS: Final[tuple[str, ...]] = (
    "OK",
    "OTHER",
    "TYPE",
    "SYNTAX",
    "INTERNAL",
    "TIMEOUT",
    "SCRIPT",
)

ALLOWED_DIFF_CHANGE_KINDS: Final[tuple[str, ...]] = (
    "unchanged",
    "improved",
    "regressed",
    "new",
    "removed",
)


# ---------------------------------------------------------------------------
# UI defaults
# ---------------------------------------------------------------------------

DEFAULT_STATUS_MESSAGE: Final[str] = "Ready."
DEFAULT_WINDOW_TITLE: Final[str] = f"{APP_NAME} {APP_VERSION}"


# ---------------------------------------------------------------------------
# GF detection hints
# ---------------------------------------------------------------------------

RGL_CANDIDATE_DIRS: Final[tuple[str, ...]] = (
    "prelude",
    "abstract",
    "common",
    "present",
    "alltenses",
    "compat",
    "api",
)

GF_PATH_AUTO_PARTS: Final[tuple[str, ...]] = (
    "lib/src",
    "lib/src/albanian",
)

CAT_MODULE_CANDIDATES: Final[tuple[str, ...]] = (
    r"abstract\Cat.gf",
    r"abstract\Cat.gfo",
    r"present\Cat.gfo",
    r"alltenses\Cat.gfo",
)


# ---------------------------------------------------------------------------
# Report limits
# ---------------------------------------------------------------------------

DEFAULT_TOP_ERRORS_LIMIT: Final[int] = 120


__all__ = [
    "APP_NAME",
    "APP_VERSION",
    "PACKAGE_DIR",
    "APP_DIR",
    "REPO_ROOT",
    "DEFAULT_OUT_ROOT",
    "DEFAULT_SCAN_DIR",
    "DEFAULT_SCAN_GLOB",
    "DEFAULT_TIMEOUT_SEC",
    "DEFAULT_MAX_FILES",
    "DEFAULT_INCLUDE_REGEX",
    "DEFAULT_EXCLUDE_REGEX",
    "DEFAULT_KEEP_OK_DETAILS",
    "DEFAULT_DIFF_PREVIOUS",
    "DEFAULT_SKIP_VERSION_PROBE",
    "DEFAULT_NO_COMPILE",
    "DEFAULT_EMIT_CPU_STATS",
    "DEFAULT_MODE",
    "DEFAULT_TARGET_FILE",
    "DEFAULT_GF_PATH",
    "RUN_DIR_PREFIX",
    "MASTER_LOG_FILENAME",
    "ALL_SCAN_LOGS_FILENAME",
    "ALL_LOGS_FILENAME",
    "SUMMARY_JSON_FILENAME",
    "SUMMARY_MD_FILENAME",
    "AI_BRIEF_FILENAME",
    "TOP_ERRORS_FILENAME",
    "DETAILS_DIRNAME",
    "RAW_DIRNAME",
    "COMPILE_LOGS_DIRNAME",
    "SCAN_LOGS_DIRNAME",
    "ARTIFACTS_DIRNAME",
    "GFO_DIRNAME",
    "OUT_DIRNAME",
    "DEFAULT_TEXT_ENCODING",
    "DEFAULT_NEWLINE",
    "ALLOWED_MODES",
    "ALLOWED_STATUSES",
    "ALLOWED_DIAGNOSTIC_CLASSES",
    "ALLOWED_ERROR_KINDS",
    "ALLOWED_DIFF_CHANGE_KINDS",
    "DEFAULT_STATUS_MESSAGE",
    "DEFAULT_WINDOW_TITLE",
    "RGL_CANDIDATE_DIRS",
    "GF_PATH_AUTO_PARTS",
    "CAT_MODULE_CANDIDATES",
    "DEFAULT_TOP_ERRORS_LIMIT",
]