from __future__ import annotations

from pathlib import Path
from textwrap import dedent
from types import SimpleNamespace

from app.audit.scanner import scan_file


def _make_run_config(project_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        project_root=project_root,
        scan_dir=r"lib\src\albanian",
        scan_glob="*.gf",
    )


def _make_run_paths(tmp_path: Path) -> SimpleNamespace:
    run_dir = tmp_path / "run_20260311_120000"
    scan_logs_dir = run_dir / "raw" / "scan"
    scan_logs_dir.mkdir(parents=True, exist_ok=True)

    return SimpleNamespace(
        run_id="20260311_120000",
        run_dir=run_dir,
        scan_logs_dir=scan_logs_dir,
    )


def _write_gf_file(project_root: Path, relative_path: str, content: str) -> Path:
    file_path = project_root / relative_path
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(dedent(content).lstrip("\n"), encoding="utf-8")
    return file_path


def _scan_value(scan_counts: object, field_name: str) -> int:
    if isinstance(scan_counts, dict):
        return int(scan_counts[field_name])
    return int(getattr(scan_counts, field_name))


def test_scan_file_detects_single_slash_eq_and_double_slash_dash(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    file_path = _write_gf_file(
        project_root,
        "lib/src/albanian/StructuralSqi.gf",
        r"""
        oper bad_lambda = \x => x ;
        oper bad_table  = \\x -> x ;
        """,
    )

    run_config = _make_run_config(project_root)
    run_paths = _make_run_paths(tmp_path)

    scan_counts, scan_log_path = scan_file(file_path=file_path, run_config=run_config, run_paths=run_paths)

    assert _scan_value(scan_counts, "single_slash_eq") == 1
    assert _scan_value(scan_counts, "double_slash_dash") == 1
    assert Path(scan_log_path).exists()


def test_scan_file_detects_runtime_string_match_block(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    file_path = _write_gf_file(
        project_root,
        "lib/src/albanian/MorphoSqi.gf",
        r'''
        oper linForm x =
          case x.s of {
            "abc" => foo ;
            _     => bar
          } ;
        ''',
    )

    run_config = _make_run_config(project_root)
    run_paths = _make_run_paths(tmp_path)

    scan_counts, _ = scan_file(file_path=file_path, run_config=run_config, run_paths=run_paths)

    assert _scan_value(scan_counts, "runtime_str_match") == 1
    assert _scan_value(scan_counts, "single_slash_eq") == 0
    assert _scan_value(scan_counts, "double_slash_dash") == 0


def test_scan_file_detects_untyped_case_and_table_string_patterns(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    file_path = _write_gf_file(
        project_root,
        "lib/src/albanian/ParadigmsSqi.gf",
        r'''
        oper c =
          case stem of { _ + "s" => mkN stem ; _ => mkN stem } ;

        oper t =
          table { _ + "e" => "x" ; _ => "y" } ;
        ''',
    )

    run_config = _make_run_config(project_root)
    run_paths = _make_run_paths(tmp_path)

    scan_counts, _ = scan_file(file_path=file_path, run_config=run_config, run_paths=run_paths)

    assert _scan_value(scan_counts, "untyped_case_str_pat") == 1
    assert _scan_value(scan_counts, "untyped_table_str_pat") == 1


def test_scan_file_counts_trailing_spaces(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    file_path = project_root / "lib/src/albanian/TestSqi.gf"
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(
        "oper a = x ;  \n"
        "oper b = y ;\n"
        "oper c = z ;\t\n",
        encoding="utf-8",
    )

    run_config = _make_run_config(project_root)
    run_paths = _make_run_paths(tmp_path)

    scan_counts, _ = scan_file(file_path=file_path, run_config=run_config, run_paths=run_paths)

    assert _scan_value(scan_counts, "trailing_spaces") == 2


def test_scan_file_ignores_patterns_inside_comments_and_strings(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    file_path = _write_gf_file(
        project_root,
        "lib/src/albanian/CommentsOnly.gf",
        r'''
        -- \x => x
        -- \\x -> x
        {- case x.s of { "abc" => foo ; _ => bar } -}
        {- case stem of { _ + "s" => mkN stem ; _ => mkN stem } -}
        {- table { _ + "e" => "x" ; _ => "y" } -}

        oper txt1 = "\x => x" ;
        oper txt2 = "\\x -> x" ;
        oper txt3 = "case x.s of { ""abc"" => foo }" ;
        ''',
    )

    run_config = _make_run_config(project_root)
    run_paths = _make_run_paths(tmp_path)

    scan_counts, _ = scan_file(file_path=file_path, run_config=run_config, run_paths=run_paths)

    assert _scan_value(scan_counts, "single_slash_eq") == 0
    assert _scan_value(scan_counts, "double_slash_dash") == 0
    assert _scan_value(scan_counts, "runtime_str_match") == 0
    assert _scan_value(scan_counts, "untyped_case_str_pat") == 0
    assert _scan_value(scan_counts, "untyped_table_str_pat") == 0
    assert _scan_value(scan_counts, "trailing_spaces") == 0


def test_scan_file_writes_summary_log(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    file_path = _write_gf_file(
        project_root,
        "lib/src/albanian/GrammarSqi.gf",
        r"""
        oper bad_lambda = \x => x ;
        """,
    )

    run_config = _make_run_config(project_root)
    run_paths = _make_run_paths(tmp_path)

    scan_counts, scan_log_path = scan_file(file_path=file_path, run_config=run_config, run_paths=run_paths)

    scan_log_text = Path(scan_log_path).read_text(encoding="utf-8")

    assert _scan_value(scan_counts, "single_slash_eq") == 1
    assert "SCAN SUMMARY:" in scan_log_text
    assert "SingleSlashThenEq hits: 1" in scan_log_text
    assert "DoubleSlashThenDash hits: 0" in scan_log_text
    assert "RuntimeStringMatch hits: 0" in scan_log_text
    assert str(file_path) in scan_log_text


def test_scan_file_handles_empty_file(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir(parents=True, exist_ok=True)

    file_path = _write_gf_file(
        project_root,
        "lib/src/albanian/Empty.gf",
        "",
    )

    run_config = _make_run_config(project_root)
    run_paths = _make_run_paths(tmp_path)

    scan_counts, scan_log_path = scan_file(file_path=file_path, run_config=run_config, run_paths=run_paths)

    assert _scan_value(scan_counts, "single_slash_eq") == 0
    assert _scan_value(scan_counts, "double_slash_dash") == 0
    assert _scan_value(scan_counts, "runtime_str_match") == 0
    assert _scan_value(scan_counts, "untyped_case_str_pat") == 0
    assert _scan_value(scan_counts, "untyped_table_str_pat") == 0
    assert _scan_value(scan_counts, "trailing_spaces") == 0
    assert Path(scan_log_path).exists()

