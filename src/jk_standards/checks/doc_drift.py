"""doc-drift: code that a doc describes cannot move without the doc.

Driven by a declarative drift map (YAML). Each mapping pairs source globs
with the doc that describes them and a written reason. If the PR diff
touches a mapped source, the PR must also touch the doc — or a commit in
the range must carry a `Docs-Not-Affected: <reason>` trailer, putting the
bypass justification in history right next to the change.

Map hygiene (documented in the map file itself): don't map archived docs
(frozen by definition) or generated docs (freshness-checked instead), and
only map real, current, checkable claims.

Note on bypass scope: any trailer in the range satisfies every triggered
mapping — the trailer is a PR-level assertion, mirroring the original
semantics this check was extracted from.

Deps-only manifests: files listed in `doc_drift.deps_only_manifests` (e.g.
`site/package.json`) are excluded from triggering mappings when every changed
line is a dependency pin — a `"name": "value"` entry whose value is version
shaped. A Dependabot bump is not a taxonomy change; the mapping's signal is a
`scripts`-block or framework edit, not a new version on an existing dep.
"""

from __future__ import annotations

import re
from fnmatch import fnmatchcase
from pathlib import Path

import yaml

from jk_standards import gitutil, output
from jk_standards.config import Config, ConfigError

TRAILER = "Docs-Not-Affected"

# A `"name": "value"` manifest entry, capturing the value so its shape can be
# judged. Block-opening lines are deliberately not matched any more: see
# is_deps_only_diff for why position-based membership cannot work on a diff.
_VERSION_LINE_RE = re.compile(r"\s*\"[^\"]+\"\s*:\s*\"(?P<value>[^\"]+)\",?\s*$")
# An npm version range as a resolver writes one: optional operator, then a
# digit-led version. This is what separates a dependency pin from a `scripts`
# entry, a package rename, or any other string-valued key.
_VERSION_VALUE_RE = re.compile(r"^[\^~]?[<>=]*\s*v?\d")


def _matches(pattern: str, changed: list[str], excluded: set[str]) -> list[str]:
    # fnmatch has no ** semantics; a prefix fallback covers the recursive case.
    if "**" in pattern:
        base = pattern.split("**")[0]
        return [f for f in changed if f.startswith(base) and f not in excluded]
    return [f for f in changed if fnmatchcase(f, pattern) and f not in excluded]


def is_deps_only_diff(diff: str) -> bool:
    """True when every changed line in a manifest diff is a dependency pin.

    A dependency pin is a ``"name": "value"`` entry whose *value* is version
    shaped — an optional range operator (``^``, ``~``, ``>=``…) followed by a
    digit-led version. That is the whole rule. A `scripts` edit, a renamed
    package, a new top-level key or a structural brace change all fail it, and
    those are the taxonomy signals the drift map must still catch.

    The earlier implementation asked a stricter question — "is every changed
    line inside a `dependencies`/`devDependencies` block?" — and tracked block
    membership by brace depth across the diff's context lines. It could not
    answer that question reliably, because a diff is a *fragment*: when the
    hunk window opens after the block's ``"dependencies": {`` line, that line
    is never seen, membership never becomes true, and a routine Dependabot
    bump is rejected. Real bumps land mid-block far more often than not, so
    the check failed closed on precisely the case it existed to allow.

    Matching on the value's shape rather than the line's position needs no
    context at all, which is what makes it correct on a fragment. It is also
    tighter than it may look: a value must lead with a digit (after an
    optional operator), so ``"test": "vitest"``, ``"name": "site"`` and
    ``"license": "Apache-2.0"`` are all rejected — each of which a
    "any `"k": "v"` entry" rule would have waved through.

    Residual limits, both failing in the safe direction. A dependency pinned
    to something not version shaped — a git URL, ``npm:`` alias, ``file:``
    path or bare ``*`` — is not recognised, so its bump still trips the
    mapping, exactly as every bump does today. And a non-dependency key whose
    value happens to be version shaped (``"engines": {"node": ">=20"}``) is
    accepted; that is a dependency-adjacent fact, not a taxonomy change.
    """
    saw_change = False
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@", "diff ", "index ")):
            continue
        if not line.startswith(("+", "-")):
            continue
        saw_change = True
        entry = _VERSION_LINE_RE.match(line[1:])
        if entry and _VERSION_VALUE_RE.match(entry.group("value")):
            continue
        return False
    return saw_change


def _parse_cannot_drift(data: dict) -> list[dict]:
    """Validate the optional `cannot_drift` registry.

    Each entry declares a doc as un-driftable with a written justification. An
    entry must be a mapping with a `doc` (string) and a non-empty `reason`
    (truthy after ``str().strip()``). A malformed entry raises ConfigError
    naming the offending index so the CLI can surface a clean config diagnostic
    instead of a KeyError traceback. Entries are recorded, not matched against
    the diff — S02 consumes the registry for the completeness check.
    """
    entries = data.get("cannot_drift", [])
    if not isinstance(entries, list):
        raise ConfigError("cannot_drift must be a list of {doc, reason} entries")
    parsed: list[dict] = []
    for i, entry in enumerate(entries):
        where = f"cannot_drift entry {i}"
        if not isinstance(entry, dict):
            raise ConfigError(f"{where} must be a mapping with 'doc' and 'reason'")
        doc = entry.get("doc")
        if not isinstance(doc, str) or not doc.strip():
            raise ConfigError(f"{where} missing a non-empty string 'doc'")
        reason = entry.get("reason")
        if reason is None or not str(reason).strip():
            raise ConfigError(f"{where} ({doc}) missing a non-empty 'reason'")
        parsed.append({"doc": doc, "reason": str(reason)})
    return parsed


def run(root: Path, cfg: Config, base: str | None = None) -> int:
    map_path = root / cfg.drift_map
    if not map_path.is_file():
        output.error(cfg.drift_map, 1, "drift map not found")
        return 1

    data = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}
    mappings = data.get("mappings", [])
    # Parse + validate up front so a malformed registry fails as a config error
    # (exit 2 via the CLI) rather than midway through the diff correlation.
    _parse_cannot_drift(data)

    base_ref = gitutil.resolve_base_ref(root, base)
    changed = gitutil.changed_files(root, base_ref)
    if not changed:
        output.summary(f"doc-drift: no changes vs {base_ref} — trivially passes")
        return 0

    bypasses = gitutil.commit_trailers(root, base_ref, TRAILER)
    if bypasses:
        output.summary(f"doc-drift: {TRAILER} trailer(s) found:")
        for bypass in bypasses:
            output.summary(f"  {bypass}")

    changed_set = set(changed)
    deps_only = {
        f
        for f in cfg.deps_only_manifests
        if f in changed_set and is_deps_only_diff(gitutil.file_diff(root, base_ref, f))
    }
    if deps_only:
        output.summary(
            f"doc-drift: deps-only bump on {', '.join(sorted(deps_only))} — "
            f"ignored for mapping triggers"
        )

    errors = 0
    satisfied = 0
    for i, mapping in enumerate(mappings):
        if not isinstance(mapping, dict) or "doc" not in mapping or "sources" not in mapping:
            raise ConfigError(f"mappings entry {i} must have 'doc' and 'sources' keys")
        doc = mapping["doc"]
        triggered = sorted(
            {f for pattern in mapping["sources"] for f in _matches(pattern, changed, deps_only)}
        )
        if not triggered:
            continue
        if doc in changed_set or bypasses:
            satisfied += 1
            continue
        shown = ", ".join(triggered[:5])
        more = f" (+{len(triggered) - 5} more)" if len(triggered) > 5 else ""
        output.error(
            doc,
            1,
            f"Doc drift: change touches {shown}{more} but not {doc!r}. "
            f"Reason: {mapping.get('reason', 'mapped source')} — update {doc} "
            f"or add a '{TRAILER}: <reason>' trailer to any commit in the range.",
        )
        errors += 1

    if errors == 0:
        if satisfied:
            output.summary(f"doc-drift: {satisfied} mapping(s) triggered, all satisfied")
        else:
            output.summary("doc-drift: no mapped sources touched")
    return errors
