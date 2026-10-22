#!/usr/bin/env python3
"""Validate the Codex plugin distribution against the skills/ tree.

Codex users install these skills as a plugin
(`codex plugin marketplace add InumberX/skills` then
`codex plugin add inumberx-skills@inumberx-skills`). Codex reads two files:

  * `.agents/plugins/marketplace.json` — the marketplace catalog. Codex looks
    for it before `.claude-plugin/marketplace.json`, so once it exists Codex
    ignores the Claude catalog entirely; and
  * `.codex-plugin/plugin.json` — the manifest of the plugin rooted at the
    repository root, whose `skills` path tells Codex where the skills live.

Only the **bundle** plugin is published for Codex. Codex loads a plugin's
skills from `<plugin root>/skills/` or from a manifest `skills` path, and that
path may not be "./", so a per-skill plugin rooted at skills/<name>/ (with
SKILL.md directly inside) would expose no skills. The catalog therefore holds
exactly one entry pointing at the repository root.

Checks (marketplace.json):
  1. Exists, is a JSON object, `name` is kebab-case and matches the Claude
     catalog's name (so `<plugin>@inumberx-skills` reads the same on both).
  2. `plugins` holds exactly one entry: kebab-case `name` equal to the
     manifest's `name`, a local `source` of exactly "./" (string or
     `{"source": "local", "path": "./"}`), `policy.installation` /
     `policy.authentication` with allowed values, and a non-empty `category`.

Checks (plugin.json):
  3. Exists, is a JSON object, `name` is kebab-case and matches the
     marketplace name.
  4. `skills` resolves to skills/ itself and skills/ holds at least one
     */SKILL.md, so every published skill (and its reference files) ships.
  5. Every path-bearing field starts with "./" and has no ".." component.
  6. `interface.defaultPrompt`, if present, has at most 3 entries of at most
     128 characters (Codex drops or truncates the rest).

Exit code is non-zero if any check fails.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
MARKETPLACE = REPO_ROOT / ".agents" / "plugins" / "marketplace.json"
MANIFEST = REPO_ROOT / ".codex-plugin" / "plugin.json"
CLAUDE_MARKETPLACE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
KEBAB_CASE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

INSTALLATION_POLICIES = {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
AUTHENTICATION_POLICIES = {"ON_INSTALL", "ON_USE"}
MAX_DEFAULT_PROMPTS = 3
MAX_DEFAULT_PROMPT_LENGTH = 128

# Manifest fields whose values are paths relative to the plugin root.
TOP_LEVEL_PATH_FIELDS = ("skills", "hooks", "mcpServers", "apps")
INTERFACE_PATH_FIELDS = ("composerIcon", "logo", "logoDark")


def _load_object(path: Path, errors: list[str]) -> dict | None:
    """Parse `path` as a JSON object, appending an error and returning None on failure."""
    rel = _rel(path)
    if not path.is_file():
        errors.append(f"{rel} is missing")
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        errors.append(f"{rel} is not valid JSON: {exc}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{rel} does not parse as a JSON object")
        return None
    return data


def check() -> list[str]:
    errors: list[str] = []
    marketplace = _load_object(MARKETPLACE, errors)
    manifest = _load_object(MANIFEST, errors)

    market_name = marketplace.get("name") if marketplace else None
    plugin_name = manifest.get("name") if manifest else None

    if marketplace is not None:
        errors.extend(check_marketplace(marketplace, plugin_name))
    if manifest is not None:
        errors.extend(check_manifest(manifest, market_name))
    return errors


def check_marketplace(data: dict, plugin_name: object) -> list[str]:
    errors: list[str] = []
    name = data.get("name")
    if not isinstance(name, str) or not KEBAB_CASE.match(name):
        errors.append("marketplace `name` is missing or not kebab-case")
    else:
        claude_name = _claude_marketplace_name()
        if claude_name is not None and name != claude_name:
            errors.append(
                f"marketplace `name` ({name!r}) must match the Claude catalog name "
                f"({claude_name!r})"
            )

    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        errors.append("marketplace `plugins` is missing or empty")
        return errors
    if len(plugins) != 1:
        # Per-skill plugins cannot expose their skill on Codex (see module docstring).
        errors.append(
            f"marketplace `plugins` must hold exactly one bundle entry, got {len(plugins)}"
        )

    for i, entry in enumerate(plugins):
        where = f"plugins[{i}]"
        if not isinstance(entry, dict):
            errors.append(f"{where} is not an object")
            continue

        pname = entry.get("name")
        if not isinstance(pname, str) or not KEBAB_CASE.match(pname):
            errors.append(f"{where}: `name` is missing or not kebab-case")
        elif isinstance(plugin_name, str) and pname != plugin_name:
            errors.append(
                f"{where}: `name` ({pname!r}) must match .codex-plugin/plugin.json "
                f"`name` ({plugin_name!r})"
            )

        path = _local_source_path(entry.get("source"))
        if path is None:
            errors.append(
                f'{where}: `source` must be a local path or {{"source": "local", "path": "./"}}'
            )
        elif path != "./":
            errors.append(f"{where}: bundle source path must be exactly './', got {path!r}")

        policy = entry.get("policy")
        if not isinstance(policy, dict):
            errors.append(f"{where}: `policy` is missing")
        else:
            if policy.get("installation") not in INSTALLATION_POLICIES:
                errors.append(
                    f"{where}: `policy.installation` must be one of "
                    + ", ".join(sorted(INSTALLATION_POLICIES))
                )
            if policy.get("authentication") not in AUTHENTICATION_POLICIES:
                errors.append(
                    f"{where}: `policy.authentication` must be one of "
                    + ", ".join(sorted(AUTHENTICATION_POLICIES))
                )

        category = entry.get("category")
        if not isinstance(category, str) or not category.strip():
            errors.append(f"{where}: `category` is missing or empty")

    return errors


def check_manifest(data: dict, market_name: object) -> list[str]:
    errors: list[str] = []
    name = data.get("name")
    if not isinstance(name, str) or not KEBAB_CASE.match(name):
        errors.append("plugin.json `name` is missing or not kebab-case")
    elif isinstance(market_name, str) and name != market_name:
        errors.append(
            f"plugin.json `name` ({name!r}) must match the marketplace name ({market_name!r})"
        )

    interface = data.get("interface")
    if interface is not None and not isinstance(interface, dict):
        errors.append("plugin.json `interface` is not an object")
        interface = None

    paths: list[tuple[str, object]] = [(f, data[f]) for f in TOP_LEVEL_PATH_FIELDS if f in data]
    if interface:
        paths += [(f"interface.{f}", interface[f]) for f in INTERFACE_PATH_FIELDS if f in interface]
        screenshots = interface.get("screenshots", [])
        if isinstance(screenshots, list):
            paths += [(f"interface.screenshots[{i}]", s) for i, s in enumerate(screenshots)]
    for field, value in paths:
        error = _path_error(value)
        if error:
            errors.append(f"plugin.json `{field}` {error}")

    # A malformed `skills` value is already reported by the path check above.
    skills = data.get("skills")
    if skills is None:
        errors.append("plugin.json `skills` is missing")
    elif not _path_error(skills):
        if (REPO_ROOT / skills).resolve() != SKILLS_DIR.resolve():
            errors.append(f"plugin.json `skills` must point at './skills/', got {skills!r}")
        elif not any(SKILLS_DIR.glob("*/SKILL.md")):
            errors.append("plugin.json `skills` points at skills/, which has no */SKILL.md")

    if interface:
        prompts = interface.get("defaultPrompt", [])
        if not isinstance(prompts, list) or not all(isinstance(p, str) for p in prompts):
            errors.append("plugin.json `interface.defaultPrompt` must be a list of strings")
        else:
            if len(prompts) > MAX_DEFAULT_PROMPTS:
                errors.append(
                    f"plugin.json `interface.defaultPrompt` has {len(prompts)} entries; "
                    f"Codex shows at most {MAX_DEFAULT_PROMPTS}"
                )
            for i, prompt in enumerate(prompts):
                if len(prompt) > MAX_DEFAULT_PROMPT_LENGTH:
                    errors.append(
                        f"plugin.json `interface.defaultPrompt[{i}]` is {len(prompt)} characters; "
                        f"the limit is {MAX_DEFAULT_PROMPT_LENGTH}"
                    )

    return errors


def _local_source_path(source: object) -> str | None:
    """Return the path of a local marketplace source, or None for any other shape."""
    if isinstance(source, str):
        return source
    if isinstance(source, dict) and source.get("source") == "local":
        path = source.get("path")
        return path if isinstance(path, str) else None
    return None


def _path_error(value: object) -> str | None:
    """Describe why `value` is not a "./"-relative path inside the plugin root, or None."""
    if not isinstance(value, str) or not value.startswith("./"):
        return "must be a path starting with './'"
    if ".." in value.split("/"):
        return "must not contain '..'"
    return None


def _claude_marketplace_name() -> str | None:
    """Name of the Claude Code catalog, or None if it cannot be read (validated elsewhere)."""
    try:
        data = json.loads(CLAUDE_MARKETPLACE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    name = data.get("name") if isinstance(data, dict) else None
    return name if isinstance(name, str) else None


def _rel(path: Path) -> str:
    """Render `path` relative to the repo root when possible, else absolute."""
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    errors = check()
    targets = f"{_rel(MARKETPLACE)}, {_rel(MANIFEST)}"
    if errors:
        print(f"FAIL {targets}")
        for err in errors:
            print(f"     - {err}")
        print("\nCodex plugin validation failed.", file=sys.stderr)
        return 1
    print(f"OK   {targets}")
    print("\nCodex plugin distribution is consistent with skills/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
