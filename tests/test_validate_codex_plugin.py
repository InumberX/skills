#!/usr/bin/env python3
"""Unit tests for scripts/validate_codex_plugin.py.

Standard library only (unittest), matching test_validate_marketplace.py. The
module under test reads REPO_ROOT-relative paths, so each test points its
module-level path constants at a temporary tree it builds, then restores them.

Run: python -m unittest discover -s tests -p "test_*.py"
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate_codex_plugin.py"
_spec = importlib.util.spec_from_file_location("validate_codex_plugin", _SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load validate_codex_plugin module from {_SCRIPT}")
validate_codex_plugin = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_codex_plugin)

_PATH_CONSTANTS = ("REPO_ROOT", "SKILLS_DIR", "MARKETPLACE", "MANIFEST", "CLAUDE_MARKETPLACE")


def _marketplace() -> dict:
    return {
        "name": "inumberx-skills",
        "interface": {"displayName": "InumberX Skills"},
        "plugins": [
            {
                "name": "inumberx-skills",
                "source": {"source": "local", "path": "./"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Coding",
            }
        ],
    }


def _manifest() -> dict:
    return {
        "name": "inumberx-skills",
        "description": "bundle",
        "skills": "./skills/",
        "interface": {"displayName": "InumberX Skills", "defaultPrompt": ["review this PR"]},
    }


class TestCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        for d in (".agents/plugins", ".codex-plugin", ".claude-plugin", "skills"):
            (self.root / d).mkdir(parents=True)
        self._saved = {n: getattr(validate_codex_plugin, n) for n in _PATH_CONSTANTS}
        validate_codex_plugin.REPO_ROOT = self.root
        validate_codex_plugin.SKILLS_DIR = self.root / "skills"
        validate_codex_plugin.MARKETPLACE = self.root / ".agents/plugins/marketplace.json"
        validate_codex_plugin.MANIFEST = self.root / ".codex-plugin/plugin.json"
        validate_codex_plugin.CLAUDE_MARKETPLACE = self.root / ".claude-plugin/marketplace.json"
        self._write(validate_codex_plugin.CLAUDE_MARKETPLACE, {"name": "inumberx-skills"})
        self._make_skill("create-pr")

    def tearDown(self):
        for name, value in self._saved.items():
            setattr(validate_codex_plugin, name, value)
        self._tmp.cleanup()

    def _make_skill(self, name: str) -> None:
        d = self.root / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f'---\nname: {name}\ndescription: "x"\n---\n', encoding="utf-8")

    @staticmethod
    def _write(path: Path, obj) -> None:
        text = obj if isinstance(obj, str) else json.dumps(obj)
        path.write_text(text, encoding="utf-8")

    def _check(self, marketplace=None, manifest=None) -> list[str]:
        self._write(validate_codex_plugin.MARKETPLACE, marketplace or _marketplace())
        self._write(validate_codex_plugin.MANIFEST, manifest or _manifest())
        return validate_codex_plugin.check()

    def _assert_error(self, errs: list[str], fragment: str) -> None:
        self.assertTrue(any(fragment in e for e in errs), f"{fragment!r} not in {errs}")

    def test_valid_distribution_passes(self):
        self.assertEqual(self._check(), [])

    def test_string_source_passes(self):
        cat = _marketplace()
        cat["plugins"][0]["source"] = "./"
        self.assertEqual(self._check(marketplace=cat), [])

    def test_missing_files(self):
        errs = validate_codex_plugin.check()
        self._assert_error(errs, "marketplace.json is missing")
        self._assert_error(errs, "plugin.json is missing")

    def test_invalid_json(self):
        self._write(validate_codex_plugin.MARKETPLACE, "{ not json")
        self._write(validate_codex_plugin.MANIFEST, _manifest())
        self._assert_error(validate_codex_plugin.check(), "not valid JSON")

    def test_marketplace_name_must_match_claude_catalog(self):
        cat = _marketplace()
        cat["name"] = "other-name"
        man = _manifest()
        man["name"] = "other-name"
        cat["plugins"][0]["name"] = "other-name"
        self._assert_error(self._check(cat, man), "must match the Claude catalog name")

    def test_manifest_name_must_match_marketplace(self):
        man = _manifest()
        man["name"] = "something-else"
        errs = self._check(manifest=man)
        self._assert_error(errs, "must match the marketplace name")
        self._assert_error(errs, "must match .codex-plugin/plugin.json")

    def test_per_skill_entry_is_rejected(self):
        # Codex cannot load a skill from a plugin rooted at skills/<name>/.
        cat = _marketplace()
        cat["plugins"].append(
            {
                "name": "create-pr",
                "source": {"source": "local", "path": "./skills/create-pr"},
                "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                "category": "Coding",
            }
        )
        errs = self._check(marketplace=cat)
        self._assert_error(errs, "exactly one bundle entry")
        self._assert_error(errs, "must be exactly './'")

    def test_non_local_source_is_rejected(self):
        cat = _marketplace()
        cat["plugins"][0]["source"] = {"source": "url", "url": "https://example.com/x.git"}
        self._assert_error(self._check(marketplace=cat), "`source` must be a local path")

    def test_policy_values_are_checked(self):
        cat = _marketplace()
        cat["plugins"][0]["policy"] = {"installation": "YES", "authentication": "NEVER"}
        errs = self._check(marketplace=cat)
        self._assert_error(errs, "policy.installation")
        self._assert_error(errs, "policy.authentication")

    def test_category_is_required(self):
        cat = _marketplace()
        del cat["plugins"][0]["category"]
        self._assert_error(self._check(marketplace=cat), "`category` is missing")

    def test_skills_path_is_required(self):
        man = _manifest()
        del man["skills"]
        self._assert_error(self._check(manifest=man), "`skills` is missing")

    def test_skills_path_must_point_at_skills_dir(self):
        man = _manifest()
        man["skills"] = "./skills/create-pr"
        self._assert_error(self._check(manifest=man), "must point at './skills/'")

    def test_skills_path_without_dot_slash_is_rejected(self):
        man = _manifest()
        man["skills"] = "skills"
        self._assert_error(self._check(manifest=man), "starting with './'")

    def test_parent_component_is_rejected(self):
        man = _manifest()
        man["interface"]["logo"] = "./../logo.png"
        self._assert_error(self._check(manifest=man), "must not contain '..'")

    def test_empty_skills_dir_is_flagged(self):
        (self.root / "skills" / "create-pr" / "SKILL.md").unlink()
        self._assert_error(self._check(), "has no */SKILL.md")

    def test_default_prompt_limits(self):
        man = _manifest()
        man["interface"]["defaultPrompt"] = ["a", "b", "c", "x" * 129]
        errs = self._check(manifest=man)
        self._assert_error(errs, "at most 3")
        self._assert_error(errs, "the limit is 128")


if __name__ == "__main__":
    unittest.main()
