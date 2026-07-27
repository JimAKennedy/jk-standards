"""snippet-regions: doc references to code regions resolve to real markers.

Docs point readers at slices of source through two forms:
  * MDX   `<CodeSnippet file="src/foo.py" region="bar" />`
  * prose `# region:bar` mentions

Each reference must resolve to a `region:<name>` marker that actually exists
in the declared source tree. When it doesn't, the snippet silently rots — the
site build (or a reader following the prose) lands on a region that was renamed
or deleted, with no diff on the doc side to warn anyone.

Marker syntax mirrors `site/src/components/CodeSnippet.astro`, the three forms
the repo already renders:
  * `// region:<name>`
  * `# region:<name>`
  * `<!-- region:<name> -->`
...and is per-file-type configurable via `snippet_regions.markers` so a
downstream repo can map its own comment styles to file extensions.

Resolution:
  * a CodeSnippet reference names its own `file=` — that file must exist and
    must define the region.
  * a prose mention carries no file — the region must exist somewhere under the
    declared `snippet_regions.source_roots`. With no source roots configured,
    prose scanning is skipped (there is nothing to resolve against).

Escape hatch: a `# snippet-region-ok: <reason>` marker on the reference line,
or the line immediately above it, suppresses the finding — the same two-line
window used by action-pinning, count-drift, and file-line-refs.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import output
from jk_standards.config import Config

# The default marker comment prefixes, matching CodeSnippet.astro's ext-agnostic
# behavior: any of the three forms is recognized in any source file.
_DEFAULT_PREFIXES: tuple[str, ...] = ("//", "#", "<!--")

# A CodeSnippet tag and its file= / region= attributes. Attribute order is not
# fixed, so file and region are pulled out of the captured attr text separately.
_CODESNIPPET_TAG_RE = re.compile(r"<CodeSnippet\b(?P<attrs>[^>]*)>")
_FILE_ATTR_RE = re.compile(r"\bfile\s*=\s*[\"'](?P<val>[^\"']+)[\"']")
_REGION_ATTR_RE = re.compile(r"\bregion\s*=\s*[\"'](?P<val>[^\"']+)[\"']")

# A prose `region:<name>` mention. `\bregion:` deliberately does NOT match
# inside `endregion:` (no word boundary before the `r`), and `region=` (the
# CodeSnippet attribute) is excluded by the required colon.
_PROSE_REF_RE = re.compile(r"\bregion:(?P<name>[\w.-]+)")

# The escape-hatch marker. Matched anywhere on the line regardless of the
# surrounding comment syntax (.md `<!-- -->`, .mdx `{/* */}`, `#`).
_ESCAPE_RE = re.compile(r"snippet-region-ok\b")


def _marker_res(prefixes: tuple[str, ...]) -> list[re.Pattern]:
    """Compile one anchored marker regex per comment prefix."""
    pats: list[re.Pattern] = []
    for prefix in prefixes:
        if prefix == "<!--":
            pats.append(re.compile(r"^\s*<!--\s*region:(?P<name>[\w.-]+)\s*-->\s*$"))
        else:
            pats.append(re.compile(rf"^\s*{re.escape(prefix)}\s*region:(?P<name>[\w.-]+)\s*$"))
    return pats


def _prefixes_for(ext: str, cfg: Config) -> tuple[str, ...]:
    for syntax in cfg.snippet_markers:
        if ext in syntax.extensions:
            return tuple(syntax.prefixes)
    return _DEFAULT_PREFIXES


def _regions_in_file(path: Path, cfg: Config) -> set[str]:
    """The set of region names defined by markers in `path`."""
    pats = _marker_res(_prefixes_for(path.suffix, cfg))
    names: set[str] = set()
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        for pat in pats:
            m = pat.match(line)
            if m:
                names.add(m.group("name"))
                break
    return names


def _codesnippet_refs(line: str) -> list[tuple[str, str]]:
    """Return `(region, file)` pairs for every CodeSnippet tag on the line."""
    refs: list[tuple[str, str]] = []
    for tag in _CODESNIPPET_TAG_RE.finditer(line):
        attrs = tag.group("attrs")
        fm = _FILE_ATTR_RE.search(attrs)
        rm = _REGION_ATTR_RE.search(attrs)
        if fm and rm:
            refs.append((rm.group("val"), fm.group("val")))
    return refs


def _iter_snippet_docs(root: Path, cfg: Config) -> list[Path]:
    """Doc files to scan for references. Falls back to the top-level doc_roots
    when `snippet_regions.doc_roots` is not configured."""
    roots = cfg.snippet_doc_roots or cfg.doc_roots
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
    errors = 0
    region_cache: dict[Path, set[str]] = {}

    def regions_of(path: Path) -> set[str]:
        if path not in region_cache:
            region_cache[path] = _regions_in_file(path, cfg) if path.is_file() else set()
        return region_cache[path]

    # Every region name defined across the declared source roots — the resolution
    # target for prose mentions, which (unlike CodeSnippet) name no file.
    all_regions: set[str] = set()
    have_source_roots = bool(cfg.snippet_source_roots)
    for source_root in cfg.snippet_source_roots:
        base = root / source_root.path
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if source_root.extensions and not any(
                path.name.endswith(e) for e in source_root.extensions
            ):
                continue
            all_regions |= regions_of(path)

    for path in _iter_snippet_docs(root, cfg):
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, start=1):
            suppressed = bool(_ESCAPE_RE.search(line)) or (
                lineno >= 2 and bool(_ESCAPE_RE.search(lines[lineno - 2]))
            )
            if suppressed:
                continue

            for region, src in _codesnippet_refs(line):
                target = root / src
                if not target.is_file():
                    output.error(
                        rel,
                        lineno,
                        f"CodeSnippet references missing file {src!r} "
                        f"(region {region!r}) — fix the path "
                        f"(or add # snippet-region-ok: <reason>)",
                    )
                    errors += 1
                elif region not in regions_of(target):
                    output.error(
                        rel,
                        lineno,
                        f"CodeSnippet region {region!r} has no marker in {src} — "
                        f"add a region:{region} marker there "
                        f"(or add # snippet-region-ok: <reason>)",
                    )
                    errors += 1

            if have_source_roots:
                for name in {m.group("name") for m in _PROSE_REF_RE.finditer(line)}:
                    if name not in all_regions:
                        output.error(
                            rel,
                            lineno,
                            f"region reference {name!r} matches no marker in the "
                            f"declared source roots "
                            f"(or add # snippet-region-ok: <reason>)",
                        )
                        errors += 1

    if errors == 0:
        output.summary("snippet-regions: all region references resolve to markers")
    return errors
