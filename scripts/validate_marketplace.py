#!/usr/bin/env python3
"""Validate .claude-plugin/marketplace.json against the skills/ tree.

The marketplace catalog lets Claude Code users install these skills as plugins
(`/plugin marketplace add InumberX/skills` then `/plugin install <name>@inumberx-skills`).
The catalog publishes two kinds of plugin:

  * a single **bundle** plugin whose source is the repo root ("./"), which ships
    every skill under skills/ at once; and
  * one **per-skill** plugin per skills/<name>/ directory, so users can install
    just the skills they want.

Because both are derived from skills/, the catalog must stay in sync with the
directory tree — a skill added without a matching per-skill entry is silently
unpublished, and an entry pointing at a deleted skill breaks install. This
script fails CI when they drift.

Checks:
  1. marketplace.json exists, is valid JSON, and has the required top-level
     fields (`name`, `owner`, `plugins`).
  2. `name` is kebab-case; `owner` has a non-empty `name`.
  3. Each plugin entry has a kebab-case `name` and a relative-path `source`
     (starting with "./") that resolves inside the repository — a source that
     escapes via "./../…" or a symlink is rejected.
  4. The bundle entry (source resolves to the repo root) must use the canonical
     source "./" and be named after the marketplace, and requires skills/ to
     hold at least one skill; it is exempt from the name==directory and the
     per-skill sync checks. Naming it after the marketplace pins it to a single
     entry (a second bundle collides on the duplicate-name check).
  5. Each per-skill entry's source is exactly ./skills/<name>/ (a direct child
     of skills/) holding a SKILL.md, and its `name` matches that directory (so
     the plugin namespace matches the skill directory). A source pointing
     elsewhere in the repo is rejected even if it happens to contain a SKILL.md.
  6. The set of per-skill entries exactly matches the set of skills/*/SKILL.md
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

    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append("`plugins` is missing or empty")
        return errors

    repo_root = REPO_ROOT.resolve()
    skills_dir = SKILLS_DIR.resolve()
    per_skill: list[str] = []  # names of per-skill entries, for the sync check
    all_names: list[str] = []  # every entry name, for duplicate detection

    for i, entry in enumerate(plugins):
        where = f"plugins[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} is not an object")
            continue

        pname = entry.get("name")
        if not isinstance(pname, str) or not KEBAB_CASE.match(pname or ""):
            errors.append(f"{where}: `name` is missing or not kebab-case")
            pname = None
        else:
            all_names.append(pname)

        source = entry.get("source")
        if not isinstance(source, str) or not source.strip():
            # Only relative-path sources are used in this repo; object sources
            # (github/url/npm) would point outside this repository.
            errors.append(f"{where} ({pname or '?'}): `source` must be a non-empty relative path")
            continue
        if not source.startswith("./"):
            errors.append(f"{where} ({pname or source}): `source` must start with './'")
            continue

        resolved = (REPO_ROOT / source).resolve()

        # Reject sources that escape the repository via "./../…" or a symlink
        # resolving outside the repo root — such an entry could ship files from
        # outside this repository while still passing the other checks.
        if resolved != repo_root and repo_root not in resolved.parents:
            errors.append(
                f"{where} ({pname or source}): source {source!r} resolves outside the repository"
            )
            continue

        if resolved == repo_root:
            # Bundle plugin: ships all of skills/. Exempt from name==dir and the
            # per-skill sync, but held to a canonical contract: source is exactly
            # "./" (not a non-canonical spelling like "./." or "./skills/.."),
            # and name equals the marketplace name. Requiring the name pins the
            # bundle to a single entry — a second bundle then collides on the
            # duplicate-name check instead of silently passing.
            if source != "./":
                errors.append(f"{where} ({pname or source}): bundle source must be exactly './'")
            if pname and isinstance(name, str) and pname != name:
                errors.append(
                    f"{where}: bundle `name` ({pname!r}) must match the marketplace name ({name!r})"
                )
            if not skill_dir_names():
                errors.append(f"{where} ({pname or source}): bundle source has no skills under skills/")
            continue

        # Per-skill plugin: source must be exactly ./skills/<name>/ (a direct
        # child of skills/) holding a SKILL.md. A path elsewhere in the repo, or
        # a nested subdirectory, would ship the wrong contents while still
        # satisfying the skills/ sync check.
        if resolved.parent != skills_dir:
            errors.append(
                f"{where} ({pname or source}): per-skill source must be './skills/<name>', "
                f"got {source!r}"
            )
            continue

        skill_md = resolved / "SKILL.md"
        if not skill_md.is_file():
            errors.append(
                f"{where} ({pname or source}): source resolves to "
                f"{_rel(resolved)}, which has no SKILL.md"
            )
        if pname and pname != resolved.name:
            errors.append(
                f"{where}: `name` ({pname!r}) must match its source directory ({resolved.name!r})"
            )
        if pname:
            per_skill.append(pname)

    # Duplicate detection across every entry (bundle included).
    dupes = sorted({n for n in all_names if all_names.count(n) > 1})
    if dupes:
        errors.append(f"duplicate plugin entries: {', '.join(dupes)}")

    # Sync: the per-skill entries must exactly cover the skills/ directories.
    published = set(per_skill)
    on_disk = skill_dir_names()
    missing = sorted(on_disk - published)
    stale = sorted(published - on_disk)
    if missing:
        errors.append(
            "skills without a per-skill marketplace entry (add them to plugins): "
            + ", ".join(missing)
        )
    if stale:
        errors.append(
            "per-skill entries with no matching skill (remove or fix): " + ", ".join(stale)
        )

    return errors


def _rel(path: Path) -> str:
    """Render `path` relative to the repo root when possible, else absolute."""
    try:
        return str(path.relative_to(REPO_ROOT.resolve()))
    except ValueError:
        return str(path)


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
