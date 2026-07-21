#!/usr/bin/env python3
"""Unit tests for scripts/validate_marketplace.py.

Standard library only (unittest), matching test_validate_skills.py. The module
under test reads REPO_ROOT-relative paths, so each test points its module-level
path constants at a temporary tree it builds, then restores them.

Run: python -m unittest discover -s tests -p "test_*.py"
"""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "validate_marketplace.py"
_spec = importlib.util.spec_from_file_location("validate_marketplace", _SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load validate_marketplace module from {_SCRIPT}")
validate_marketplace = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(validate_marketplace)


def _bundle_entry(name: str = "inumberx-skills") -> dict:
    return {"name": name, "source": "./", "description": f"{name} bundle"}


def _skill_entry(name: str) -> dict:
    return {"name": name, "source": f"./skills/{name}", "description": f"{name} plugin"}


def _catalog(skill_names: list[str], *, bundle: bool = True) -> dict:
    plugins = []
    if bundle:
        plugins.append(_bundle_entry())
    plugins.extend(_skill_entry(n) for n in skill_names)
    return {
        "name": "inumberx-skills",
        "owner": {"name": "InumberX"},
        "plugins": plugins,
    }


class TestCheck(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".claude-plugin").mkdir()
        (self.root / "skills").mkdir()
        # Redirect the module's path constants at the temp tree.
        self._saved = (
            validate_marketplace.REPO_ROOT,
            validate_marketplace.SKILLS_DIR,
            validate_marketplace.MARKETPLACE,
        )
        validate_marketplace.REPO_ROOT = self.root
        validate_marketplace.SKILLS_DIR = self.root / "skills"
        validate_marketplace.MARKETPLACE = self.root / ".claude-plugin" / "marketplace.json"

    def tearDown(self):
        (
            validate_marketplace.REPO_ROOT,
            validate_marketplace.SKILLS_DIR,
            validate_marketplace.MARKETPLACE,
        ) = self._saved
        self._tmp.cleanup()

    def _make_skill(self, name: str) -> None:
        d = self.root / "skills" / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "SKILL.md").write_text(f'---\nname: {name}\ndescription: "x"\n---\n', encoding="utf-8")

    def _write_catalog(self, obj) -> None:
        text = obj if isinstance(obj, str) else json.dumps(obj)
        validate_marketplace.MARKETPLACE.write_text(text, encoding="utf-8")

    def test_in_sync_with_bundle_passes(self):
        for n in ("create-pr", "review-pr"):
            self._make_skill(n)
        self._write_catalog(_catalog(["create-pr", "review-pr"]))
        self.assertEqual(validate_marketplace.check(), [])

    def test_in_sync_without_bundle_passes(self):
        # The bundle is optional; per-skill-only catalogs are still valid.
        self._make_skill("create-pr")
        self._write_catalog(_catalog(["create-pr"], bundle=False))
        self.assertEqual(validate_marketplace.check(), [])

    def test_bundle_does_not_count_as_a_skill(self):
        # A bundle entry alongside its skills must not be flagged as stale, and
        # must not satisfy the sync check on its own.
        self._make_skill("create-pr")
        self._write_catalog(_catalog(["create-pr"]))
        self.assertEqual(validate_marketplace.check(), [])

    def test_bundle_with_no_skills_is_flagged(self):
        self._write_catalog({"name": "inumberx-skills", "owner": {"name": "X"}, "plugins": [_bundle_entry()]})
        errs = validate_marketplace.check()
        self.assertTrue(any("bundle source has no skills" in e for e in errs))

    def test_source_must_start_with_dot_slash(self):
        self._make_skill("create-pr")
        cat = _catalog(["create-pr"], bundle=False)
        cat["plugins"][0]["source"] = "skills/create-pr"  # missing ./
        self._write_catalog(cat)
        errs = validate_marketplace.check()
        self.assertTrue(any("must start with './'" in e for e in errs))

    def test_source_escaping_repo_is_flagged(self):
        # "./../…" resolves outside the repo root and must be rejected before the
        # SKILL.md / name checks can be fooled by files outside this repository.
        self._make_skill("create-pr")
        cat = _catalog(["create-pr"], bundle=False)
        cat["plugins"][0]["source"] = "./../evil"
        self._write_catalog(cat)
        errs = validate_marketplace.check()
        self.assertTrue(any("resolves outside the repository" in e for e in errs))

    def test_per_skill_source_outside_skills_dir_is_flagged(self):
        # A source inside the repo but not under skills/<name> must be rejected
        # even when a SKILL.md sits there, so it can't ship the wrong contents.
        (self.root / "create-pr").mkdir()
        (self.root / "create-pr" / "SKILL.md").write_text(
            '---\nname: create-pr\ndescription: "x"\n---\n', encoding="utf-8"
        )
        self._make_skill("create-pr")  # the real one under skills/
        cat = _catalog([], bundle=False)
        cat["plugins"] = [{"name": "create-pr", "source": "./create-pr", "description": "x"}]
        self._write_catalog(cat)
        errs = validate_marketplace.check()
        self.assertTrue(any("must be './skills/<name>'" in e for e in errs))

    def test_missing_file(self):
        errs = validate_marketplace.check()
        self.assertTrue(any("missing" in e for e in errs))

    def test_invalid_json(self):
        self._write_catalog("{ not json")
        errs = validate_marketplace.check()
        self.assertTrue(any("not valid JSON" in e for e in errs))

    def test_skill_without_entry_is_flagged(self):
        self._make_skill("create-pr")
        self._make_skill("review-pr")
        self._write_catalog(_catalog(["create-pr"]))  # review-pr unpublished
        errs = validate_marketplace.check()
        self.assertTrue(any("without a per-skill marketplace entry" in e and "review-pr" in e for e in errs))

    def test_stale_entry_is_flagged(self):
        self._make_skill("create-pr")
        self._write_catalog(_catalog(["create-pr", "ghost"]))  # ghost has no skill dir
        errs = validate_marketplace.check()
        self.assertTrue(any("no matching skill" in e and "ghost" in e for e in errs))
        self.assertTrue(any("no SKILL.md" in e for e in errs))

    def test_name_source_mismatch(self):
        self._make_skill("create-pr")
        self._make_skill("other")
        cat = _catalog([], bundle=False)
        cat["plugins"] = [{"name": "create-pr", "source": "./skills/other", "description": "x"}]
        self._write_catalog(cat)
        errs = validate_marketplace.check()
        self.assertTrue(any("must match its source directory" in e for e in errs))

    def test_non_kebab_name(self):
        self._make_skill("create-pr")
        cat = _catalog(["create-pr"])
        cat["name"] = "Inumberx_Skills"
        self._write_catalog(cat)
        errs = validate_marketplace.check()
        self.assertTrue(any("kebab-case" in e for e in errs))

    def test_missing_owner(self):
        self._make_skill("create-pr")
        cat = _catalog(["create-pr"])
        del cat["owner"]
        self._write_catalog(cat)
        errs = validate_marketplace.check()
        self.assertTrue(any("owner.name" in e for e in errs))

    def test_duplicate_entries(self):
        self._make_skill("create-pr")
        cat = _catalog(["create-pr"])
        cat["plugins"].append(_skill_entry("create-pr"))
        self._write_catalog(cat)
        errs = validate_marketplace.check()
        self.assertTrue(any("duplicate" in e for e in errs))


if __name__ == "__main__":
    unittest.main()
