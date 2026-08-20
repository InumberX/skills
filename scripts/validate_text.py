#!/usr/bin/env python3
"""Validate Japanese punctuation in the repository's Markdown files.

textlint covers prose style, but its `4.3.1.丸かっこ（）` rule cannot be relied
on for parentheses: it skips headings, table cells and block quotes, and its
autofix converts the opening bracket while leaving the closing one half-width —
producing a mismatched pair that the same rule then reports as clean. This
script performs that check deterministically instead.

Checks per Markdown file, line by line:
  1. No half-width parentheses wrap Japanese text. The repository writes
     Japanese with full-width （） (see skills/create-skill/rules/format.md).
  2. No mismatched pair, i.e. `（…)` or `(…）`.

Inline code spans (`` `...` ``) and fenced code blocks are still checked: the
directory trees and commented examples in them are prose, and the repository
formats them the same way as body text. Parentheses that wrap no Japanese
character — `push(main)`, `redirect(to)` — are left alone, so real code
samples are unaffected.

Matching is per line, so a pair split across a line break is not detected. The
Markdown here is written without hard wrapping, which keeps every pair on one
line; revisit this if that convention changes.

Exit code is non-zero if any file fails.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files to check: every Markdown file at the repository root plus everything
# shipped with a skill. The root pattern is a glob rather than `README.md` so a
# document added later is covered without editing this list.
TARGETS = ("*.md", "skills/**/*.md")

# Hiragana, katakana, CJK ideographs, the prolonged-sound mark, iteration mark
# and the Japanese quotation/punctuation marks that appear inside parentheses.
JAPANESE = r"[ぁ-んァ-ヶー一-龥々「」『』、。・]"

# A half-width pair wrapping at least one Japanese character. Nested *half-width*
# parentheses are excluded so the match stays on the innermost pair; a nested
# full-width pair is allowed through, because the outer half-width pair is still
# the violation to report — `(あ（い）う)` is flagged on its outer brackets.
HALF_WIDTH_PAIR = re.compile(rf"\([^()]*{JAPANESE}[^()]*\)")

# A pair whose brackets disagree in width. Both widths are excluded from the
# body so that a correctly paired inner group cannot be read as the closing
# bracket of an outer one.
MISMATCHED_PAIR = re.compile(r"（[^（）()]*\)|\([^（）()]*）")


def iter_targets() -> list[Path]:
    """Markdown files to validate, sorted for stable output."""
    found: set[Path] = set()
    for pattern in TARGETS:
        found.update(p for p in REPO_ROOT.glob(pattern) if p.is_file())
    return sorted(found)


def check(markdown: Path) -> list[str]:
    errors: list[str] = []
    text = markdown.read_text(encoding="utf-8")

    for lineno, line in enumerate(text.splitlines(), 1):
        for match in MISMATCHED_PAIR.finditer(line):
            errors.append(
                f"line {lineno}: 開き括弧と閉じ括弧の全角/半角が揃っていません: {match.group()!r}"
            )
        for match in HALF_WIDTH_PAIR.finditer(line):
            errors.append(
                f"line {lineno}: 日本語を半角括弧で囲んでいます。"
                f"全角の（）を使ってください: {match.group()!r}"
            )

    return errors


def main() -> int:
    targets = iter_targets()
    if not targets:
        print("no Markdown files found", file=sys.stderr)
        return 1

    failed = 0
    for markdown in targets:
        rel = markdown.relative_to(REPO_ROOT)
        errors = check(markdown)
        if errors:
            failed += 1
            print(f"FAIL {rel}")
            for error in errors:
                print(f"  - {error}")
        else:
            print(f"OK   {rel}")

    print()
    if failed:
        print(f"{failed} of {len(targets)} file(s) failed.")
        return 1

    print(f"All {len(targets)} file(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
