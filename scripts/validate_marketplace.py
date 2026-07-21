#!/usr/bin/env python3
"""Validate .claude-plugin/marketplace.json against the skills/ tree.

The marketplace catalog lets Claude Code users install these skills as plugins
(`/plugin marketplace add InumberX/skills` then `/plugin install <name>@inumberx-skills`).
Because every skill is published as its own single-skill plugin, the catalog and
the skills/ directories must stay in sync — a skill added without a matching
entry is silently unpublished, and an entry pointing at a deleted skill breaks
install. This script fails CI when they drift.

Checks:
  1. marketplace.json exists, is valid JSON, and has the required top-level
     fields (`name`, `owner`, `plugins`).
  2. `name` is kebab-case; `owner` has a non-empty `name`.
  3. Each plugin entry has a kebab-case `name` and a `source`.
  4. With `metadata.pluginRoot: "./skills"`, every entry's source resolves to an
     existing skills/<source>/SKILL.md.
  5. Entry `name` matches its source directory (so the plugin namespace matches
     the skill directory).
  6. The set of published plugins exactly matches the set of skills/*/SKILL.md
     directories — no missing entries, no stale entries, no duplicates.

Exit code is non-zero if any check fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def skill_dir_names() -> set[str]:
    """Directory names of the published skills (skills/<name>/SKILL.md)."""
    return {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")}


def check() -> list[str]:
    errors: list[str] = []

    if not MARKETPLACE.is_file():
        return [f"{MARKETPLACE.relative_to(REPO_ROOT)} is missing"]

    try:
        data = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return [f"marketplace.json is not valid JSON: {exc}"]

    if not isinstance(data, dict):
        return ["marketplace.json does not parse as a JSON object"]

    name = data.get("name")
    if not isinstance(name, str) or not KEBAB_CASE.match(name or ""):
        errors.append("`name` is missing or not kebab-case")

    owner = data.get("owner")
    if not isinstance(owner, dict) or not isinstance(owner.get("name"), str) or not owner["name"].strip():
        errors.append("`owner.name` is missing or empty")

    plugin_root = ""
    metadata = data.get("metadata")
    if isinstance(metadata, dict):
        plugin_root = metadata.get("pluginRoot", "") or ""

    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append("`plugins` is missing or empty")
        return errors

    listed: list[str] = []
    for i, entry in enumerate(plugins):
        where = f"plugins[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} is not an object")
            continue

        pname = entry.get("name")
        if not isinstance(pname, str) or not KEBAB_CASE.match(pname or ""):
            errors.append(f"{where}: `name` is missing or not kebab-case")
            pname = None

        source = entry.get("source")
        if not isinstance(source, str) or not source.strip():
            # Only relative-path sources are used in this repo; object sources
            # (github/url/npm) would point outside the skills/ tree.
            errors.append(f"{where} ({pname or '?'}): `source` must be a non-empty relative path")
            continue

        # With pluginRoot "./skills", a bare source "foo" resolves to skills/foo.
        rel_root = plugin_root.lstrip("./")
        resolved = (REPO_ROOT / rel_root / source) if rel_root else (REPO_ROOT / source)
        skill_md = resolved / "SKILL.md"
        if not skill_md.is_file():
            errors.append(
                f"{where} ({pname or source}): source resolves to {resolved.relative_to(REPO_ROOT)}, "
                "which has no SKILL.md"
            )

        if pname and pname != source:
            errors.append(
                f"{where}: `name` ({pname!r}) must match its source directory ({source!r})"
            )

        if pname:
            listed.append(pname)

    # Sync: published set must equal the skills/ set, with no duplicates.
    dupes = sorted({n for n in listed if listed.count(n) > 1})
    if dupes:
        errors.append(f"duplicate plugin entries: {', '.join(dupes)}")

    published = set(listed)
    on_disk = skill_dir_names()
    missing = sorted(on_disk - published)
    stale = sorted(published - on_disk)
    if missing:
        errors.append(
            "skills without a marketplace entry (add them to plugins): " + ", ".join(missing)
        )
    if stale:
        errors.append(
            "marketplace entries with no matching skill (remove or fix): " + ", ".join(stale)
        )

    return errors


def main() -> int:
    errors = check()
    rel = MARKETPLACE.relative_to(REPO_ROOT)
    if errors:
        print(f"FAIL {rel}")
        for err in errors:
            print(f"     - {err}")
        print("\nMarketplace validation failed.", file=sys.stderr)
        return 1
    print(f"OK   {rel}")
    print("\nMarketplace catalog is in sync with skills/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
