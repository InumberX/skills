#!/usr/bin/env python3
"""Unit tests for scripts/validate_text.py.

Standard library only (unittest), matching the other test modules. `check()`
takes a path, so each test writes a temporary Markdown file and inspects the
returned messages.

Run: python -m unittest discover -s tests -p "test_*.py"
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate_text.py"
_spec = importlib.util.spec_from_file_location("validate_text", _SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load validate_text module from {_SCRIPT}")
validate_text = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_text)


class CheckTest(unittest.TestCase):
    def check(self, body: str) -> list[str]:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.md"
            path.write_text(body, encoding="utf-8")
            return validate_text.check(path)

    def assertClean(self, body: str) -> None:
        self.assertEqual(self.check(body), [])

    # --- half-width parentheses around Japanese ---

    def test_flags_half_width_pair_wrapping_japanese(self):
        errors = self.check("スキル(タスク単位)を作る\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("line 1", errors[0])
        self.assertIn("半角括弧", errors[0])

    def test_accepts_full_width_pair(self):
        self.assertClean("スキル（タスク単位）を作る\n")

    def test_flags_each_occurrence_on_one_line(self):
        self.assertEqual(len(self.check("あ(い)う(え)お\n")), 2)

    def test_reports_the_line_number(self):
        errors = self.check("一行目\n\nスキル(タスク単位)\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("line 3", errors[0])

    # --- parentheses that wrap no Japanese are left alone ---

    def test_ignores_ascii_only_pair(self):
        self.assertClean("`git push(main)` と全 PR で自動実行する\n")

    def test_code_sample_without_japanese_is_clean(self):
        # 実際のコード例は日本語を含まないため、フェンスの中でも指摘されない。
        self.assertClean("```ts\nreturn redirect(to.pathname + to.search)\n```\n")

    def test_ignores_empty_pair(self):
        self.assertClean("空の括弧 () は対象外\n")

    # --- fenced code blocks are checked, not skipped ---

    def test_flags_japanese_inside_a_fenced_block(self):
        # README のディレクトリツリーのように、フェンスの中の注釈も本文と同じ扱い。
        errors = self.check("```text\n└── skills/   # 1 スキル = 1 ディレクトリ(タスク単位)\n```\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("line 2", errors[0])

    def test_flags_japanese_inside_an_inline_code_span(self):
        self.assertEqual(len(self.check("`値(デフォルト)` を書く\n")), 1)

    # --- Japanese detection covers the marks used in this repository ---

    def test_detects_katakana(self):
        self.assertEqual(len(self.check("値(デフォルト)\n")), 1)

    def test_detects_quotation_marks(self):
        self.assertEqual(len(self.check("列挙する(「Use when ...」)\n")), 1)

    def test_detects_middle_dot(self):
        self.assertEqual(len(self.check("Foo(a・b)\n")), 1)

    # --- mismatched pairs ---

    def test_flags_full_width_open_with_half_width_close(self):
        errors = self.check("更新する（ローカルでは `x`)\n")
        self.assertTrue(any("全角/半角が揃っていません" in e for e in errors))

    def test_flags_half_width_open_with_full_width_close(self):
        errors = self.check("更新する(ローカルでは `x`）\n")
        self.assertTrue(any("全角/半角が揃っていません" in e for e in errors))

    def test_mismatched_ascii_only_pair_is_still_flagged(self):
        # 中身が日本語でなくても、対応の取れていない括弧は誤りとして扱う。
        errors = self.check("push（main)\n")
        self.assertTrue(any("全角/半角が揃っていません" in e for e in errors))

    def test_nested_pairs_do_not_report_a_mismatch(self):
        self.assertClean("外側（内側（さらに内）まで）を書く\n")


class TargetsTest(unittest.TestCase):
    def test_repository_files_are_discovered(self):
        targets = validate_text.iter_targets()
        names = {p.name for p in targets}
        self.assertIn("README.md", names)
        self.assertIn("SKILL.md", names)

    def test_targets_are_sorted_and_unique(self):
        targets = validate_text.iter_targets()
        self.assertEqual(targets, sorted(set(targets)))


class RepositoryTest(unittest.TestCase):
    def test_repository_is_clean(self):
        """本番のファイルが規約を満たしていること（CI と同じ判定）。"""
        failures = {
            p.relative_to(validate_text.REPO_ROOT).as_posix(): errors
            for p in validate_text.iter_targets()
            if (errors := validate_text.check(p))
        }
        self.assertEqual(failures, {})


if __name__ == "__main__":
    unittest.main()
