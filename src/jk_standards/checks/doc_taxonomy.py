"""doc-taxonomy: every doc must declare a lifecycle class.

Docs carry YAML front-matter `class: <value>` with a value from the
configured vocabulary (default: generated | gated | archived). The class is
what the other checks key off — gated docs get drift-mapped and
status-prose-linted, archived docs are exempt, generated docs must diff
clean against their generator.
"""

from __future__ import annotations

from pathlib import Path

from jk_standards import frontmatter, output
from jk_standards.config import Config, iter_docs


def run(root: Path, cfg: Config) -> int:
    errors = 0
    checked = 0
    targets = list(iter_docs(root, cfg))
    targets += [root / f for f in cfg.taxonomy_extra_files if (root / f).is_file()]

    for path in targets:
        checked += 1
        rel = path.relative_to(root).as_posix()
        klass = frontmatter.read_class(path.read_text(encoding="utf-8", errors="replace"))
        if klass is None:
            output.error(
                rel,
                1,
                f"Missing 'class:' front-matter field. Add one of: "
                f"{', '.join(cfg.taxonomy_classes)}",
            )
            errors += 1
        elif klass not in cfg.taxonomy_classes:
            output.error(
                rel,
                1,
                f"Invalid class '{klass}'. Must be one of: {', '.join(cfg.taxonomy_classes)}",
            )
            errors += 1

    if errors == 0:
        output.summary(f"doc-taxonomy: all {checked} doc(s) carry a valid class")
    return errors
