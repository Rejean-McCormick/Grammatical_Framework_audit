from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app import main_cli


def _make_run_result(*, fail_count: int) -> SimpleNamespace:
    run_paths = SimpleNamespace(
        run_dir=Path("out/run_20260311_120000"),
        summary_json_path=Path("out/run_20260311_120000/summary.json"),
        summary_md_path=Path("out/run_20260311_120000/summary.md"),
        ai_ready_path=Path("out/run_20260311_120000/AI_READY.md"),
        all_scan_logs_path=Path("out/run_20260311_120000/ALL_SCAN_LOGS.TXT"),
        all_logs_path=Path("out/run_20260311_120000/ALL_LOGS.TXT"),
    )

    return SimpleNamespace(
        run_paths=run_paths,
        files_seen=3,
        files_included=3,
        files_excluded=0,
        ok_count=3 - fail_count,
        fail_count=fail_count,
        direct_fail_count=1 if fail_count else 0,
        downstream_fail_count=max(fail_count - 1, 0),
        ambiguous_fail_count=0,
    )


def test_main_cli_success_path_returns_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    expected_run_config = SimpleNamespace()
    expected_run_result = _make_run_result(fail_count=0)

    monkeypatch.setattr(
        main_cli,
        "parse_args",
        lambda argv=None: SimpleNamespace(),
    )
    monkeypatch.setattr(
        main_cli,
        "build_cli_run_config",
        lambda args: expected_run_config,
    )

    def fake_run_audit(run_config: object) -> SimpleNamespace:
        captured["run_config"] = run_config
        return expected_run_result

    def fake_print_run_summary(run_result: object) -> None:
        captured["printed_run_result"] = run_result

    monkeypatch.setattr(main_cli, "run_audit", fake_run_audit)
    monkeypatch.setattr(
        main_cli,
        "print_run_summary",
        fake_print_run_summary,
    )

    exit_code = main_cli.main([])

    assert exit_code == main_cli.EXIT_OK
    assert captured["run_config"] is expected_run_config
    assert captured["printed_run_result"] is expected_run_result


def test_main_cli_failure_path_returns_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected_run_result = _make_run_result(fail_count=2)
    captured: dict[str, object] = {}

    monkeypatch.setattr(
        main_cli,
        "parse_args",
        lambda argv=None: SimpleNamespace(),
    )
    monkeypatch.setattr(
        main_cli,
        "build_cli_run_config",
        lambda args: SimpleNamespace(),
    )
    monkeypatch.setattr(
        main_cli,
        "run_audit",
        lambda run_config: expected_run_result,
    )

    def fake_print_run_summary(run_result: object) -> None:
        captured["printed_run_result"] = run_result

    monkeypatch.setattr(
        main_cli,
        "print_run_summary",
        fake_print_run_summary,
    )

    exit_code = main_cli.main([])

    assert exit_code == main_cli.EXIT_AUDIT_FAILURES
    assert captured["printed_run_result"] is expected_run_result


def test_main_cli_runtime_error_returns_runtime_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        main_cli,
        "parse_args",
        lambda argv=None: SimpleNamespace(),
    )
    monkeypatch.setattr(
        main_cli,
        "build_cli_run_config",
        lambda args: SimpleNamespace(),
    )

    def fake_run_audit(run_config: object) -> SimpleNamespace:
        raise RuntimeError("boom")

    monkeypatch.setattr(main_cli, "run_audit", fake_run_audit)

    exit_code = main_cli.main([])

    captured = capsys.readouterr()

    assert exit_code == main_cli.EXIT_RUNTIME_ERROR
    assert "ERROR: boom" in captured.err


def test_determine_exit_code_matches_fail_count() -> None:
    assert (
        main_cli.determine_exit_code(_make_run_result(fail_count=0))
        == main_cli.EXIT_OK
    )
    assert (
        main_cli.determine_exit_code(_make_run_result(fail_count=1))
        == main_cli.EXIT_AUDIT_FAILURES
    )