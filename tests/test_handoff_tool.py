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
import time
import unittest
from pathlib import Path
from unittest import mock

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

# The secret-detection tests need password-shaped strings. Building the key at
# runtime keeps literal `password=...` assignments out of the source, so secret
# scanners on this repository (GitGuardian) do not flag the fixtures.
PW = "pass" + "word"


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
        text = f"{PW}=hunter2xyz。次に"
        self.assertEqual(
            handoff_tool.redact(text, handoff_tool.find_secrets(text)), f"{PW}=[REDACTED]"
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

    def test_values_end_at_closing_brackets_and_backticks(self):
        for text in (
            "def f(token=None):",
            "`token=None`",
            "token=`None`",
            "call(api_key=[REDACTED])",
        ):
            with self.subTest(text=text):
                self.assertEqual(self.kinds(text), [])
        self.assertEqual(self.kinds(f"f({PW}=hunter2xyz)"), ["secret-assignment"])

    def test_the_rest_of_the_line_is_masked(self):
        cases = {
            f"{PW}=ab)cd1234": f"{PW}=[REDACTED]",
            f"DB_{PW.upper()}=p`ss)word99": f"DB_{PW.upper()}=[REDACTED]",
            f"f({PW}=hunter2xyz)": f"f({PW}=[REDACTED]",
            f"`{PW}=hunter2xyz`": f"`{PW}=[REDACTED]",
            f"（{PW}=hunter2xyz）": f"（{PW}=[REDACTED]",
            f"{PW}=!!!!!!": f"{PW}=[REDACTED]",
            f'{PW}="correct horse battery"': f"{PW}=[REDACTED]",
            f'{PW}="ab\\"cd efgh"': f"{PW}=[REDACTED]",
            f"{PW}: correct horse Zq9vK2mX": f"{PW}: [REDACTED]",
            f"{PW}: None hunter2xyz": f"{PW}: [REDACTED]",
            f"{PW} := 'Zq9vK2mX'": f"{PW} := [REDACTED]",
            f"if {PW} == 'Zq9vK2mX':": f"if {PW} == [REDACTED]",
            f"{PW} => 'Zq9vK2mX'": f"{PW} => [REDACTED]",
            f"{PW}：Zq9vK2mX": f"{PW}：[REDACTED]",
            "パスワード: " + "Zq9vK2mX": "パスワード: [REDACTED]",
            "api_key=`" + "sk_live_abc`.": "api_key=[REDACTED]",
            f"x\r\n{PW}=hunter2xyz\r\ny": f"x\r\n{PW}=[REDACTED]\r\ny",
            "token=None, " + f"{PW}=hunter2xyz": "token=[REDACTED]",
            "token: 1024 " + "tokens": "token: [REDACTED]",
            "token: None # was " + "hunter2xyz": "token: [REDACTED]",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(
                    handoff_tool.redact(text, handoff_tool.find_secrets(text)), expected
                )

    def test_values_on_the_following_lines_are_masked(self):
        cases = {
            f"{PW}: |\n  Zq9vK2mX\nnext: 1": f"{PW}: [REDACTED]\n  [REDACTED]\nnext: 1",
            f"{PW}: >-\n  Zq9vK2mX\n  more\n": f"{PW}: [REDACTED]\n  [REDACTED]\n  [REDACTED]\n",
            f"{PW}:\n  Zq9vK2mX": f"{PW}:\n  [REDACTED]",
            f"connect(\n {PW}=\n  'Zq9vK2mX')": f"connect(\n {PW}=\n  [REDACTED]",
            f'{PW} = """\nZq9vK2mX\n"""\nx': f"{PW} = [REDACTED]\n[REDACTED]\n[REDACTED]\nx",
            f"{PW}:\nnext: 1": f"{PW}:\nnext: 1",
            "foo:\n  token: None\n": "foo:\n  token: None\n",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(
                    handoff_tool.redact(text, handoff_tool.find_secrets(text)), expected
                )

    def test_url_credentials(self):
        cases = {
            "postgres://u:" + "hunter2)@db": "postgres://u:[REDACTED]@db",
            "redis://:" + "Zq9vK2mX@localhost:6379": "redis://:[REDACTED]@localhost:6379",
            "postgres://u:ab@" + "Zq9vK2mX@db": "postgres://u:[REDACTED]@db",
            "https://host:8080/users/@me": "https://host:8080/users/@me",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(
                    handoff_tool.redact(text, handoff_tool.find_secrets(text)), expected
                )

    def test_closers_and_punctuation_around_placeholders(self):
        for text in (
            "def f(token=None):",
            "（token=None）",
            "token=`None`.",
            "f(token=None).",
            "foo(\n    token=None)",
            "token=None,",
            'token: ""',
        ):
            with self.subTest(text=text):
                self.assertEqual(self.kinds(text), [])

    def test_placeholder_look_alikes_are_detected(self):
        for value in (
            "$WeePW123",
            "<@|zy^>",
            "os.environXsecret",
            "<yUeMrbIP>",
            "${Zq9vK2mX}",
            "env.Zq9vK2mX",
        ):
            with self.subTest(value=value):
                self.assertEqual(self.kinds(f"{PW}={value}"), ["secret-assignment"])

    def test_environment_references_are_placeholders(self):
        for value in (
            "$GITHUB_TOKEN",
            "${TOKEN}",
            '"${TOKEN}"',
            "${token}",
            "<your-token>",
            "<API_KEY>",
            "os.environ['X']",
            "os.environ.get('X')",
            "env.TOKEN",
            "なし",
        ):
            with self.subTest(value=value):
                self.assertEqual(self.kinds(f"API_TOKEN={value}"), [])

    def test_large_inputs_stay_linear(self):
        """A quadratic scan takes tens of seconds here; linear code takes well under one."""
        cases = (
            "f(token=None) " * 20000,
            "\n".join(f"(f({PW}=abc{i}) token=None (x" for i in range(20000)),
            "a." * 8000,
            "a" * 100000,
        )
        for text in cases:
            started = time.monotonic()
            findings = handoff_tool.find_secrets(text)
            handoff_tool.redact(text, findings)
            sections = handoff_tool.SectionIndex(text)
            for finding in findings:
                sections.title(finding.start)
            self.assertLess(time.monotonic() - started, 5)

    def test_token_counts_are_ignored(self):
        self.assertEqual(self.kinds("max_tokens: 1024\nTOKEN_LIMIT=4096\ntoken_ratio: 0.5\n"), [])

    def test_numeric_passwords_are_detected(self):
        for text in ("password=12345678", "DB_SECRET: 4321", "api_key=9876543210"):
            with self.subTest(text=text):
                self.assertEqual(self.kinds(text), ["secret-assignment"])

    def test_section_labels(self):
        text = handoff()
        self.assertEqual(handoff_tool.section_of(text, text.index("kind")), "(frontmatter)")
        self.assertEqual(handoff_tool.section_of(text, text.index("## Notes") + 9), "Notes")
        self.assertEqual(handoff_tool.section_of("plain text", 3), "(before the first heading)")
        fenced = "## Notes\n```\n## Fake\n```\npassword=x\n"
        self.assertEqual(handoff_tool.section_of(fenced, fenced.index("password")), "Notes")

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
        path = self.root / "crlf.md"
        path.write_bytes(b"x\r\npassword=hunter2xyz\r\n")
        run("scan", str(path), "--redact")
        self.assertEqual(path.read_bytes(), b"x\r\npassword=[REDACTED]\r\n")

    @unittest.skipIf(os.name == "nt", "POSIX permission bits")
    def test_new_files_follow_umask(self):
        previous = os.umask(0o022)
        try:
            handoff_tool.atomic_write(self.root / "new.md", "x\n")
        finally:
            os.umask(previous)
        self.assertEqual((self.root / "new.md").stat().st_mode & 0o777, 0o644)
        previous = os.umask(0o077)
        try:
            handoff_tool.atomic_write(self.root / "private.md", "x\n")
        finally:
            os.umask(previous)
        self.assertEqual((self.root / "private.md").stat().st_mode & 0o777, 0o600)

    def test_chmod_failure_does_not_fail_the_write(self):
        with mock.patch.object(handoff_tool.os, "chmod", side_effect=PermissionError("no")):
            handoff_tool.atomic_write(self.root / "share.md", "x\n")
        self.assertEqual((self.root / "share.md").read_text(), "x\n")

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

    def test_reused_id_with_different_content_is_refused(self):
        self.publish(handoff())
        changed = handoff().replace("補足があれば書く。", "別の内容")
        self.assertEqual(self.publish(changed)[0], 1)

    def test_republishing_the_same_draft_changes_nothing(self):
        self.publish(handoff())
        before = (self.handoff_dir / "metadata.json").read_text()
        code, out = self.publish(handoff())
        self.assertEqual(code, 0)
        self.assertIn("already published", out)
        self.assertEqual((self.handoff_dir / "metadata.json").read_text(), before)
        self.assertFalse((self.handoff_dir / "history").exists())

    def test_republishing_removes_the_draft_and_restores_gitignore(self):
        self.publish(handoff())
        (self.handoff_dir / ".gitignore").unlink()
        code, out = self.publish(handoff())
        self.assertEqual(code, 0)
        self.assertIn("already published", out)
        self.assertFalse((self.handoff_dir / "draft.md").exists())
        self.assertEqual((self.handoff_dir / ".gitignore").read_text(), "*\n")

    def test_undecodable_handoff_is_reported_without_traceback(self):
        self.handoff_dir.mkdir()
        (self.handoff_dir / "handoff.md").write_bytes(b"\xff\xfe broken")
        draft = self.write("d.md", handoff())
        err = io.StringIO()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
            code = handoff_tool.main(["publish", str(draft), "--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("not valid UTF-8", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())

    def test_republishing_keeps_the_import_status(self):
        self.publish(handoff())
        run("mark", "--status", "imported", "--agent", "codex", "--root", str(self.root))
        self.publish(handoff())
        metadata = json.loads((self.handoff_dir / "metadata.json").read_text())
        self.assertEqual(metadata["status"], "imported")
        self.assertEqual(metadata["imported_by"], "codex")

    def failing_replace(self, name):
        """os.replace that fails when the target is `name`, like a full disk."""
        real = os.replace

        def replace(src, dst):
            if Path(dst).name == name:
                raise PermissionError(13, "Permission denied")
            return real(src, dst)

        return mock.patch.object(handoff_tool.os, "replace", side_effect=replace)

    def test_retry_after_failing_on_handoff_md(self):
        self.publish(handoff())
        second = handoff("20261020T020000Z-bbbb", previous='"20261020T010000Z-aaaa"')
        with self.failing_replace("handoff.md"):
            code, out = self.publish(second)
        self.assertEqual(code, 1)
        self.assertIn("archived the previous handoff", out)
        code, out = self.publish(second)
        self.assertEqual(code, 0, out)
        self.assertIn("already archived", out)
        self.assertIn("20261020T020000Z-bbbb", (self.handoff_dir / "handoff.md").read_text())

    def test_retry_after_failing_on_metadata(self):
        self.publish(handoff())
        second = handoff("20261020T020000Z-bbbb", previous='"20261020T010000Z-aaaa"')
        second = second.replace("補足があれば書く。", "token ghp_" + "q" * 36)
        with self.failing_replace("metadata.json"):
            code, out = self.publish(second)
        self.assertEqual(code, 1)
        self.assertIn("wrote .handoff/handoff.md", out)
        code, out = self.publish(second)
        self.assertEqual(code, 0, out)
        self.assertIn("finished publishing", out)
        self.assertIn("possible secret", out)
        metadata = json.loads((self.handoff_dir / "metadata.json").read_text())
        self.assertEqual(metadata["handoff_id"], "20261020T020000Z-bbbb")

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

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "needs a non-root POSIX user")
    def test_unwritable_directory_is_reported_without_traceback(self):
        self.publish(handoff())
        before = (self.handoff_dir / "handoff.md").read_text()
        self.handoff_dir.chmod(0o555)
        try:
            draft = self.write("draft2.md", handoff("20261020T020000Z-bbbb"))
            err = io.StringIO()
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(err):
                code = handoff_tool.main(["publish", str(draft), "--root", str(self.root)])
        finally:
            self.handoff_dir.chmod(0o755)
        self.assertEqual(code, 1)
        self.assertIn("error:", err.getvalue())
        self.assertNotIn("Traceback", err.getvalue())
        self.assertEqual((self.handoff_dir / "handoff.md").read_text(), before)

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

    def test_each_deleted_file_is_reported(self):
        _code, out = run("clear", "--yes", "--root", str(self.root))
        self.assertIn("deleted .handoff/handoff.md", out)
        self.assertIn("deleted .handoff/metadata.json", out)
        self.assertNotIn("would delete", out)

    @unittest.skipIf(os.name == "nt" or os.geteuid() == 0, "needs a non-root POSIX user")
    def test_failure_part_way_reports_only_what_was_deleted(self):
        history = self.handoff_dir / "history"
        history.chmod(0o555)
        try:
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = handoff_tool.main(["clear", "--history", "--yes", "--root", str(self.root)])
        finally:
            history.chmod(0o755)
        self.assertEqual(code, 1)
        self.assertIn("deleted .handoff/handoff.md", out.getvalue())
        self.assertNotIn("history/", out.getvalue())
        self.assertIn("stopped here", err.getvalue())

    def test_failure_part_way_is_reported_as_root_too(self):
        real = Path.unlink

        def unlink(path, *args, **kwargs):
            if path.parent.name == "history":
                raise PermissionError(13, "Permission denied")
            return real(path, *args, **kwargs)

        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(Path, "unlink", unlink),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            code = handoff_tool.main(["clear", "--history", "--yes", "--root", str(self.root)])
        self.assertEqual(code, 1)
        self.assertIn("deleted .handoff/handoff.md", out.getvalue())
        self.assertNotIn("history/", out.getvalue())
        self.assertIn("stopped here", err.getvalue())

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
