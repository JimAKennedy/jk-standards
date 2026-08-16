"""Shared parsing for GitHub Actions workflow files.

Two checks — `workflow-permissions` and `workflow-concurrency` — reason about
the *composition* of workflows rather than the contents of any one of them, and
both need the same two things: the parsed YAML, and the line each interesting
key sits on so a finding can be reported at `file:line`.

`yaml.safe_load` gives the first and throws away the second, so this module
composes the document into a node graph instead (`yaml.compose`), converts it to
plain Python values, and records a `path -> line` map alongside. A *path* is the
tuple of mapping keys and sequence indices leading to a node, so
`("jobs", "build", "permissions")` locates the `permissions:` key of the `build`
job. Lines are 1-based, matching the annotation format.
"""

from __future__ import annotations

from pathlib import Path

import yaml

# The value of a `permissions:` block, normalised to scope -> level. GitHub
# resolves an omitted scope to `none`, so a mapping is total: anything absent
# is denied. `read-all` / `write-all` are expanded lazily via _ALL.
_LEVELS = {"none": 0, "read": 1, "write": 2}

# Sentinel scope meaning "every scope, at this level", produced by the
# `read-all` / `write-all` shorthands.
ALL_SCOPES = "*"

# Turns a composed ScalarNode back into a Python value using the tag the
# resolver already assigned. Stateless for scalars, so one instance is shared.
_SCALARS = yaml.constructor.SafeConstructor()


def level_of(name: object) -> int:
    """Return the numeric rank of a permission level (`none` < `read` < `write`).

    Unknown values rank as `none`, which is the conservative reading: an
    unrecognised level never counts as granting anything.
    """
    return _LEVELS.get(str(name).strip().lower(), 0)


def iter_workflow_files(root: Path, rel_dir: str, extensions: list[str]) -> list[Path]:
    """Return the workflow files under ``root/rel_dir``, sorted for determinism.

    Returns an empty list when the directory is absent, letting a caller treat
    "no workflows" as a clean skip rather than an error.
    """
    base = root / rel_dir
    if not base.is_dir():
        return []
    return sorted(
        p
        for p in base.rglob("*")
        if p.is_file() and any(p.name.endswith(ext) for ext in extensions)
    )


def _convert(node: yaml.Node, path: tuple, lines: dict[tuple, int]) -> object:
    """Recursively turn a composed YAML node into plain data, recording lines."""
    lines[path] = node.start_mark.line + 1
    if isinstance(node, yaml.MappingNode):
        out: dict = {}
        for key_node, value_node in node.value:
            key = str(key_node.value)
            # Record the *key's* line: a finding about `permissions:` should
            # point at the key, not at wherever its nested value happens to
            # start. The value's own line is recorded by the recursive call.
            lines[path + (key,)] = key_node.start_mark.line + 1
            out[key] = _convert(value_node, path + (key,), lines)
        return out
    if isinstance(node, yaml.SequenceNode):
        return [_convert(item, path + (i,), lines) for i, item in enumerate(node.value)]
    # ScalarNode — apply PyYAML's usual implicit typing (bool, int, null) so
    # `deploy: false` arrives as False rather than the string "false". The
    # resolver already tagged the node during compose(), so constructing it
    # directly is enough; re-serialising a bare scalar does not round-trip.
    return _SCALARS.construct_object(node, deep=True)


def load_workflow(path: Path) -> tuple[object, dict[tuple, int]]:
    """Parse one workflow into ``(data, lines)``.

    ``data`` is the plain-Python document (``None`` for an empty file) and
    ``lines`` maps each node path to its 1-based line. A file that does not
    parse yields ``(None, {})`` rather than raising: a malformed workflow is
    GitHub's error to report, and a check that crashed on it would be strictly
    less useful than one that skipped it.
    """
    try:
        node = yaml.compose(path.read_text(encoding="utf-8", errors="replace"))
    except yaml.YAMLError:
        return None, {}
    if node is None:
        return None, {}
    lines: dict[tuple, int] = {}
    return _convert(node, (), lines), lines


def normalise_permissions(value: object) -> dict[str, int] | None:
    """Normalise a ``permissions:`` value to ``scope -> level`` ranks.

    Returns ``None`` when no block was declared at all, which is materially
    different from an empty one: an absent block means "inherit the repository
    default" (unknowable statically), while ``permissions: {}`` means "grant
    nothing". Callers must distinguish the two to avoid inventing findings
    against a default they cannot see.
    """
    if value is None:
        return None
    if isinstance(value, str):
        token = value.strip().lower()
        if token == "read-all":
            return {ALL_SCOPES: _LEVELS["read"]}
        if token == "write-all":
            return {ALL_SCOPES: _LEVELS["write"]}
        return {}
    if isinstance(value, dict):
        return {str(scope): level_of(level) for scope, level in value.items()}
    return {}


def granted_level(grant: dict[str, int], scope: str) -> int:
    """Level ``grant`` confers on ``scope``, honouring the all-scopes sentinel.

    An omitted scope resolves to `none`, mirroring GitHub: declaring any
    `permissions:` block sets every unlisted scope to none rather than leaving
    it at the default.
    """
    return max(grant.get(scope, 0), grant.get(ALL_SCOPES, 0))
