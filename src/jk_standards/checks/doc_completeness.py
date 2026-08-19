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

    accounted: set[str] = {entry["doc"] for entry in cannot_drift}
    for i, mapping in enumerate(data.get("mappings", [])):
        if not isinstance(mapping, dict) or "doc" not in mapping:
            raise ConfigError(f"mappings entry {i} must have a 'doc' key")
        accounted.add(mapping["doc"])

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

    if errors == 0:
        summary = f"doc-completeness: all {checked} doc(s) mapped or declared"
        if exempted:
            summary += f" ({exempted} exempt by class)"
        output.summary(summary)
    return errors
