# gf-audit

`gf-audit` is a project-level audit tool for GF grammars.

It scans GF source files, optionally compiles them with `gf.exe`, classifies failures, and generates structured outputs designed for both human debugging and AI-assisted analysis.

## Goals

- audit a whole GF project or one target file
- separate heuristic scan findings from real compilation failures
- distinguish likely direct failures from downstream cascades
- exclude noisy backup, copy, and temporary files
- generate compact summaries first and detailed logs second
- support iterative debugging with run-to-run diffing
- provide both a Windows GUI and a CLI
- produce a top-level AI handoff file without requiring a second compilation

## Core Features

- file selection with include/exclude regex filters
- GF-aware scanning with comment stripping and string masking
- per-file compilation with timeout
- compile error normalization
- failure classification:
  - `direct`
  - `downstream`
  - `ambiguous`
- source fingerprinting
- diff against the previous run
- structured outputs for summary, logs, and AI-ready handoff

## Repository Layout

```text
gf-audit/
  launch_gui.bat
  launch_cli.bat
  pyproject.toml
  README.md
  .gitignore

  app/
    __init__.py
    main_gui.py
    main_cli.py
    bootstrap.py
    config.py
    state.py
    models.py

    audit/
      __init__.py
      audit_core.py
      classifier.py
      compiler.py
      diff.py
      file_selector.py
      fingerprint.py
      result_model.py
      scanner.py

    gui/
      __init__.py
      dialogs.py
      main_window.py
      validators.py
      widgets.py

    reports/
      __init__.py
      report_ai_ready.py
      report_details.py
      report_json.py
      report_logs.py
      report_md.py

    utils/
      __init__.py
      gf_utils.py
      io_utils.py
      logging_utils.py
      path_utils.py
      process_utils.py

  tests/
    test_classifier.py
    test_diff.py
    test_reports.py
    test_scanner.py
    test_smoke.py
````

## Requirements

* Python 3.11+
* Windows
* `gf.exe`
* a GF project root
* an RGL root

## Main Concepts

### Modes

`gf-audit` supports two run modes:

* `all`

  * audit all selected GF files under the configured scan directory
* `file`

  * audit exactly one target file

### Scan vs Compile

Each file can produce two distinct kinds of results:

* **scan result**

  * heuristic detection of suspicious GF patterns
* **compile result**

  * actual `gf.exe` execution result

These are intentionally kept separate.

### Failure Classification

Compilation failures are classified into:

* `direct`
* `downstream`
* `ambiguous`

This avoids treating cascade failures as root causes.

## Outputs

Each run creates a timestamped run directory under the configured output root.

Typical outputs include:

```text
_gf_audit/
  run_YYYYMMDD_HHMMSS/
    summary.json
    summary.md
    AI_READY.md
    top_errors.txt
    details/
    raw/
```

### Main Report Files

* `summary.json`

  * structured result for tooling and automation
* `summary.md`

  * human-readable report
* `AI_READY.md`

  * top-level AI handoff packet with inlined diagnostic excerpts, artifact paths, and a ready-to-paste prompt
* `top_errors.txt`

  * grouped first-error summary

### Raw / Detailed Logs

* `master.log`
* `ALL_SCAN_LOGS.TXT`
* `ALL_LOGS.TXT`
* per-file scan logs
* per-file compile logs
* per-file detail logs for failures

## AI-First Workflow

`gf-audit` is designed to support AI-assisted debugging without rerunning compilation.

A normal workflow is:

1. run `gf-audit` once
2. inspect `summary.md` if you want a quick human summary
3. give `AI_READY.md` to an AI system as the main handoff artifact
4. use `ALL_LOGS.TXT` or files under `details/` only when deeper raw evidence is needed

`AI_READY.md` is intended to be self-contained. It includes:

* run summary
* main failure summary
* selected compile progression excerpt
* selected stderr excerpt
* fatal error block
* artifact paths
* a ready-made prompt for another AI

This avoids forcing the AI to dig through nested folders before it can reason about the failure.

## Configuration

Central defaults live in `app/config.py`.

Important settings include:

* scan directory
* scan glob
* timeout
* include regex
* exclude regex
* output directory
* report file names
* default mode
* default flags:

  * `keep_ok_details`
  * `diff_previous`
  * `skip_version_probe`
  * `no_compile`
  * `emit_cpu_stats`

## CLI Entry Point

Use `launch_cli.bat` to run the command-line version.

The CLI builds a run configuration, resolves run paths, runs the audit, and writes outputs.

Typical top-level outputs exposed by the CLI include:

* `summary.json`
* `summary.md`
* `AI_READY.md`
* `top_errors.txt`

## GUI Entry Point

Use `launch_gui.bat` to run the Windows GUI.

The GUI is responsible for:

* selecting the mode
* choosing paths
* editing filters
* starting a run
* displaying run status
* opening generated outputs

## Internal Data Model

The core run contract is based on typed models such as:

* `AppConfig`
* `RunConfig`
* `RunPaths`
* `ScanCounts`
* `SourceFingerprint`
* `CompileSummary`
* `FileResult`
* `DiffEntry`
* `RunResult`

These objects connect the scanner, compiler, classifier, diff engine, and output writers.

Important `RunPaths` artifacts include:

* `summary_json_path`
* `summary_md_path`
* `ai_ready_path`
* `top_errors_path`
* `master_log_path`
* `all_scan_logs_path`
* `all_logs_path`

## Execution Flow

1. build `RunConfig`
2. build `RunPaths`
3. select files
4. scan each file
5. optionally compile each file
6. fingerprint each file
7. build `FileResult`
8. classify failures
9. build `RunResult`
10. diff against the previous run
11. write outputs

## Testing

Tests live under `tests/`.

Recommended focus areas:

* scanner behavior
* classifier logic
* diff behavior
* report generation
* smoke path for a complete run

## Design Principles

* stable file and variable naming
* explicit typed models between modules
* robust filesystem handling
* logs preserved even after partial failure
* compact summaries first, raw logs second
* AI-ready handoff at the top level
* no hidden coupling between scan and compile phases
* no second compilation to produce AI-facing output

## Status

This project is structured as a serious Python-based audit tool for GF development:

* Python core
* Windows launchers
* GUI + CLI workflow
* report-driven debugging
* AI-oriented output design
* scalable foundation for future refinement

