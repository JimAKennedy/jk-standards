"""doc-completeness: every doc under a doc_root is mapped or declared.

The doc-drift map records which docs a source change must drag along, and
the cannot_drift registry records which docs are deliberately exempt. But
neither fails when a brand-new page is added under a doc_root and simply
forgotten — left out of both. This static check closes that gap: it
enumerates every doc `iter_docs` sees under the configured doc_roots and
fails, naming any doc that is neither a mapped `doc:` target nor listed in
the cannot_drift registry. "Forgot to register this page" becomes a hard
error on every `jk-standards all`.

It reuses doc_drift's cannot_drift parser, so a malformed registry surfaces
as the same `config error: ...` (exit 2) rather than a traceback. Unlike
doc-drift it needs no git base ref — the working tree and the map are the
only inputs — so it runs unconditionally as a static check.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from jk_standards import frontmatter, output
from jk_standards.checks import doc_drift
from jk_standards.config import Config, ConfigError, iter_docs


def run(root: Path, cfg: Config) -> int:
    map_path = root / cfg.drift_map
    if not map_path.is_file():
        output.error(cfg.drift_map, 1, "drift map not found")
        return 1

    data = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}

    # Reuse doc_drift's parser so a malformed cannot_drift registry fails as a
    # config error (exit 2 via the CLI) with the exact same diagnostic.
    cannot_drift = doc_drift._parse_cannot_drift(data)

    # Track provenance (doc -> registry) rather than an anonymous set so the
    # reverse existence pass can name which registry an orphaned entry came
    # from. A doc registered in both registries is tagged ``mappings`` (the
    # more actionable failure: a stale mapping is an unsatisfiable gate).
    accounted: dict[str, str] = {}
    for entry in cannot_drift:
        accounted[entry["doc"]] = "cannot_drift"
    for i, mapping in enumerate(data.get("mappings", [])):
        if not isinstance(mapping, dict) or "doc" not in mapping:
            raise ConfigError(f"mappings entry {i} must have a 'doc' key")
        accounted[mapping["doc"]] = "mappings"

    docs = iter_docs(root, cfg)
    # An ``archived`` (or otherwise exempt-classed) doc is deliberately frozen,
    # so requiring it to be mapped or cannot_drift-declared is noise. The
    # exemption keys off the doc's own front-matter class read here, NOT
    # cfg.generated — a generated-config doc classed ``gated`` stays governed.
    exempt_classes = set(cfg.doc_completeness_exempt_classes)
    errors = 0
    checked = 0
    exempted = 0
    for path in docs:
        rel = path.relative_to(root).as_posix()
        if exempt_classes:
            text = path.read_text(encoding="utf-8", errors="replace")
            if frontmatter.read_class(text) in exempt_classes:
                exempted += 1
                continue
        checked += 1
        if rel in accounted:
            continue
        output.error(
            rel,
            1,
            f"Doc completeness: {rel} is under a doc_root but is neither mapped "
            f"nor declared un-driftable in {cfg.drift_map}. Add a mappings entry "
            f"(sources + reason) or a cannot_drift entry with a reason.",
        )
        errors += 1

    # Reverse existence pass: a registry entry naming a path that no longer
    # exists is an orphan. This is a fact about the filesystem, so it uses plain
    # ``is_file`` (NOT iter_docs membership — an entry may legitimately name a
    # doc outside the enumerated doc_roots) and runs unconditionally, never
    # behind the #50 git fail-open branch inside iter_docs. Each registry has a
    # distinct failure mode, so each gets a distinct message.
    orphans = 0
    for doc, registry in accounted.items():
        if (root / doc).is_file():
            continue
        if registry == "cannot_drift":
            output.error(
                doc,
                1,
                f"Doc completeness: cannot_drift entry '{doc}' in {cfg.drift_map} "
                f"names a path that no longer exists. A stale cannot_drift entry "
                f"silently pre-exempts any future doc created at that path from the "
                f"completeness gate. Remove the entry or correct its path.",
            )
        else:
            output.error(
                doc,
                1,
                f"Doc completeness: mappings entry '{doc}' in {cfg.drift_map} names "
                f"a path that no longer exists. A stale mapping is an unsatisfiable "
                f"gate — the doc can never be produced, so its only escape is a "
                f"'{doc_drift.TRAILER}' trailer on every affecting commit. Remove the "
                f"mappings entry or correct its path.",
            )
        orphans += 1
    errors += orphans

    if errors == 0:
        summary = (
            f"doc-completeness: all {checked} doc(s) mapped or declared; "
            f"{len(accounted)} registry entr{'y' if len(accounted) == 1 else 'ies'} "
            f"existence-checked"
        )
        if exempted:
            summary += f" ({exempted} exempt by class)"
        output.summary(summary)
    return errors
