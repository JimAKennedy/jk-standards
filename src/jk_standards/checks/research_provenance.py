"""research-provenance: summarised research never reads as original research.

Documentation that restates published scholarship — theory guides, design
rationale citing papers, tutorials built on other people's analysis — must
make its provenance mechanically visible: every citation link resolves to a
stable anchor in the bibliography, anchors are never duplicated, and pages
that opt in as research-derived (front-matter `provenance: research`) carry
both a provenance sentence and an Attribution note assigning their claims
to the three provenance classes (sourced claim, practical distillation,
project-specific value). The prose discipline behind the markers lives in
`skills/research-provenance/SKILL.md`.

Opt-in is two-level. The check as a whole is enabled by configuring
`research_provenance.bib_file` — with no bibliography configured it is
skipped, matching the incremental-adoption contract of count-drift and
behavioral-claims. Per page, the sentence/Attribution requirements apply
only to docs whose front-matter declares `provenance: research`; citation
resolution applies to every doc, because a dangling citation is broken
navigation whatever the page's class. Archived docs are exempt throughout.

Escape hatch: a `# provenance-ok: <reason>` marker on the citing line, or
the line immediately above it, suppresses citation-resolution findings —
the same two-line window used by action-pinning, count-drift, and
snippet-regions. The page-level requirements have no marker hatch: a page
that shouldn't carry them shouldn't declare `provenance: research`.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import frontmatter, output
from jk_standards.config import Config

# The escape-hatch marker. Matched anywhere on the line regardless of the
# surrounding comment syntax (.md `<!-- -->`, .mdx `{/* */}`, `#`).
_ESCAPE_RE = re.compile(r"provenance-ok\b")

# The per-page Attribution note research-derived pages must end with.
_ATTRIBUTION_RE = re.compile(r"\*\*Attribution:?\*\*")


def _iter_provenance_docs(root: Path, cfg: Config) -> list[Path]:
    """Doc files to scan. Falls back to the top-level doc_roots when
    `research_provenance.doc_roots` is not configured."""
    roots = cfg.provenance_doc_roots or cfg.doc_roots
    out: list[Path] = []
    for doc_root in roots:
        base = root / doc_root.path
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if not any(path.name.endswith(ext) for ext in doc_root.extensions):
                continue
            rel = path.relative_to(root).as_posix()
            if any(rel.startswith(d) for d in cfg.exempt_dirs):
                continue
            out.append(path)
    return out


def run(root: Path, cfg: Config) -> int:
    if not cfg.provenance_bib_file:
        output.summary("research-provenance: no bibliography configured — skipped")
        return 0

    bib_rel = cfg.provenance_bib_file
    bib_path = root / bib_rel
    if not bib_path.is_file():
        output.error(
            bib_rel,
            1,
            f"research_provenance.bib_file {bib_rel!r} does not exist — "
            f"fix the path or remove the config section",
        )
        return 1

    # A malformed pattern must fail loudly, not silently pass everything —
    # the same contract as an invalid boundaries `forbid` regex.
    try:
        id_re = re.compile(rf"id=\"(?P<anchor>{cfg.provenance_anchor_pattern})\"")
        cite_re = re.compile(rf"#(?P<anchor>{cfg.provenance_anchor_pattern})\b")
        phrase_re = re.compile(cfg.provenance_phrase, re.IGNORECASE)
    except re.error as e:
        output.error(bib_rel, 1, f"invalid research_provenance regex: {e}")
        return 1

    errors = 0

    # 1. Collect defined anchor ids from the bibliography; duplicates break
    # every citation pointing at the id, so each redefinition is flagged.
    defined: dict[str, int] = {}
    for lineno, line in enumerate(
        bib_path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
    ):
        for m in id_re.finditer(line):
            anchor = m.group("anchor")
            if anchor in defined:
                output.error(
                    bib_rel,
                    lineno,
                    f"duplicate bibliography id {anchor!r} "
                    f"(first defined at line {defined[anchor]})",
                )
                errors += 1
            else:
                defined[anchor] = lineno

    for path in _iter_provenance_docs(root, cfg):
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace")
        if frontmatter.read_class(text) == "archived":
            continue
        lines = text.splitlines()

        # 2. Every citation resolves to a defined bibliography id.
        for lineno, line in enumerate(lines, start=1):
            suppressed = bool(_ESCAPE_RE.search(line)) or (
                lineno >= 2 and bool(_ESCAPE_RE.search(lines[lineno - 2]))
            )
            if suppressed:
                continue
            for anchor in {m.group("anchor") for m in cite_re.finditer(line)}:
                if anchor not in defined:
                    output.error(
                        rel,
                        lineno,
                        f"citation anchor {anchor!r} is not defined in {bib_rel} — "
                        f"add the bibliography entry "
                        f"(or add # provenance-ok: <reason>)",
                    )
                    errors += 1

        # 3+4. Pages opted in as research-derived carry the provenance
        # sentence and the Attribution note.
        if frontmatter.read_field(text, "provenance") != "research":
            continue
        if not phrase_re.search(text):
            output.error(
                rel,
                1,
                f"page declares `provenance: research` but has no provenance "
                f"sentence matching /{cfg.provenance_phrase}/ — state that the "
                f"content summarises cited scholarship",
            )
            errors += 1
        if not _ATTRIBUTION_RE.search(text):
            output.error(
                rel,
                1,
                "page declares `provenance: research` but has no "
                "**Attribution:** note assigning its claims to sourced / "
                "distilled / project-specific classes",
            )
            errors += 1

    if errors == 0:
        output.summary(
            "research-provenance: all citations resolve and research pages declare provenance"
        )
    return errors
