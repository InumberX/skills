#!/usr/bin/env python3
"""Unit tests for skills/hand-off-context/scripts/handoff_tool.py.

The script ships inside the skill and must run with the standard library only,
so these tests use only unittest as well. The module is loaded by path via
importlib, like the other test modules here. Tests that need Git create a
throwaway repository and are skipped when git is not installed.

Run: python -m unittest discover -s tests -p "test_*.py"
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_SKILL = Path(__file__).resolve().parent.parent / "skills" / "hand-off-context"
_SCRIPT = _SKILL / "scripts" / "handoff_tool.py"
_spec = importlib.util.spec_from_file_location("handoff_tool", _SCRIPT)
if _spec is None or _spec.loader is None:
    raise ImportError(f"cannot load handoff_tool module from {_SCRIPT}")
handoff_tool = importlib.util.module_from_spec(_spec)
# dataclasses resolves string annotations through sys.modules.
sys.modules["handoff_tool"] = handoff_tool
_spec.loader.exec_module(handoff_tool)

HAS_GIT = shutil.which("git") is not None


def handoff(handoff_id="20261020T010000Z-aaaa", previous="null", kind='"handoff"'):
    """A valid Handoff File built from the shipped template."""
    text = (_SKILL / "templates" / "handoff.md").read_text(encoding="utf-8")
    text = text.replace('"YYYYMMDDTHHMMSSZ-xxxx"', f'"{handoff_id}"')
    text = text.replace("previous_handoff_id: null", f"previous_handoff_id: {previous}")
    text = text.replace('kind: "handoff"', f"kind: {kind}")
    text = text.replace("YYYY-MM-DDTHH:MM:SSZ", "2026-10-20T01:00:00Z")
    text = text.replace("full-commit-sha", "0" * 40)
    return text


def run(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = handoff_tool.main(list(argv))
    return code, out.getvalue()


def git(root, *args):
    subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=root,
        check=True,
        capture_output=True,
    )


class TempDirTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.handoff_dir = self.root / ".handoff"

    def tearDown(self):
        self._tmp.cleanup()

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path


class TestFrontmatter(unittest.TestCase):
    def report_for(self, text):
        report = handoff_tool.Report()
        lines, _body = handoff_tool.split_frontmatter(text)
        data = handoff_tool.parse_frontmatter(lines, report)
        handoff_tool.check_frontmatter(data, report)
        return data, report

    def test_template_values_parse(self):
        data, report = self.report_for(handoff())
        self.assertEqual(report.errors, [])
        self.assertIsNone(data["previous_handoff_id"])
        self.assertIs(data["dirty"], False)
        self.assertEqual(data["created_at"], "2026-10-20T01:00:00Z")

    def test_byte_order_mark_is_ignored(self):
        data, report = self.report_for("\ufeff" + handoff())
        self.assertEqual(report.errors, [])
        self.assertEqual(data["kind"], "handoff")

    def test_missing_block(self):
        self.assertIsNone(handoff_tool.split_frontmatter("# Handoff\n"))
        self.assertIsNone(handoff_tool.split_frontmatter("---\nkind: x\n"))

    def test_missing_field_is_an_error(self):
        _data, report = self.report_for(handoff().replace('project: "project-name"\n', ""))
        self.assertTrue(any("project" in e for e in report.errors))

    def test_unsupported_schema_version(self):
        text = handoff().replace('schema_version: "1.0"', 'schema_version: "2.0"')
        _data, report = self.report_for(text)
        self.assertTrue(report.unsupported)
        self.assertFalse(report.ok)

    def test_invalid_kind(self):
        _data, report = self.report_for(handoff(kind='"summary"'))
        self.assertTrue(any("kind" in e for e in report.errors))

    def test_nested_value_is_rejected(self):
        text = handoff().replace('branch: "branch-name"', 'git:\n  branch: "x"')
        _data, report = self.report_for(text)
        self.assertTrue(any("flat" in e for e in report.errors))

    def test_dirty_must_be_boolean_or_unknown(self):
        _data, report = self.report_for(handoff().replace("dirty: false", 'dirty: "maybe"'))
        self.assertTrue(any("dirty" in e for e in report.errors))
        _data, report = self.report_for(handoff().replace("dirty: false", 'dirty: "Unknown"'))
        self.assertEqual(report.errors, [])

    def test_malformed_id_and_short_sha_are_warnings(self):
        text = handoff(handoff_id="20261020-001").replace("0" * 40, "abc1234")
        _data, report = self.report_for(text)
        self.assertEqual(report.errors, [])
        self.assertEqual(len(report.warnings), 2)

    def test_unquoted_string_warns(self):
        _data, report = self.report_for(handoff().replace('"project-name"', "project-name"))
        self.assertTrue(any("double-quoted" in w for w in report.warnings))

    def test_value_containing_colon(self):
        data, _report = self.report_for(handoff())
        self.assertEqual(data["created_at"], "2026-10-20T01:00:00Z")


class TestSections(unittest.TestCase):
    def check(self, text):
        _data, _body, report = self.load(text)
        return report

    def load(self, text):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "h.md"
            path.write_text(text, encoding="utf-8")
            return handoff_tool.load_handoff(path)

    def test_template_has_every_section(self):
        self.assertEqual(self.check(handoff()).warnings, [])

    def test_missing_section_is_a_warning(self):
        report = self.check(handoff().replace("## Known Issues\n", ""))
        self.assertTrue(report.ok)
        self.assertTrue(any("Known Issues" in w for w in report.warnings))

    def test_review_requires_review_findings(self):
        text = handoff(kind='"review"').replace("## Review Findings\n", "")
        self.assertTrue(any("Review Findings" in w for w in self.check(text).warnings))

    def test_headings_inside_code_fences_do_not_count(self):
        text = handoff().replace("## Next Actions\n", "```text\n## Next Actions\n```\n")
        self.assertTrue(any("Next Actions" in w for w in self.check(text).warnings))

    def test_section_items_count_top_level_only(self):
        body = "### In Progress\n\n- a\n  - detail 1\n  - detail 2\n- b\n"
        self.assertEqual(handoff_tool.section_items(body, "In Progress"), ["a", "b"])

    def test_section_items_skip_none(self):
        body = "### Pending\n\n- one\n- None\n1. two\n\n## Other\n\n- three\n"
        self.assertEqual(handoff_tool.section_items(body, "Pending"), ["one", "two"])


class TestClassify(unittest.TestCase):
    def test_codes(self):
        cases = {
            "??": ("Untracked", "Untracked"),
            "M ": ("Modified", "Staged"),
            " M": ("Modified", "Unstaged"),
            "MM": ("Modified", "Both"),
            "A ": ("Added", "Staged"),
            "AM": ("Added", "Both"),
            " D": ("Deleted", "Unstaged"),
            "R ": ("Renamed", "Staged"),
            "C ": ("Added", "Staged"),
            " T": ("Modified", "Unstaged"),
            "UU": ("Conflicted", "Both"),
            "AA": ("Conflicted", "Both"),
            "DD": ("Conflicted", "Both"),
            "UD": ("Conflicted", "Both"),
        }
        for xy, expected in cases.items():
            with self.subTest(xy=xy):
                self.assertEqual(handoff_tool.classify(xy), expected)

    def test_table_limit_and_escaping(self):
        files = [handoff_tool.ChangedFile(f"a|{i}.txt", "Added", "Staged") for i in range(3)]
        table, left_out = handoff_tool.changed_files_table(files, 2)
        self.assertEqual(left_out, 1)
        self.assertIn("a\\|0.txt", table)
        self.assertEqual(table.count("\n"), 3)
        self.assertEqual(handoff_tool.changed_files_table([], 100), ("None", 0))


@unittest.skipUnless(HAS_GIT, "git is not installed")
class TestGit(TempDirTest):
    def setUp(self):
        super().setUp()
        git(self.root, "init", "-q")

    def test_unborn_repository(self):
        info = handoff_tool.git_info(self.root)
        self.assertEqual(info["commit"], "Unknown")
        self.assertIs(info["dirty"], False)

    def test_changed_files_and_info(self):
        self.write("old.txt", "x\n")
        git(self.root, "add", "old.txt")
        git(self.root, "commit", "-q", "-m", "init")
        git(self.root, "mv", "old.txt", "new name.txt")
        self.write("untracked.txt", "y\n")
        self.write(".handoff/handoff.md", "ignored\n")

        files = handoff_tool.changed_files(self.root)
        by_path = {f.path: f for f in files}
        self.assertEqual(set(by_path), {"new name.txt", "untracked.txt"})
        self.assertEqual(by_path["new name.txt"].status, "Renamed")
        self.assertEqual(by_path["new name.txt"].original, "old.txt")

        info = handoff_tool.git_info(self.root)
        self.assertRegex(info["commit"], r"^[0-9a-f]{40}$")
        self.assertIs(info["dirty"], True)

    def test_detached_head_branch_is_unknown(self):
        git(self.root, "commit", "-q", "--allow-empty", "-m", "init")
        git(self.root, "checkout", "-q", "--detach")
        self.assertEqual(handoff_tool.git_info(self.root)["branch"], "Unknown")


class TestNotGit(TempDirTest):
    def test_outside_git(self):
        if (
            HAS_GIT
            and subprocess.run(
                ["git", "rev-parse", "--is-inside-work-tree"], cwd=self.root, capture_output=True
            ).returncode
            == 0
        ):
            self.skipTest("the temporary directory is inside a Git work tree")
        self.assertIsNone(handoff_tool.changed_files(self.root))
        self.assertEqual(handoff_tool.git_info(self.root)["dirty"], "Unknown")


class TestInfo(unittest.TestCase):
    def test_id_matches_created_at(self):
        created_at = handoff_tool.utc_now()
        self.assertRegex(created_at, handoff_tool.ISO_8601)
        handoff_id = handoff_tool.new_handoff_id(created_at)
        self.assertRegex(handoff_id, handoff_tool.HANDOFF_ID)
        self.assertTrue(handoff_id.startswith(re.sub(r"[-:]", "", created_at)))


class TestSecrets(unittest.TestCase):
    def kinds(self, text):
        return [f.kind for f in handoff_tool.find_secrets(text)]

    def test_known_token_shapes(self):
        samples = {
            "aws-access-key": "AKIA" + "A" * 16,
            "github-token": "ghp_" + "a" * 36,
            "anthropic-api-key": "sk-ant-" + "a" * 30,
            "openai-api-key": "sk-proj-" + "a" * 30,
            "slack-token": "xoxb-" + "1" * 12,
            "google-api-key": "AIza" + "a" * 35,
            "jwt": "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12,
        }
        for kind, sample in samples.items():
            with self.subTest(kind=kind):
                self.assertEqual(self.kinds(f"value {sample} end"), [kind])

    def test_tokens_next_to_japanese_text(self):
        token = "ghp_" + "a" * 36
        self.assertEqual(self.kinds(f"トークンは{token}です"), ["github-token"])
        text = "password=hunter2xyz。次に"
        self.assertEqual(
            handoff_tool.redact(text, handoff_tool.find_secrets(text)), "password=[REDACTED]。次に"
        )

    def test_overlap_reports_once(self):
        self.assertEqual(self.kinds("sk-ant-" + "a" * 30), ["anthropic-api-key"])

    def test_private_key_block_is_masked_whole(self):
        text = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\nxyz\n-----END RSA PRIVATE KEY-----\nafter"
        findings = handoff_tool.find_secrets(text)
        self.assertEqual(handoff_tool.redact(text, findings), "[REDACTED]\nafter")

    def test_only_the_value_is_masked(self):
        text = "STRIPE_SECRET_KEY=sk_live_51Habc\nurl postgres://user:hunter22@db/x\n"
        redacted = handoff_tool.redact(text, handoff_tool.find_secrets(text))
        self.assertEqual(
            redacted, "STRIPE_SECRET_KEY=[REDACTED]\nurl postgres://user:[REDACTED]@db/x\n"
        )

    def test_plain_numbers_are_ignored(self):
        self.assertEqual(self.kinds("max_tokens: 1024\nTOKEN_LIMIT=4096\nratio: 0.5\n"), [])

    def test_section_labels(self):
        text = handoff()
        self.assertEqual(handoff_tool.section_of(text, text.index("kind")), "(frontmatter)")
        self.assertEqual(handoff_tool.section_of(text, text.index("## Notes") + 9), "Notes")
        self.assertEqual(handoff_tool.section_of("plain text", 3), "(before the first heading)")

    def test_placeholders_are_ignored(self):
        for value in ("xxx", "<your-token>", "${TOKEN}", "process.env.TOKEN", "[REDACTED]"):
            with self.subTest(value=value):
                self.assertEqual(self.kinds(f"API_TOKEN={value}"), [])

    def test_patterns_match_the_reference_table(self):
        """references/secret-patterns.md and the script must list the same regexes."""
        table = (_SKILL / "references" / "secret-patterns.md").read_text(encoding="utf-8")
        documented = set()
        for line in table.splitlines():
            if line.startswith("| ") and "`" in line:
                cells = line.split(" | ")
                for span in re.findall(r"`((?:[^`\\]|\\.)+)`", cells[-1]):
                    if "\\" in span or "[" in span:
                        documented.add(span.replace("\\|", "|"))
        in_script = {pattern for _kind, pattern in handoff_tool.SECRET_PATTERNS}
        self.assertEqual(documented, in_script)


class TestScanCommand(TempDirTest):
    def test_redact_keeps_line_endings(self):
        path = self.write("crlf.md", "x\r\npassword=hunter2xyz\r\n")
        path.write_bytes(b"x\r\npassword=hunter2xyz\r\n")
        run("scan", str(path), "--redact")
        self.assertEqual(path.read_bytes(), b"x\r\npassword=[REDACTED]\r\n")

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_redact_keeps_permissions(self):
        path = self.write("run.sh", "#!/bin/sh\npassword=hunter2xyz\n")
        path.chmod(0o755)
        run("scan", str(path), "--redact")
        self.assertEqual(path.stat().st_mode & 0o777, 0o755)

    def test_scan_reports_without_values_and_redacts(self):
        secret = "ghp_" + "z" * 36
        path = self.write("draft.md", f"# Handoff\n\n## Notes\n\ntoken is {secret}\n")
        code, out = run("scan", str(path))
        self.assertEqual(code, 1)
        self.assertNotIn(secret, out)
        self.assertIn("[Notes]", out)
        code, _out = run("scan", str(path), "--redact")
        self.assertEqual(code, 0)
        self.assertNotIn(secret, path.read_text(encoding="utf-8"))
        self.assertEqual(run("scan", str(path))[0], 0)


class TestPublishAndMark(TempDirTest):
    def publish(self, text):
        draft = self.write(".handoff/draft.md", text)
        return run("publish", str(draft), "--root", str(self.root))

    def test_first_publish(self):
        code, _out = self.publish(handoff())
        self.assertEqual(code, 0)
        self.assertEqual((self.handoff_dir / ".gitignore").read_text(), "*\n")
        self.assertFalse((self.handoff_dir / "draft.md").exists())
        metadata = json.loads((self.handoff_dir / "metadata.json").read_text())
        self.assertEqual(metadata["handoff_id"], "20261020T010000Z-aaaa")
        self.assertEqual(metadata["status"], "ready")

    def test_second_publish_archives_the_first(self):
        self.publish(handoff())
        first = (self.handoff_dir / "handoff.md").read_text()
        code, _out = self.publish(
            handoff("20261020T020000Z-bbbb", previous='"20261020T010000Z-aaaa"')
        )
        self.assertEqual(code, 0)
        archived = self.handoff_dir / "history" / "20261020T010000Z-aaaa.md"
        self.assertEqual(archived.read_text(), first)
        self.assertIn("20261020T020000Z-bbbb", (self.handoff_dir / "handoff.md").read_text())

    def test_invalid_draft_changes_nothing(self):
        self.publish(handoff())
        before = (self.handoff_dir / "handoff.md").read_text()
        code, _out = self.publish("# no frontmatter\n")
        self.assertEqual(code, 1)
        self.assertEqual((self.handoff_dir / "handoff.md").read_text(), before)
        self.assertFalse((self.handoff_dir / "history").exists())

    def test_reused_id_is_refused(self):
        self.publish(handoff())
        self.assertEqual(self.publish(handoff())[0], 1)

    def test_existing_archive_is_not_overwritten(self):
        self.publish(handoff())
        self.write(".handoff/history/20261020T010000Z-aaaa.md", "keep\n")
        self.assertEqual(self.publish(handoff("20261020T020000Z-bbbb"))[0], 1)
        archived = self.handoff_dir / "history" / "20261020T010000Z-aaaa.md"
        self.assertEqual(archived.read_text(), "keep\n")

    def test_malformed_id_is_refused(self):
        self.write(".handoff/handoff.md", "broken\n")
        code, out = self.publish(handoff("../../../escaped"))
        self.assertEqual(code, 1)
        self.assertIn("refused", out)
        self.assertEqual((self.handoff_dir / "handoff.md").read_text(), "broken\n")
        written = {p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()}
        self.assertEqual(written, {".handoff/handoff.md", ".handoff/draft.md"})

    def test_publish_warns_about_secrets_but_publishes(self):
        text = handoff().replace("補足があれば書く。", "token ghp_" + "q" * 36)
        code, out = self.publish(text)
        self.assertEqual(code, 0)
        self.assertIn("possible secret", out)
        self.assertNotIn("q" * 36, out)

    def test_unreadable_current_is_archived_as_invalid(self):
        self.write(".handoff/handoff.md", "broken\n")
        self.assertEqual(self.publish(handoff("20261020T020000Z-bbbb"))[0], 0)
        archived = self.handoff_dir / "history" / "invalid-20261020T020000Z-bbbb.md"
        self.assertEqual(archived.read_text(), "broken\n")

    def test_mark_imported(self):
        self.publish(handoff())
        code, _out = run(
            "mark", "--status", "imported", "--agent", "codex", "--root", str(self.root)
        )
        self.assertEqual(code, 0)
        metadata = json.loads((self.handoff_dir / "metadata.json").read_text())
        self.assertEqual(metadata["status"], "imported")
        self.assertEqual(metadata["imported_by"], "codex")
        self.assertRegex(metadata["imported_at"], handoff_tool.ISO_8601)

    def test_mark_without_handoff_changes_nothing(self):
        code, _out = run("mark", "--status", "invalid", "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertFalse(self.handoff_dir.exists())

    def test_mark_imported_requires_agent(self):
        self.assertEqual(run("mark", "--status", "imported", "--root", str(self.root))[0], 2)


class TestValidateCommand(TempDirTest):
    def test_summary_and_stale_metadata(self):
        self.write(".handoff/handoff.md", handoff())
        self.write(".handoff/metadata.json", '{"handoff_id": "other", "status": "ready"}')
        code, out = run("validate", "--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("stale", out)
        self.assertIn("in_progress:  1", out)
        self.assertIn("valid:        yes", out)

    def test_missing_file(self):
        code, out = run("validate", "--root", str(self.root))
        self.assertEqual(code, 1)
        self.assertIn("does not exist", out)


class TestClearCommand(TempDirTest):
    def setUp(self):
        super().setUp()
        self.write(".handoff/handoff.md", handoff())
        self.write(".handoff/metadata.json", "{}")
        for name in ("20261018T000000Z-aaaa", "invalid-20261019T000000Z-bbbb"):
            self.write(f".handoff/history/{name}.md", name)
        self.write(".handoff/history/20261020T000000Z-cccc.md", "c")
        self.write("src/keep.txt", "source")

    def remaining(self):
        return sorted(p.relative_to(self.root).as_posix() for p in self.root.rglob("*.*"))

    def test_dry_run_deletes_nothing(self):
        before = self.remaining()
        code, out = run("clear", "--history", "--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertIn("would delete", out)
        self.assertEqual(self.remaining(), before)

    def test_default_keeps_history(self):
        run("clear", "--yes", "--root", str(self.root))
        self.assertFalse((self.handoff_dir / "handoff.md").exists())
        self.assertEqual(len(list((self.handoff_dir / "history").iterdir())), 3)
        self.assertTrue((self.root / "src" / "keep.txt").exists())

    def test_keep_prunes_oldest_by_id(self):
        run("clear", "--keep", "1", "--yes", "--root", str(self.root))
        names = sorted(p.name for p in (self.handoff_dir / "history").iterdir())
        self.assertEqual(names, ["20261020T000000Z-cccc.md"])
        self.assertTrue((self.handoff_dir / "handoff.md").exists())

    def test_history_deletes_everything_but_sources(self):
        run("clear", "--history", "--yes", "--root", str(self.root))
        self.assertEqual(list((self.handoff_dir / "history").iterdir()), [])
        self.assertTrue((self.root / "src" / "keep.txt").exists())


if __name__ == "__main__":
    unittest.main()
