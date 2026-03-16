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


def test_main_cli_success_path_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    monkeypatch.setattr(main_cli, "parse_args", lambda argv=None: SimpleNamespace())
    monkeypatch.setattr(main_cli, "build_cli_run_config", lambda args: SimpleNamespace())

    def fake_run_audit(run_config):
        captured["run_config"] = run_config
        return _make_run_result(fail_count=0)

    def fake_write_reports(run_result):
        captured["write_reports_called"] = True
        captured["written_run_result"] = run_result

    def fake_print_run_summary(run_result):
        captured["print_run_summary_called"] = True

    monkeypatch.setattr(main_cli, "run_audit", fake_run_audit)
    monkeypatch.setattr(main_cli, "write_reports", fake_write_reports)
    monkeypatch.setattr(main_cli, "print_run_summary", fake_print_run_summary)

    exit_code = main_cli.main([])

    assert exit_code == main_cli.EXIT_OK
    assert captured["write_reports_called"] is True
    assert captured["print_run_summary_called"] is True
    assert captured["run_config"] is not None
    assert captured["written_run_result"].fail_count == 0


def test_main_cli_failure_path_returns_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main_cli, "parse_args", lambda argv=None: SimpleNamespace())
    monkeypatch.setattr(main_cli, "build_cli_run_config", lambda args: SimpleNamespace())
    monkeypatch.setattr(main_cli, "run_audit", lambda run_config: _make_run_result(fail_count=2))
    monkeypatch.setattr(main_cli, "write_reports", lambda run_result: None)
    monkeypatch.setattr(main_cli, "print_run_summary", lambda run_result: None)

    exit_code = main_cli.main([])

    assert exit_code == main_cli.EXIT_AUDIT_FAILURES


def test_main_cli_runtime_error_returns_runtime_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(main_cli, "parse_args", lambda argv=None: SimpleNamespace())
    monkeypatch.setattr(main_cli, "build_cli_run_config", lambda args: SimpleNamespace())

    def fake_run_audit(run_config):
        raise RuntimeError("boom")

    monkeypatch.setattr(main_cli, "run_audit", fake_run_audit)

    exit_code = main_cli.main([])

    captured = capsys.readouterr()
    assert exit_code == main_cli.EXIT_RUNTIME_ERROR
    assert "ERROR: boom" in captured.err


def test_determine_exit_code_matches_fail_count() -> None:
    assert main_cli.determine_exit_code(_make_run_result(fail_count=0)) == main_cli.EXIT_OK
    assert (
        main_cli.determine_exit_code(_make_run_result(fail_count=1))
        == main_cli.EXIT_AUDIT_FAILURES
    )