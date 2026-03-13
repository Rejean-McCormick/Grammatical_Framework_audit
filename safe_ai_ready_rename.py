#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Rule:
    path: str
    replacements: tuple[tuple[str, str], ...]


SAFE_RULES: tuple[Rule, ...] = (
    Rule(
        "README.md",
        (
            ("ai_brief.txt", "AI_READY.md"),
            ("report_ai_brief.py", "report_ai_ready.py"),
            ("ai_brief_path", "ai_ready_path"),
        ),
    ),
    Rule(
        "app/bootstrap.py",
        (
            ('AI_BRIEF_FILENAME = "ai_brief.txt"', 'AI_READY_FILENAME = "AI_READY.md"'),
            ("AI_BRIEF_FILENAME", "AI_READY_FILENAME"),
            ("ai_brief_path", "ai_ready_path"),
        ),
    ),
    Rule(
        "app/audit/audit_core.py",
        (
            ("from ..reports.report_ai_brief import write_ai_brief", "from ..reports.report_ai_ready import write_ai_ready"),
            ("write_ai_brief(run_result)", "write_ai_ready(run_result)"),
        ),
    ),
    Rule(
        "app/reports/__init__.py",
        (
            ("from .report_ai_brief import write_ai_brief", "from .report_ai_ready import write_ai_ready"),
            ('"write_ai_brief"', '"write_ai_ready"'),
            ("write_ai_brief", "write_ai_ready"),
        ),
    ),
    Rule(
        "app/reports/report_json.py",
        (
            ('"ai_brief_path"', '"ai_ready_path"'),
            ("ai_brief_path", "ai_ready_path"),
            ("ai_brief.txt", "AI_READY.md"),
        ),
    ),
    Rule(
        "app/reports/report_logs.py",
        (
            ('"ai_brief_path"', '"ai_ready_path"'),
            ("ai_brief_path", "ai_ready_path"),
            ("ai_brief.txt", "AI_READY.md"),
            ("BEGIN: ai_brief.txt", "BEGIN: AI_READY.md"),
            ("END: ai_brief.txt", "END: AI_READY.md"),
            ("ai_brief:", "ai_ready:"),
        ),
    ),
    Rule(
        "app/main_cli.py",
        (
            ("ai_brief_path", "ai_ready_path"),
            ("ai_brief:", "ai_ready:"),
            ("write_ai_brief", "write_ai_ready"),
            ("report_ai_brief", "report_ai_ready"),
        ),
    ),
    Rule(
        "tests/test_reports.py",
        (
            ("from app.reports.report_ai_brief import write_ai_brief", "from app.reports.report_ai_ready import write_ai_ready"),
            ("write_ai_brief(", "write_ai_ready("),
            ("ai_brief_path", "ai_ready_path"),
            ("ai_brief.txt", "AI_READY.md"),
            ("ai_brief:", "ai_ready:"),
        ),
    ),
)

# Deliberately excluded from search-and-replace:
# - app/models.py
# - app/audit/diff.py
# Those files need targeted manual logic for legacy summary compatibility.


def apply_replacements(text: str, replacements: tuple[tuple[str, str], ...]) -> tuple[str, list[tuple[str, str, int]]]:
    updated = text
    changes: list[tuple[str, str, int]] = []

    for old, new in replacements:
        count = updated.count(old)
        if count:
            updated = updated.replace(old, new)
            changes.append((old, new, count))

    return updated, changes


def show_diff(path: Path, before: str, after: str) -> None:
    diff = difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=str(path),
        tofile=str(path),
        n=3,
    )
    print("".join(diff), end="")


def main() -> int:
    parser = argparse.ArgumentParser(description="Safe dry-run search/replace for the AI_READY rename.")
    parser.add_argument("--root", default=".", help="Repository root")
    parser.add_argument("--apply", action="store_true", help="Write changes instead of dry-run")
    parser.add_argument(
        "--backup-dir",
        default=".rename_backups",
        help="Backup directory used only with --apply",
    )
    args = parser.parse_args()

    root = Path(args.root).resolve()
    backup_dir = root / args.backup_dir

    total_files_changed = 0
    total_replacements = 0

    print(f"mode={'APPLY' if args.apply else 'DRY-RUN'}")
    print(f"root={root}")
    print()

    for rule in SAFE_RULES:
        path = root / rule.path
        if not path.exists():
            print(f"SKIP missing: {rule.path}")
            continue

        before = path.read_text(encoding="utf-8")
        after, changes = apply_replacements(before, rule.replacements)

        if not changes:
            print(f"OK no changes: {rule.path}")
            continue

        total_files_changed += 1
        total_replacements += sum(count for _, _, count in changes)

        print(f"CHANGE {rule.path}")
        for old, new, count in changes:
            print(f"  {count:>3}x  {old!r}  ->  {new!r}")
        print()

        show_diff(path, before, after)
        print()

        if args.apply:
            backup_path = backup_dir / rule.path
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(before, encoding="utf-8")
            path.write_text(after, encoding="utf-8")

    print("-" * 60)
    print(f"files_changed={total_files_changed}")
    print(f"replacements={total_replacements}")
    print()

    if not args.apply:
        print("No files were modified. Re-run with --apply to write changes.")
    else:
        print(f"Backups written under: {backup_dir}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())