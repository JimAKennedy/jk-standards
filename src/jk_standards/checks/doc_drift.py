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
"""

from __future__ import annotations

from fnmatch import fnmatchcase
from pathlib import Path

import yaml

from jk_standards import gitutil, output
from jk_standards.config import Config

TRAILER = "Docs-Not-Affected"


def _matches(pattern: str, changed: list[str]) -> list[str]:
    # fnmatch has no ** semantics; a prefix fallback covers the recursive case.
    if "**" in pattern:
        base = pattern.split("**")[0]
        return [f for f in changed if f.startswith(base)]
    return [f for f in changed if fnmatchcase(f, pattern)]


def run(root: Path, cfg: Config, base: str | None = None) -> int:
    map_path = root / cfg.drift_map
    if not map_path.is_file():
        output.error(cfg.drift_map, 1, "drift map not found")
        return 1

    data = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}
    mappings = data.get("mappings", [])

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
    errors = 0
    satisfied = 0
    for mapping in mappings:
        doc = mapping["doc"]
        triggered = sorted(
            {f for pattern in mapping["sources"] for f in _matches(pattern, changed)}
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
