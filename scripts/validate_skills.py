#!/usr/bin/env python3
"""Validate every skills/*/SKILL.md frontmatter.

Enforces the machine-checkable parts of skills/create-skill/rules/format.md so
that a malformed or undiscoverable skill fails CI instead of being merged.

Checks per SKILL.md:
  1. Starts with a `---` frontmatter block that closes with `---`.
  2. The frontmatter parses as a YAML mapping.
  3. `name` and `description` keys exist and are non-empty strings.
  4. `name` is kebab-case and matches the skill directory name.
  5. `description` is wrapped in double quotes in the source (format.md rule:
     unquoted natural language with `:`/`#` breaks YAML parsing).

Exit code is non-zero if any skill fails.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def split_frontmatter(text: str) -> str | None:
    """Return the raw frontmatter block, or None if it is missing/unterminated.

    The opening and closing delimiters must be lines whose entire content is
    exactly `---`; a line such as `----` or `---foo` is not a delimiter.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r\n") == "---":
            return "".join(lines[1:i])
    return None


def check(skill_md: Path) -> list[str]:
    errors: list[str] = []
    raw = skill_md.read_text(encoding="utf-8")

    front = split_frontmatter(raw)
    if front is None:
        return ["missing or unterminated `---` frontmatter block"]

    try:
        data = yaml.safe_load(front)
    except yaml.YAMLError as exc:
        return [f"frontmatter is not valid YAML: {exc}"]

    if not isinstance(data, dict):
        return ["frontmatter does not parse as a YAML mapping"]

    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        errors.append("`name` is missing or empty")
    else:
        if not KEBAB_CASE.match(name):
            errors.append(f"`name` must be kebab-case, got {name!r}")
        if name != skill_md.parent.name:
            errors.append(
                f"`name` ({name!r}) must match its directory ({skill_md.parent.name!r})"
            )

    description = data.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("`description` is missing or empty")
    elif description_scalar_style(front) != '"':
        # format.md: the description value must be a double-quoted YAML scalar.
        # Checked via the parsed scalar *style* (not a string prefix) so that a
        # single-quoted or plain value that merely contains a double quote —
        # e.g. description: '"x"' — cannot slip through.
        errors.append(
            "`description` must be a double-quoted YAML scalar "
            "(see create-skill/rules/format.md)"
        )

    return errors


def description_scalar_style(front: str) -> str | None:
    """Return the YAML scalar style of the `description` value.

    `"` for double-quoted, `'` for single-quoted, `|`/`>` for block scalars,
    and None for a plain (unquoted) scalar. Returns None if absent.
    """
    node = yaml.compose(front)
    if not isinstance(node, yaml.MappingNode):
        return None
    for key_node, value_node in node.value:
        if (
            isinstance(key_node, yaml.ScalarNode)
            and key_node.value == "description"
            and isinstance(value_node, yaml.ScalarNode)
        ):
            return value_node.style
    return None


def main() -> int:
    skill_files = sorted(SKILLS_DIR.glob("**/SKILL.md"))
    if not skill_files:
        print(f"No SKILL.md found under {SKILLS_DIR}", file=sys.stderr)
        return 1

    failed = False
    for skill_md in skill_files:
        rel = skill_md.relative_to(REPO_ROOT)
        errors = check(skill_md)
        if errors:
            failed = True
            print(f"FAIL {rel}")
            for err in errors:
                print(f"     - {err}")
        else:
            print(f"OK   {rel}")

    if failed:
        print("\nSkill frontmatter validation failed.", file=sys.stderr)
        return 1
    print(f"\nAll {len(skill_files)} skill(s) passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
