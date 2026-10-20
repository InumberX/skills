#!/usr/bin/env python3
"""Deterministic helpers for the hand-off-context skill.

The skill works without this script: every step can be done with Git commands
and the agent's own file tools (see rules/*.md). When Python 3.10+ is
available, this script takes over the parts that are easy to get subtly wrong
by hand — reading Git state, mapping `git status` to the Changed Files table,
validating a Handoff File, detecting secrets, and writing files atomically.

Only the standard library is used, so the script runs in any project the skill
is copied into, whatever that project installs.

Subcommands (run with --help for details):
  info            Print the frontmatter values that come from the environment.
  changed-files   Print the Changed Files table built from `git status`.
  scan FILE       Report (and with --redact, mask) secrets in FILE.
  validate [FILE] Validate a Handoff File and print a status summary.
  publish DRAFT   Validate DRAFT, archive the current handoff, install DRAFT.
  mark            Record the import result in metadata.json.
  clear           List (and with --yes, delete) handoff data.

Exit codes: 0 success, 1 problems found or the operation was refused,
2 usage error.
"""

from __future__ import annotations

import argparse
import bisect
import contextlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

SCHEMA_VERSION = "1.0"
HANDOFF_DIR = ".handoff"
HANDOFF_FILE = "handoff.md"
METADATA_FILE = "metadata.json"
HISTORY_DIR = "history"
DRAFT_FILE = "draft.md"
UNKNOWN = "Unknown"
REDACTED = "[REDACTED]"
CHANGED_FILES_LIMIT = 100

HANDOFF_ID = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{4}$")
ISO_8601 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

REQUIRED_FIELDS = (
    "schema_version",
    "handoff_id",
    "previous_handoff_id",
    "kind",
    "source_agent",
    "created_at",
    "project",
    "branch",
    "commit",
    "dirty",
)
KINDS = ("handoff", "review")

# (heading level, title). Order follows references/handoff-schema.md.
REQUIRED_SECTIONS = (
    (1, "Handoff"),
    (2, "Task"),
    (2, "Context"),
    (2, "Progress"),
    (3, "Completed"),
    (3, "In Progress"),
    (3, "Pending"),
    (2, "Decisions"),
    (2, "Changed Files"),
    (2, "Validation"),
    (2, "Known Issues"),
    (2, "Next Actions"),
)
REVIEW_SECTION = (2, "Review Findings")

# Mirrors the table in references/secret-patterns.md; a unit test keeps the two
# in sync. A named group `value` means only that part is masked, so the key or
# URL around it stays readable for the next agent.
SECRET_PATTERNS: tuple[tuple[str, str], ...] = (
    ("private-key", r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ("aws-access-key", r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b"),
    ("github-token", r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{36,}\b"),
    ("github-token", r"\bgithub_pat_[A-Za-z0-9_]{22,}\b"),
    ("anthropic-api-key", r"\bsk-ant-[A-Za-z0-9_-]{20,}"),
    ("openai-api-key", r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}"),
    ("slack-token", r"\bxox[abprs]-[A-Za-z0-9-]{10,}"),
    ("google-api-key", r"\bAIza[0-9A-Za-z_-]{35}\b"),
    ("jwt", r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    # The lookbehind makes each URL start only at a token boundary, so a long run
    # of letters cannot make the engine retry the scheme at every position. The
    # user may be empty (`redis://:pw@host`) and the password runs to the last
    # "@" of the authority, so an unencoded "@" inside it is masked too.
    (
        "url-credentials",
        r"(?<![A-Za-z0-9+.-])[A-Za-z][A-Za-z0-9+.-]*://[^/\s:@]*:(?P<value>[^/\s]*)@",
    ),
)
# A secret-like key followed by a separator. Everything after the separator up
# to the end of the line is masked (see secret_assignment_findings): deciding
# where a value ends is what let parts of secrets through before.
SECRET_KEY_WORDS_PATTERN = (
    "password|passwd|secret|token|api[_-]?key|private[_-]key|credential|authorization|パスワード"
)
SECRET_ASSIGNMENT = (
    "secret-assignment",
    # The key starts at a token boundary (lookbehind) and its prefix is lazy,
    # so the engine tries one start per token instead of every position.
    # Up to four closing characters may sit between the key and the separator:
    # `config["password"] =`, `os.environ['TOKEN'] =`, `{\"password\":`.
    rf"(?i)(?<![\w.-])(?P<key>[\w.-]*?(?:{SECRET_KEY_WORDS_PATTERN})[\w.-]*)"
    r"[\\\"'`\])]{0,4}[ \t]*(?P<sep>:=|==|=>|[:=\uff1a])",
)
PRIVATE_KEY_BLOCK = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(?:-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S
)
# Values that are clearly not secrets: placeholders, references to the
# environment, and values already masked. Each form is kept narrow and
# case-consistent, because a real secret that merely looks like a placeholder
# would be written out: `$TOKEN`, `${token}` and `<your-token>` pass, while
# `$WeePW123`, `${Zq9vK2mX}` and `<yUeMrbIP>` (mixed case) are secrets.
NAME = r"(?:[A-Z_][A-Z0-9_]*|[a-z_][a-z0-9_]*)"
PLACEHOLDER = re.compile(
    rf"^(?:x+|X+|\*+|\.{{3}}|<(?:[a-z0-9]+(?:[ _-][a-z0-9]+)*|[A-Z0-9]+(?:[ _-][A-Z0-9]+)*)>"
    rf"|\$\{{{NAME}\}}|\${NAME}|(?:process\.)?env\.{NAME}"
    r"|os\.environ(?:\[[^\]]+\]|\.get\([^)]*\))?|\[REDACTED\]"
    "|(?i:none|null|nil|unknown|true|false|undefined)|\u306a\u3057|\u672a\u8a2d\u5b9a)$"
)
# A number under a key whose only secret-like word is "token" is a count
# (`max_tokens: 1024`, `TOKEN_LIMIT=4096`), not a credential. Under any other
# word (`password=12345678`) a number can be a PIN or password, so it is kept.
SECRET_KEY_WORDS = re.compile(SECRET_KEY_WORDS_PATTERN, re.I)
NUMBER = re.compile(r"^\d+(?:\.\d+)?$")
# YAML block scalars (`|`, `>-`) and an opened triple quote put the value on the
# following lines.
# A YAML comment needs whitespace before "#": `|#abc` is a value, not a block.
BLOCK_START = re.compile(r"(?:[|>][-+0-9]*|\"\"\"|\'\'\')(?:[ \t]+#.*)?[ \t]*")
FRONTMATTER_BLOCK = re.compile(r"\A\ufeff?---[ \t]*\r?\n.*?^---[ \t]*\r?$", re.S | re.M)


# --------------------------------------------------------------------------
# Small utilities
# --------------------------------------------------------------------------


def utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_handoff_id(created_at: str) -> str:
    stamp = created_at.replace("-", "").replace(":", "")
    return f"{stamp}-{secrets.token_hex(2)}"


def git(root: Path, *args: str) -> str | None:
    """Run git in root and return stdout, or None if git fails or is missing."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.decode("utf-8", errors="replace")


def find_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    cwd = Path.cwd()
    top = git(cwd, "rev-parse", "--show-toplevel")
    return Path(top.strip()).resolve() if top else cwd.resolve()


def current_umask() -> int:
    mask = os.umask(0)
    os.umask(mask)
    return mask


def atomic_write(path: Path, text: str) -> None:
    """Write text to path via a temporary file in the same directory.

    os.replace is atomic on POSIX and Windows when source and target share a
    filesystem, so a reader never sees a half-written file. Line endings are
    written as given. An existing file keeps its permissions and a new file
    follows the umask (mkstemp alone would leave every file at 0600).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        if path.exists():
            shutil.copymode(path, tmp)
        else:
            # A new file gets the same mode as one created by the agent's own
            # file tools, so .handoff/ does not mix 0600 and 0644 files.
            # Best effort: some filesystems (network shares, FAT) refuse chmod,
            # and the mode is not worth failing the write over.
            with contextlib.suppress(OSError):
                os.chmod(tmp, 0o666 & ~current_umask())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_text(path: Path) -> str:
    # newline="" keeps CRLF as is, so rewriting a file does not change its line endings.
    with path.open(encoding="utf-8", newline="") as fh:
        return fh.read()


# --------------------------------------------------------------------------
# Handoff File parsing and validation
# --------------------------------------------------------------------------


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    unsupported: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors


def split_frontmatter(text: str) -> tuple[list[str], str] | None:
    """Return (frontmatter lines, body) or None if the block is missing."""
    # Some Windows editors and older PowerShell write a UTF-8 byte order mark.
    lines = text.removeprefix("\ufeff").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return lines[1:i], "\n".join(lines[i + 1 :])
    return None


def parse_value(raw: str) -> object:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] == '"':
        return raw[1:-1]
    return {"true": True, "false": False, "null": None}.get(raw, raw)


def parse_frontmatter(lines: list[str], report: Report) -> dict[str, object]:
    data: dict[str, object] = {}
    for number, line in enumerate(lines, start=2):
        if not line.strip():
            continue
        key, sep, raw = line.partition(":")
        key = key.strip()
        if not sep or not key or line[:1].isspace():
            report.errors.append(f"frontmatter line {number} is not a flat `key: value` pair")
            continue
        if key in data:
            report.errors.append(f"frontmatter key `{key}` appears more than once")
        value = parse_value(raw)
        if isinstance(value, str) and raw.strip() and not raw.strip().startswith('"'):
            report.warnings.append(f"frontmatter `{key}` should be a double-quoted string")
        data[key] = value
    return data


def check_frontmatter(data: dict[str, object], report: Report) -> None:
    missing = [key for key in REQUIRED_FIELDS if key not in data]
    if missing:
        report.errors.append("missing frontmatter field(s): " + ", ".join(missing))

    version = data.get("schema_version")
    if "schema_version" in data and version != SCHEMA_VERSION:
        report.unsupported = True
        report.errors.append(
            f"unsupported schema_version {version!r}; this skill reads {SCHEMA_VERSION!r} only"
        )

    if "kind" in data and data["kind"] not in KINDS:
        report.errors.append(f"`kind` must be one of {', '.join(KINDS)}, got {data['kind']!r}")

    for key in ("handoff_id", "source_agent", "created_at", "project", "branch", "commit"):
        if key in data and not (isinstance(data[key], str) and data[key]):
            report.errors.append(f"`{key}` must be a non-empty string")

    handoff_id = data.get("handoff_id")
    if isinstance(handoff_id, str) and handoff_id and not HANDOFF_ID.match(handoff_id):
        report.warnings.append(f"`handoff_id` {handoff_id!r} is not YYYYMMDDTHHMMSSZ-xxxx")

    previous = data.get("previous_handoff_id")
    if "previous_handoff_id" in data and previous is not None and not isinstance(previous, str):
        report.errors.append("`previous_handoff_id` must be a string or null")

    agent = data.get("source_agent")
    if isinstance(agent, str) and agent and not KEBAB_CASE.match(agent):
        report.warnings.append(f"`source_agent` {agent!r} is not kebab-case")

    created_at = data.get("created_at")
    if isinstance(created_at, str) and created_at and not ISO_8601.match(created_at):
        report.warnings.append(f"`created_at` {created_at!r} is not ISO 8601 with a timezone")

    commit = data.get("commit")
    if isinstance(commit, str) and commit and commit != UNKNOWN and not FULL_SHA.match(commit):
        report.warnings.append("`commit` is not a full 40-character SHA")

    if "dirty" in data and data["dirty"] not in (True, False, UNKNOWN):
        report.errors.append('`dirty` must be true, false or "Unknown"')


def headings_with_offsets(text: str) -> list[tuple[int, int, str]]:
    """(offset, level, title) of Markdown ATX headings outside fenced code blocks."""
    found: list[tuple[int, int, str]] = []
    fence: str | None = None
    offset = 0
    for line in text.splitlines(keepends=True):
        start, offset = offset, offset + len(line)
        marker = line.strip()[:3]
        if marker in ("```", "~~~"):
            if fence is None:
                fence = marker
            elif marker == fence:
                fence = None
            continue
        if fence is not None:
            continue
        match = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if match:
            found.append((start, len(match.group(1)), match.group(2)))
    return found


def headings(body: str) -> list[tuple[int, str]]:
    """Markdown ATX headings outside fenced code blocks."""
    return [(level, title) for _offset, level, title in headings_with_offsets(body)]


def check_sections(body: str, kind: object, report: Report) -> None:
    present = set(headings(body))
    required = list(REQUIRED_SECTIONS)
    if kind == "review":
        required.append(REVIEW_SECTION)
    missing = [
        f"{'#' * level} {title}" for level, title in required if (level, title) not in present
    ]
    if missing:
        report.warnings.append("missing section(s): " + ", ".join(missing))


def section_items(body: str, title: str) -> list[str]:
    """Top-level bullet or numbered items under the `### title` heading.

    Indented items are details of the item above them, not separate tasks.
    """
    items: list[str] = []
    inside = False
    for line in body.splitlines():
        match = re.match(r"^(#{1,6})\s+(.*?)\s*$", line)
        if match:
            inside = match.group(2) == title
            continue
        if inside:
            item = re.match(r"^(?:[-*+]|\d+[.)])\s+(.*\S)", line)
            if item and item.group(1).strip() not in ("None", UNKNOWN):
                items.append(item.group(1).strip())
    return items


def load_handoff(path: Path) -> tuple[dict[str, object], str, Report]:
    report = Report()
    try:
        text = read_text(path)
    except FileNotFoundError:
        report.errors.append(f"{path} does not exist")
        return {}, "", report
    except (OSError, UnicodeDecodeError) as exc:
        report.errors.append(f"cannot read {path}: {exc}")
        return {}, "", report
    split = split_frontmatter(text)
    if split is None:
        report.errors.append("missing or unterminated `---` frontmatter block")
        return {}, text, report
    lines, body = split
    data = parse_frontmatter(lines, report)
    check_frontmatter(data, report)
    if not report.unsupported:
        check_sections(body, data.get("kind"), report)
    return data, body, report


def load_metadata(path: Path) -> tuple[dict[str, object] | None, str | None]:
    """Return (metadata, problem). problem is None when the file is usable."""
    try:
        data = json.loads(read_text(path))
    except FileNotFoundError:
        return None, "metadata.json is missing"
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return None, f"metadata.json cannot be read: {exc}"
    if not isinstance(data, dict):
        return None, "metadata.json is not a JSON object"
    return data, None


def metadata_document(handoff_id: str, status: str, agent: str | None, at: str | None) -> str:
    document = {
        "schema_version": SCHEMA_VERSION,
        "handoff_id": handoff_id,
        "status": status,
        "imported_by": agent,
        "imported_at": at,
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def history_entries(handoff_dir: Path) -> list[Path]:
    history = handoff_dir / HISTORY_DIR
    if not history.is_dir():
        return []
    # Sort by the embedded id so `invalid-<id>.md` files sit at their own time.
    return sorted(history.glob("*.md"), key=lambda p: p.stem.removeprefix("invalid-"))


# --------------------------------------------------------------------------
# Git
# --------------------------------------------------------------------------

STATUS_NAMES = {
    "A": "Added",
    "M": "Modified",
    "D": "Deleted",
    "R": "Renamed",
    "C": "Added",
    "T": "Modified",
}


def classify(xy: str) -> tuple[str, str]:
    """Map a porcelain v1 XY code to (Status, Area)."""
    x, y = xy[0], xy[1]
    if xy == "??":
        return "Untracked", "Untracked"
    if "U" in xy or xy in ("AA", "DD"):
        return "Conflicted", "Both"
    if x != " " and y == " ":
        return STATUS_NAMES.get(x, "Modified"), "Staged"
    if x == " ":
        return STATUS_NAMES.get(y, "Modified"), "Unstaged"
    return STATUS_NAMES.get(x, "Modified"), "Both"


@dataclass
class ChangedFile:
    path: str
    status: str
    area: str
    original: str | None = None


def changed_files(root: Path) -> list[ChangedFile] | None:
    """Parse `git status -z`; None when root is not a Git work tree."""
    out = git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    if out is None:
        return None
    entries = out.split("\0")
    files: list[ChangedFile] = []
    i = 0
    while i < len(entries):
        entry = entries[i]
        i += 1
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        original = None
        if "R" in xy or "C" in xy:
            # With -z the original path follows as its own entry.
            original = entries[i] if i < len(entries) else None
            i += 1
        if path == HANDOFF_DIR or path.startswith(HANDOFF_DIR + "/"):
            continue
        status, area = classify(xy)
        files.append(ChangedFile(path, status, area, original))
    return files


def escape_cell(text: str) -> str:
    return text.replace("|", "\\|")


def changed_files_table(files: list[ChangedFile], limit: int) -> tuple[str, int]:
    """Return (markdown, number of files left out)."""
    if not files:
        return "None", 0
    rows = ["| File | Status | Area | Description |", "| --- | --- | --- | --- |"]
    for item in files[:limit]:
        description = f"Renamed from {escape_cell(item.original)}" if item.original else ""
        rows.append(f"| {escape_cell(item.path)} | {item.status} | {item.area} | {description} |")
    return "\n".join(rows), max(0, len(files) - limit)


def git_info(root: Path) -> dict[str, object]:
    info: dict[str, object] = {"branch": UNKNOWN, "commit": UNKNOWN, "dirty": UNKNOWN}
    if git(root, "rev-parse", "--is-inside-work-tree") is None:
        return info
    branch = (git(root, "rev-parse", "--abbrev-ref", "HEAD") or "").strip()
    if branch and branch != "HEAD":
        info["branch"] = branch
    commit = (git(root, "rev-parse", "--verify", "-q", "HEAD") or "").strip()
    if FULL_SHA.match(commit):
        info["commit"] = commit
    files = changed_files(root)
    if files is not None:
        info["dirty"] = bool(files)
    return info


# --------------------------------------------------------------------------
# Secrets
# --------------------------------------------------------------------------


@dataclass
class Finding:
    kind: str
    line: int
    start: int
    end: int


def is_token_count(key: str, value: str) -> bool:
    if not NUMBER.match(value):
        return False
    words = {word.lower() for word in SECRET_KEY_WORDS.findall(key)}
    return words == {"token"}


# A value's first word is read at most this far, so a long line without
# whitespace and with many keys stays linear. A longer word is no placeholder.
MAX_WORD = 256
WORD = re.compile(rf"\S{{1,{MAX_WORD + 1}}}")
NON_SPACE = re.compile(r"\S")
# Values on lines longer than this are masked to the end of the line without
# looking for a value continued on later lines (which needs the whole line).
MAX_ANALYSED_LINE = 4096
# A value continued on later lines is followed at most this many lines.
MAX_CONTINUATION_LINES = 200
# `src/auth/token.ts:42` is a file and line number, not a key and a value.
FILE_NAME_KEY = re.compile(r"\.[A-Za-z][A-Za-z0-9]{0,5}$")
# A following line that starts its own key: a quoted key (`"user":`) or a YAML
# key followed by whitespace or the end of the line (`next: 1`). Anything less
# clear is taken as the value and masked (`"ab:cd"`, `abc:def`).
KEY_LINE = re.compile(r"[ \t]*(?:\"[\w.-]+\"|'[\w.-]+'|[\w.-]+)[ \t]*:(?:[ \t]|$)")


def sole_word(text: str, start: int, end: int) -> tuple[str | None, bool]:
    """(first word, whether it is the only word) of text[start:end].

    Looks at no more than the first two words, so a long line costs the same as
    a short one; slicing or splitting the rest of the line on every match made
    a long single-line text quadratic.
    """
    first = WORD.search(text, start, end)
    if first is None:
        return None, False
    if len(first.group()) > MAX_WORD:
        return first.group(), False
    return first.group(), NON_SPACE.search(text, first.end(), end) is None


def is_placeholder(word: str) -> bool:
    """Whether a value's only word is a placeholder (`None`, `${TOKEN}`).

    Quotes, brackets and sentence punctuation around the word are tried off one
    at a time (`"None"`, `None):`), so `${TOKEN}` keeps its own braces. Callers
    pass only a value that is a single word: in `password: None hunter2` or
    `password: None # was hunter2` the rest of the line may hold the secret.
    Only decides whether to mask, never how much.
    """
    word = word.lstrip("\"'`(\uff08")
    while word:
        if PLACEHOLDER.match(word):
            return True
        if word[-1] not in "\"'`)\uff09]},;:.!?":
            return False
        word = word[:-1]
    return False


def bare_word(word: str) -> str:
    """A word without surrounding quotes, brackets and punctuation."""
    return word.strip("\"'`)\uff09]},;:.!?(\uff08[")


class LineIndex:
    """Line numbers and bounds by offset, computed once per text.

    Searching backwards for the previous newline on every finding made a long
    single-line text quadratic.
    """

    def __init__(self, text: str) -> None:
        self.text = text
        self.newlines = [i for i, c in enumerate(text) if c == "\n"]

    def number(self, offset: int) -> int:
        return bisect.bisect_left(self.newlines, offset) + 1

    def bounds(self, offset: int) -> tuple[int, int]:
        """(start, end) of the line containing offset, end excluding "\r\n"."""
        i = bisect.bisect_left(self.newlines, offset)
        start = self.newlines[i - 1] + 1 if i else 0
        end = self.newlines[i] if i < len(self.newlines) else len(self.text)
        if self.text[end - 1 : end] == "\r":
            end -= 1
        return start, end


def indent_of(line: str) -> int:
    """Width of the leading whitespace, with tabs expanded to 8 columns."""
    return len(line[: len(line) - len(line.lstrip(" \t"))].expandtabs(8))


def following_lines(text: str, lines: LineIndex, line_end: int):
    """(start, end, line) of up to MAX_CONTINUATION_LINES lines after line_end."""
    pos = line_end
    for _ in range(MAX_CONTINUATION_LINES):
        nl = text.find("\n", pos)
        if nl == -1:
            return
        start, end = lines.bounds(nl + 1)
        yield start, end, text[start:end]
        pos = end


BRACKETS = {"(": ")", "[": "]", "{": "}"}


def open_brackets(value: str) -> int:
    return sum(value.count(o) - value.count(c) for o, c in BRACKETS.items())


def unclosed_triple_quote(value: str) -> str | None:
    for quote in ('"""', "'''"):
        if value.count(quote) % 2 == 1:
            return quote
    return None


def continuation_spans(
    text: str,
    lines: LineIndex,
    line_start: int,
    line_end: int,
    value: str,
    empty: bool,
    by_indent: bool,
) -> list[tuple[int, int]]:
    """Spans of the following lines that carry a value continued from the key's line.

    - An unclosed triple quote: the lines up to the one that closes it.
    - Brackets left open at the end of the line (`password = (`): the lines
      until they balance.
    - A trailing backslash: the lines while each one ends in a backslash.
    - With by_indent (an empty value, a YAML block scalar, `null` with an
      indented continuation): the lines indented deeper than the key's line, skipping
      blank lines. After an empty value, a next line at the same indent that
      does not start its own key is taken as the value too (`"password":` then
      `"x"` on the next line).

    All of them stop after MAX_CONTINUATION_LINES lines.
    """

    def content(start: int, end: int, line: str) -> tuple[int, int]:
        return start + len(line) - len(line.lstrip(" \t")), end

    spans: list[tuple[int, int]] = []
    triple = unclosed_triple_quote(value)
    if triple:
        for start, end, line in following_lines(text, lines, line_end):
            if line.strip():
                spans.append(content(start, end, line))
            if triple in line:
                break
        return spans
    depth = open_brackets(value)
    # Only a line that ends inside the brackets (`password = (`, `f(password=x,`)
    # continues; an unclosed "(" in the middle of prose does not.
    if depth > 0 and value.rstrip()[-1:] in ("(", "[", "{", ","):
        for start, end, line in following_lines(text, lines, line_end):
            if line.strip():
                spans.append(content(start, end, line))
            depth += open_brackets(line)
            if depth <= 0:
                break
        return spans
    if value.rstrip().endswith("\\"):
        for start, end, line in following_lines(text, lines, line_end):
            spans.append(content(start, end, line))
            if not line.rstrip().endswith("\\"):
                break
        return spans
    if not by_indent:
        # A one-line value such as `token: rotate it` followed by an indented
        # list in prose: the list is not part of the value.
        return spans
    key_indent = indent_of(text[line_start:line_end])
    for start, end, line in following_lines(text, lines, line_end):
        if not line.strip():
            continue
        if indent_of(line) > key_indent:
            spans.append(content(start, end, line))
            continue
        if empty and not spans and not KEY_LINE.match(line):
            spans.append(content(start, end, line))
        break
    return spans


def secret_assignment_findings(text: str) -> list[Finding]:
    """Mask everything after a secret-like `key=` / `key:` to the end of the line.

    Deciding where a value ends (quotes, escapes, brackets, spaces) kept letting
    part of a secret through, so the rest of the line is masked instead; masking
    too much hides some text, masking too little writes part of a secret out.
    When the value continues on later lines (see continuation_spans), those
    lines are masked too.
    """
    findings: list[Finding] = []
    kind, pattern = SECRET_ASSIGNMENT
    lines = LineIndex(text)
    # End of the text already masked. A key inside it is masked with it; looking
    # at it again would rescan the same continuation lines once per key.
    covered = 0
    for match in re.finditer(pattern, text, re.ASCII):
        if match.start() < covered:
            continue
        line_start, line_end = lines.bounds(match.start())
        value_start = match.end()
        while value_start < line_end and text[value_start] in " \t":
            value_start += 1
        key = match.group("key")
        if (
            match.group("sep") == ":"
            and FILE_NAME_KEY.search(key)
            and text[value_start : value_start + 1].isdigit()
        ):
            continue  # `token.ts:42` is a file name and a line number
        word, single = sole_word(text, value_start, line_end)
        if line_end - value_start > MAX_ANALYSED_LINE:
            findings.append(Finding(kind, lines.number(value_start), value_start, line_end))
            covered = max(covered, line_end)
            continue
        value = text[value_start:line_end]
        empty = word is None
        skippable = single and (
            not word.strip("\"'`")  # an empty string such as `password=""`
            or is_placeholder(word)
            or is_token_count(key, bare_word(word))
        )
        block = not empty and BLOCK_START.fullmatch(value)
        by_indent = bool(empty or block or skippable)
        follows = continuation_spans(text, lines, line_start, line_end, value, empty, by_indent)
        if (empty or skippable) and not follows:
            # A placeholder or an empty value with nothing continued below it:
            # there is nothing to mask. A block opener is masked regardless, in
            # case it is not a block opener after all.
            continue
        spans = ([] if empty else [(value_start, line_end)]) + follows
        for start, end in spans:
            findings.append(Finding(kind, lines.number(start), start, end))
        covered = max(covered, spans[-1][1]) if spans else covered
    return findings


def find_secrets(text: str) -> list[Finding]:
    spans = secret_assignment_findings(text)
    lines = LineIndex(text)
    for kind, pattern in SECRET_PATTERNS:
        # ASCII mode: in Unicode mode Japanese letters count as \w, so `\b` finds no
        # boundary in "トークンはghp_..." and the token would go undetected.
        for match in re.finditer(pattern, text, re.ASCII):
            if "value" in match.re.groupindex:
                if not match.group("value") or PLACEHOLDER.match(match.group("value")):
                    continue
                start, end = match.span("value")
            elif kind == "private-key":
                block = PRIVATE_KEY_BLOCK.match(text, match.start())
                start, end = match.start(), block.end() if block else match.end()
            else:
                start, end = match.span()
            spans.append(Finding(kind, lines.number(start), start, end))
    # Merge overlapping spans instead of dropping one, so the tail of a wider
    # finding that starts later is still masked.
    spans.sort(key=lambda f: (f.start, -(f.end - f.start)))
    findings: list[Finding] = []
    for finding in spans:
        if findings and finding.start < findings[-1].end:
            findings[-1].end = max(findings[-1].end, finding.end)
            continue
        findings.append(finding)
    return findings


def redact(text: str, findings: list[Finding]) -> str:
    parts: list[str] = []
    pos = 0
    for finding in sorted(findings, key=lambda f: f.start):
        parts.append(text[pos : finding.start])
        parts.append(REDACTED)
        pos = max(pos, finding.end)
    parts.append(text[pos:])
    return "".join(parts)


class SectionIndex:
    """Section titles by offset, computed once per text (bisect per lookup)."""

    def __init__(self, text: str) -> None:
        block = FRONTMATTER_BLOCK.match(text)
        self.frontmatter_end = block.end() if block else 0
        found = headings_with_offsets(text)
        self.starts = [start for start, _level, _title in found]
        self.titles = [title for _start, _level, title in found]

    def title(self, offset: int) -> str:
        if offset < self.frontmatter_end:
            return "(frontmatter)"
        i = bisect.bisect_right(self.starts, offset)
        return self.titles[i - 1] if i else "(before the first heading)"


def section_of(text: str, offset: int) -> str:
    return SectionIndex(text).title(offset)


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------


def cmd_info(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    created_at = utc_now()
    values: dict[str, object] = {
        "handoff_id": new_handoff_id(created_at),
        "created_at": created_at,
        "project": root.name,
        **git_info(root),
    }
    for key, value in values.items():
        if isinstance(value, bool):
            print(f"{key}: {'true' if value else 'false'}")
        else:
            print(f'{key}: "{value}"')
    return 0


def cmd_changed_files(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    files = changed_files(root)
    if files is None:
        print(UNKNOWN)
        print("not a Git work tree; Changed Files is Unknown", file=sys.stderr)
        return 0
    table, left_out = changed_files_table(files, args.limit)
    print(table)
    if left_out:
        print(f"{left_out} more file(s) not listed; note the count in Notes", file=sys.stderr)
    return 0


def cmd_scan(args: argparse.Namespace) -> int:
    path = Path(args.file)
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"ERROR: cannot read {path}: {exc}", file=sys.stderr)
        return 1
    findings = find_secrets(text)
    if not findings:
        print(f"OK   no secrets detected in {path}")
        return 0
    sections = SectionIndex(text)
    for finding in findings:
        # Never print the matched value itself.
        section = sections.title(finding.start)
        print(f"FOUND line {finding.line} [{section}]: {finding.kind}")
    if args.redact:
        atomic_write(path, redact(text, findings))
        print(f"masked {len(findings)} value(s) in {path} with {REDACTED}")
        return 0
    print(f"{len(findings)} possible secret(s); re-run with --redact to mask them")
    return 1


def print_report(report: Report) -> None:
    for error in report.errors:
        print(f"ERROR   {error}")
    for warning in report.warnings:
        print(f"WARNING {warning}")


def cmd_validate(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    handoff_dir = root / HANDOFF_DIR
    path = Path(args.file) if args.file else handoff_dir / HANDOFF_FILE
    data, body, report = load_handoff(path)

    metadata: dict[str, object] | None = None
    if not args.file:
        metadata, problem = load_metadata(handoff_dir / METADATA_FILE)
        if problem:
            report.warnings.append(problem + "; handoff.md is treated as authoritative")
        elif metadata and metadata.get("handoff_id") != data.get("handoff_id"):
            report.warnings.append("metadata.json handoff_id differs from handoff.md; it is stale")

    print_report(report)
    if not data:
        return 1

    print(f"handoff_id:   {data.get('handoff_id', UNKNOWN)}")
    print(f"kind:         {data.get('kind', UNKNOWN)}")
    print(f"source_agent: {data.get('source_agent', UNKNOWN)}")
    print(f"created_at:   {data.get('created_at', UNKNOWN)}")
    print(f"project:      {data.get('project', UNKNOWN)}")
    print(f"branch:       {data.get('branch', UNKNOWN)}")
    print(f"in_progress:  {len(section_items(body, 'In Progress'))}")
    print(f"pending:      {len(section_items(body, 'Pending'))}")
    if not args.file:
        status = metadata.get("status", UNKNOWN) if metadata else UNKNOWN
        print(f"status:       {status}")
        print(f"history:      {len(history_entries(handoff_dir))}")
    print("valid:        " + ("yes" if report.ok else "no"))
    return 0 if report.ok else 1


def cmd_publish(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    handoff_dir = root / HANDOFF_DIR
    draft = Path(args.draft)
    data, _body, report = load_handoff(draft)
    if not report.ok:
        print_report(report)
        print("refused: the draft is not a valid Handoff File; nothing was changed")
        return 1

    draft_text = read_text(draft)
    sections = SectionIndex(draft_text)
    for finding in find_secrets(draft_text):
        # A safety net for a skipped `scan`; not a refusal, since some findings are false positives.
        report.warnings.append(
            f"possible secret on line {finding.line} [{sections.title(finding.start)}]:"
            f" {finding.kind}; run `scan` to review it"
        )

    new_id = str(data["handoff_id"])
    # The id becomes a file name under history/; anything but the documented
    # shape could point outside it (e.g. "../../x").
    if not HANDOFF_ID.match(new_id):
        print(f"refused: handoff_id {new_id!r} is not YYYYMMDDTHHMMSSZ-xxxx; nothing was changed")
        print("run `info` to get a new handoff_id")
        return 1
    current = handoff_dir / HANDOFF_FILE
    archive: Path | None = None
    current_text: str | None = None
    if current.exists():
        current_text = read_text(current)
        split = split_frontmatter(current_text)
        old = parse_frontmatter(split[0], Report()) if split else {}
        old_id = old.get("handoff_id")
        if old_id == new_id:
            if current_text != draft_text:
                print(
                    f"refused: the draft reuses the current handoff_id {new_id};"
                    " nothing was changed"
                )
                return 1
            metadata, problem = load_metadata(handoff_dir / METADATA_FILE)
            if problem is None and metadata and metadata.get("handoff_id") == new_id:
                # Already published, and possibly imported since: re-running must
                # not reset the status recorded by `mark`. Only tidy up what a
                # normal publish would have left behind.
                print_report(report)
                ensure_gitignore(root, handoff_dir)
                remove_draft(handoff_dir, draft)
                print(f"already published {new_id}; the handoff was not changed")
                return 0
            # An earlier publish replaced handoff.md and then failed before
            # metadata.json. Finish it instead of refusing for good.
            print_report(report)
            return finish_publish(root, handoff_dir, draft, new_id, resumed=True)
        if isinstance(old_id, str) and HANDOFF_ID.match(old_id):
            name = f"{old_id}.md"
            if data.get("previous_handoff_id") != old_id:
                report.warnings.append(
                    f"previous_handoff_id should be {old_id!r} (the handoff being replaced)"
                )
        else:
            name = f"invalid-{new_id}.md"
        archive = handoff_dir / HISTORY_DIR / name
        if archive.exists():
            if read_text(archive) == current_text:
                # An earlier publish archived this handoff and then failed before
                # replacing it. The copy is identical, so reuse it.
                print(f"already archived: {archive.relative_to(root).as_posix()}")
                archive = None
            else:
                print(f"refused: {archive} already exists; nothing was changed")
                return 1

    print_report(report)
    # Each completed write is printed, so a failure part-way says exactly how far
    # it got; re-running the same command then picks up from there.
    ensure_gitignore(root, handoff_dir)
    if archive is not None and current_text is not None:
        atomic_write(archive, current_text)
        print(f"archived the previous handoff to {archive.relative_to(root).as_posix()}")
    atomic_write(current, draft_text)
    print(f"wrote {current.relative_to(root).as_posix()}")
    return finish_publish(root, handoff_dir, draft, new_id, resumed=False)


def ensure_gitignore(root: Path, handoff_dir: Path) -> None:
    gitignore = handoff_dir / ".gitignore"
    if not gitignore.exists():
        atomic_write(gitignore, "*\n")
        print(f"wrote {gitignore.relative_to(root).as_posix()}")


def remove_draft(handoff_dir: Path, draft: Path) -> None:
    if draft.resolve().parent == handoff_dir.resolve() and draft.name == DRAFT_FILE:
        draft.unlink()


def finish_publish(root: Path, handoff_dir: Path, draft: Path, new_id: str, resumed: bool) -> int:
    metadata = handoff_dir / METADATA_FILE
    atomic_write(metadata, metadata_document(new_id, "ready", None, None))
    print(f"wrote {metadata.relative_to(root).as_posix()}")
    remove_draft(handoff_dir, draft)
    verb = "finished publishing" if resumed else "published"
    print(f"{verb} {(handoff_dir / HANDOFF_FILE).relative_to(root).as_posix()} ({new_id})")
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    handoff_dir = root / HANDOFF_DIR
    current = handoff_dir / HANDOFF_FILE
    # Without a handoff there is nothing to mark, and writing metadata.json alone
    # would create .handoff/ without its .gitignore.
    if not current.is_file():
        print(
            f"refused: {current.relative_to(root).as_posix()} does not exist; nothing was changed"
        )
        return 1
    data, _body, _report = load_handoff(current)
    handoff_id = data.get("handoff_id")
    if not isinstance(handoff_id, str) or not handoff_id:
        handoff_id = UNKNOWN
    if args.status == "imported":
        document = metadata_document(handoff_id, "imported", args.agent, utc_now())
    else:
        document = metadata_document(handoff_id, args.status, None, None)
    atomic_write(handoff_dir / METADATA_FILE, document)
    print(f"metadata.json: status={args.status} handoff_id={handoff_id}")
    return 0


def cmd_clear(args: argparse.Namespace) -> int:
    root = find_root(args.root)
    handoff_dir = root / HANDOFF_DIR
    history = history_entries(handoff_dir)
    if args.keep is not None:
        targets = history[: max(0, len(history) - args.keep)]
    else:
        current = (handoff_dir / HANDOFF_FILE, handoff_dir / METADATA_FILE)
        targets = [p for p in current if p.exists()]
        if args.history:
            targets += history
    if not targets:
        print("nothing to delete")
        return 0
    if not args.yes:
        for path in targets:
            print(f"would delete {path.relative_to(root).as_posix()}")
        print(f"{len(targets)} file(s); re-run with --yes after the user confirms")
        return 0
    # Report each file only after it is gone, so a failure part-way leaves an
    # accurate record of what was deleted.
    for path in targets:
        path.unlink()
        print(f"deleted {path.relative_to(root).as_posix()}")
    print(f"deleted {len(targets)} file(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="handoff_tool.py", description="Helpers for the hand-off-context skill."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name: str, help_text: str) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument("--root", help="project root (default: Git top level, else cwd)")
        return p

    p = add("info", "print created_at, handoff_id, project and Git values for the frontmatter")
    p.set_defaults(func=cmd_info)

    p = add("changed-files", "print the Changed Files table built from git status")
    p.add_argument("--limit", type=int, default=CHANGED_FILES_LIMIT)
    p.set_defaults(func=cmd_changed_files)

    p = sub.add_parser("scan", help="report secrets in FILE without printing their values")
    p.add_argument("file")
    p.add_argument("--redact", action="store_true", help="mask findings in place")
    p.set_defaults(func=cmd_scan)

    p = add("validate", "validate a Handoff File (default: .handoff/handoff.md) and summarize it")
    p.add_argument("file", nargs="?")
    p.set_defaults(func=cmd_validate)

    p = add("publish", "validate DRAFT, archive the current handoff, and install DRAFT")
    p.add_argument("draft")
    p.set_defaults(func=cmd_publish)

    p = add("mark", "record the import result in metadata.json")
    p.add_argument("--status", choices=("imported", "invalid"), required=True)
    p.add_argument("--agent", help="the importing agent, e.g. codex")
    p.set_defaults(func=cmd_mark)

    p = add("clear", "list handoff data to delete; delete it with --yes")
    scope = p.add_mutually_exclusive_group()
    scope.add_argument("--history", action="store_true", help="also delete history/")
    scope.add_argument("--keep", type=int, metavar="N", help="prune history/ to the newest N")
    p.add_argument("--yes", action="store_true", help="actually delete")
    p.set_defaults(func=cmd_clear)
    return parser


def main(argv: list[str] | None = None) -> int:
    # Section titles may be Japanese; a legacy Windows console encoding must not
    # turn a report into a crash.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    args = build_parser().parse_args(argv)
    if args.command == "mark" and args.status == "imported" and not args.agent:
        print("error: --agent is required with --status imported", file=sys.stderr)
        return 2
    if args.command == "clear" and args.keep is not None and args.keep < 0:
        print("error: --keep must be 0 or more", file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except UnicodeDecodeError as exc:
        # A file that is not UTF-8 (written by another tool, or damaged).
        print(f"error: a file is not valid UTF-8: {exc}", file=sys.stderr)
        print("nothing after this point was changed", file=sys.stderr)
        return 1
    except OSError as exc:
        # Permission denied, disk full and the like: report it plainly instead
        # of a traceback. Writes go through atomic_write, so no file is left
        # half-written, and every completed write or deletion was printed.
        print(f"error: {exc}", file=sys.stderr)
        print(
            "stopped here: files written or deleted so far are listed above;"
            " no file was left half-written. Fix the cause and run the same command again",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
