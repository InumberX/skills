#!/usr/bin/env python3
"""Unit tests for scripts/validate_skills.py.

Uses only the standard library (unittest) so CI needs no extra dependency
beyond PyYAML, which the validator itself requires. The module under test is
loaded by path via importlib so these tests do not depend on packaging or
sys.path layout.

Run: python -m unittest discover -s tests -p "test_*.py"
"""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate_skills.py"
_spec = importlib.util.spec_from_file_location("validate_skills", _SCRIPT)
validate_skills = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_skills)


def frontmatter(name: str, description_line: str) -> str:
    """Build a SKILL.md body with the given name and a raw description line."""
    return f"---\nname: {name}\n{description_line}\n---\n\n# {name}\n"


class TestSplitFrontmatter(unittest.TestCase):
    def test_valid_block_is_returned(self):
        text = "---\nname: x\ndescription: \"y\"\n---\nbody\n"
        self.assertEqual(validate_skills.split_frontmatter(text), 'name: x\ndescription: "y"\n')

    def test_crlf_delimiters(self):
        text = "---\r\nname: x\r\n---\r\nbody\r\n"
        self.assertEqual(validate_skills.split_frontmatter(text), "name: x\r\n")

    def test_missing_leading_delimiter(self):
        self.assertIsNone(validate_skills.split_frontmatter("name: x\n---\n"))

    def test_unterminated(self):
        self.assertIsNone(validate_skills.split_frontmatter("---\nname: x\n"))

    def test_four_dash_line_is_not_a_terminator(self):
        self.assertIsNone(validate_skills.split_frontmatter("---\nname: x\n----\nbody\n"))

    def test_dash_prefixed_string_is_not_a_terminator(self):
        self.assertIsNone(validate_skills.split_frontmatter("---\nname: x\n---foo\nbody\n"))


class TestDescriptionScalarStyle(unittest.TestCase):
    def test_double_quoted(self):
        self.assertEqual(validate_skills.description_scalar_style('description: "a: b"'), '"')

    def test_single_quoted(self):
        self.assertEqual(validate_skills.description_scalar_style("description: 'a'"), "'")

    def test_single_quoted_starting_with_double_quote(self):
        # The value's content starts with a double quote but the scalar style
        # is single-quoted -> must not be reported as double-quoted.
        self.assertEqual(validate_skills.description_scalar_style("description: '\"a\"'"), "'")

    def test_plain(self):
        self.assertIsNone(validate_skills.description_scalar_style("description: a"))

    def test_block_scalar(self):
        self.assertEqual(validate_skills.description_scalar_style("description: |\n  a\n"), "|")

    def test_absent(self):
        self.assertIsNone(validate_skills.description_scalar_style("name: x"))


class TestCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def write_skill(self, dir_name: str, body: str) -> Path:
        skill_dir = self.root / dir_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_md = skill_dir / "SKILL.md"
        skill_md.write_text(body, encoding="utf-8")
        return skill_md

    # --- valid cases -------------------------------------------------------

    def test_valid_minimal(self):
        md = self.write_skill("do-thing", frontmatter("do-thing", 'description: "Do the thing."'))
        self.assertEqual(validate_skills.check(md), [])

    def test_valid_description_with_colon(self):
        md = self.write_skill(
            "do-thing", frontmatter("do-thing", 'description: "Prefixes like feat: and fix: are fine."')
        )
        self.assertEqual(validate_skills.check(md), [])

    def test_valid_description_with_hash(self):
        md = self.write_skill(
            "do-thing", frontmatter("do-thing", 'description: "Handles #tags and colons: here."')
        )
        self.assertEqual(validate_skills.check(md), [])

    def test_valid_crlf(self):
        body = '---\r\nname: do-thing\r\ndescription: "Do the thing."\r\n---\r\n\r\n# do-thing\r\n'
        md = self.write_skill("do-thing", body)
        self.assertEqual(validate_skills.check(md), [])

    # --- invalid cases -----------------------------------------------------

    def assert_error_contains(self, errors, needle):
        self.assertTrue(errors, "expected at least one error")
        self.assertTrue(
            any(needle in e for e in errors),
            f"expected an error containing {needle!r}, got {errors!r}",
        )

    def test_no_frontmatter(self):
        md = self.write_skill("do-thing", "# do-thing\n\nno frontmatter here\n")
        self.assert_error_contains(validate_skills.check(md), "frontmatter")

    def test_unterminated_frontmatter(self):
        md = self.write_skill("do-thing", '---\nname: do-thing\ndescription: "x"\n')
        self.assert_error_contains(validate_skills.check(md), "frontmatter")

    def test_four_dash_terminator(self):
        md = self.write_skill("do-thing", '---\nname: do-thing\ndescription: "x"\n----\nbody\n')
        self.assert_error_contains(validate_skills.check(md), "frontmatter")

    def test_name_missing(self):
        md = self.write_skill("do-thing", '---\ndescription: "x"\n---\n')
        self.assert_error_contains(validate_skills.check(md), "`name` is missing")

    def test_name_empty(self):
        md = self.write_skill("do-thing", '---\nname: ""\ndescription: "x"\n---\n')
        self.assert_error_contains(validate_skills.check(md), "`name` is missing")

    def test_name_not_kebab(self):
        md = self.write_skill("Do_Thing", frontmatter("Do_Thing", 'description: "x"'))
        self.assert_error_contains(validate_skills.check(md), "kebab-case")

    def test_name_dir_mismatch(self):
        md = self.write_skill("other-dir", frontmatter("do-thing", 'description: "x"'))
        self.assert_error_contains(validate_skills.check(md), "must match its directory")

    def test_description_missing(self):
        md = self.write_skill("do-thing", "---\nname: do-thing\n---\n")
        self.assert_error_contains(validate_skills.check(md), "`description` is missing")

    def test_description_empty(self):
        md = self.write_skill("do-thing", '---\nname: do-thing\ndescription: ""\n---\n')
        self.assert_error_contains(validate_skills.check(md), "`description` is missing")

    def test_description_plain_scalar(self):
        md = self.write_skill("do-thing", "---\nname: do-thing\ndescription: plain text\n---\n")
        self.assert_error_contains(validate_skills.check(md), "double-quoted")

    def test_description_single_quoted(self):
        md = self.write_skill("do-thing", "---\nname: do-thing\ndescription: 'single'\n---\n")
        self.assert_error_contains(validate_skills.check(md), "double-quoted")

    def test_description_single_quoted_starting_with_double_quote(self):
        md = self.write_skill("do-thing", "---\nname: do-thing\ndescription: '\"x\"'\n---\n")
        self.assert_error_contains(validate_skills.check(md), "double-quoted")


if __name__ == "__main__":
    unittest.main()
