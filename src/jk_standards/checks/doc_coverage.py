"""doc-coverage: every code module must be documented *somewhere*.

The doc-drift checks catch a doc that lies about code. This check catches the
opposite gap: code that no doc — and no docstring — describes at all. It walks
the configured Python source roots, enumerates each module's public
documentable units (the module itself, its top-level public classes and
functions, and the public methods of those classes), and asks of every unit
whether it is documented by ANY of three independent OR-signals:

1. **docstring** — the unit carries a non-empty docstring.
2. **drift**     — the unit's file matches a `sources:` glob in the drift map,
                   so a change to it is already touch-correlated to a doc.
3. **mention**   — the unit's bare symbol name appears as a whole word in one
                   of the configured doc scopes (prose that names it).

The gate is deliberately lenient: it fails at MODULE granularity. A module is
flagged only when EVERY one of its public units is undocumented by all three
signals — a genuinely bare file that nothing, anywhere, describes. One
`::error file=...,line=...` is emitted per fully-undocumented module so it
surfaces inline on PRs.

Escape hatch: a top-of-file ``# doc-coverage-ok: <reason>`` comment (in the
leading comment block, before the first code) waives a module in place with
its reason recorded. The summary line always reports how many waivers are live
so rising escape-hatch usage stays visible in CI logs.

Scope: Python-only. The enumerator returns per-unit records carrying all three
signal booleans, so a downstream emitter can reuse the walk without re-parsing.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from jk_standards import output
from jk_standards.checks import doc_drift
from jk_standards.config import Config

# `doc-coverage-ok` after a `#` comment opener (Python's only comment form).
_MARKER_RE = re.compile(r"#\s*doc-coverage-ok\b")
# Identifier-ish word tokens for the "mention" corpus. `\w` includes the
# underscore, so a symbol like `load_config` is a single token and set
# membership is exactly a word-boundary match for any Python identifier.
_TOKEN_RE = re.compile(r"\w+")


@dataclass
class DocUnit:
    """One public documentable unit and its three OR-signals.

    ``documented`` is the disjunction the S01 gate consumes; the individual
    booleans are retained so a downstream worklist can report *why* a unit is
    (un)documented without re-walking the tree.
    """

    file: str  # repo-relative posix path of the containing module
    kind: str  # "module" | "class" | "function" | "method"
    name: str  # bare symbol name (module stem for the module unit)
    lineno: int
    has_docstring: bool
    drift_match: bool
    mention: bool

    @property
    def documented(self) -> bool:
        return self.has_docstring or self.drift_match or self.mention


def _iter_py_files(root: Path, cfg: Config) -> list[Path]:
    """Every source file under the configured doc_coverage source roots."""
    out: list[Path] = []
    for source_root in cfg.doc_coverage_source_roots:
        base = root / source_root.path
        if not base.is_dir():
            continue
        exts = source_root.extensions or [".py"]
        for path in sorted(base.rglob("*")):
            if path.is_file() and any(path.name.endswith(e) for e in exts):
                out.append(path)
    return out


def _drift_patterns(root: Path, cfg: Config) -> list[str]:
    """All `sources:` globs across the drift map's mappings.

    A missing drift map simply yields no patterns — the drift signal is then
    always off and the check falls back to the docstring and mention signals.
    """
    map_path = root / cfg.drift_map
    if not map_path.is_file():
        return []
    data = yaml.safe_load(map_path.read_text(encoding="utf-8")) or {}
    patterns: list[str] = []
    for mapping in data.get("mappings", []):
        if isinstance(mapping, dict):
            patterns.extend(str(s) for s in mapping.get("sources", []))
    return patterns


def _mention_tokens(root: Path, cfg: Config) -> set[str]:
    """The set of whole-word tokens found across all configured doc scopes.

    Read once for the whole run; a symbol is "mentioned" iff its bare name is
    in this set. Unreadable/binary bytes are replaced rather than raising.
    """
    tokens: set[str] = set()
    for scope in cfg.doc_coverage_doc_scopes:
        base = root / scope
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            tokens.update(_TOKEN_RE.findall(text))
    return tokens


def _is_public(name: str) -> bool:
    return not name.startswith("_")


_FUNC_NODES = (ast.FunctionDef, ast.AsyncFunctionDef)


def _units_for_file(rel: str, source: str, drift: bool, tokens: set[str]) -> list[DocUnit]:
    """Enumerate the module unit plus public top-level defs and methods.

    A file that does not parse degrades to a single module unit with no
    docstring signal (drift/mention still apply), so a syntax error surfaces
    as an ordinary bare-module finding rather than a traceback.
    """

    def unit(kind: str, name: str, lineno: int, has_doc: bool) -> DocUnit:
        return DocUnit(
            file=rel,
            kind=kind,
            name=name,
            lineno=lineno,
            has_docstring=has_doc,
            drift_match=drift,
            mention=name in tokens,
        )

    stem = rel.rsplit("/", 1)[-1].removesuffix(".py")
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return [unit("module", stem, 1, has_doc=False)]

    units = [unit("module", stem, 1, has_doc=bool(ast.get_docstring(tree)))]
    for node in tree.body:
        if isinstance(node, _FUNC_NODES) and _is_public(node.name):
            units.append(unit("function", node.name, node.lineno, bool(ast.get_docstring(node))))
        elif isinstance(node, ast.ClassDef) and _is_public(node.name):
            units.append(unit("class", node.name, node.lineno, bool(ast.get_docstring(node))))
            for sub in node.body:
                if isinstance(sub, _FUNC_NODES) and _is_public(sub.name):
                    units.append(unit("method", sub.name, sub.lineno, bool(ast.get_docstring(sub))))
    return units


def enumerate_units(root: Path, cfg: Config) -> list[DocUnit]:
    """Walk the configured source roots and return per-unit signal records.

    This is the reusable seam: a downstream emitter consumes these records
    directly rather than re-parsing the source tree.
    """
    patterns = _drift_patterns(root, cfg)
    tokens = _mention_tokens(root, cfg)
    units: list[DocUnit] = []
    for path in _iter_py_files(root, cfg):
        rel = path.relative_to(root).as_posix()
        drift = any(doc_drift._matches(p, [rel], set()) for p in patterns)
        source = path.read_text(encoding="utf-8", errors="replace")
        units.extend(_units_for_file(rel, source, drift, tokens))
    return units


def _has_waiver(path: Path) -> bool:
    """True if a `# doc-coverage-ok:` marker sits in the leading comment block.

    "Top of file" means before the first non-comment, non-blank line — a
    shebang or `# doc-coverage-ok:` header counts; a mention buried in code or
    a docstring does not.
    """
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("#"):
            break
        if _MARKER_RE.search(stripped):
            return True
    return False


def run(root: Path, cfg: Config) -> int:
    if not cfg.doc_coverage_source_roots:
        output.summary("doc-coverage: no source roots configured — skipped")
        return 0

    units = enumerate_units(root, cfg)
    by_file: dict[str, list[DocUnit]] = {}
    for u in units:
        by_file.setdefault(u.file, []).append(u)

    failing = 0
    waived = 0
    for rel, file_units in sorted(by_file.items()):
        if any(u.documented for u in file_units):
            continue
        if _has_waiver(root / rel):
            waived += 1
            continue
        output.error(
            rel,
            1,
            f"doc-coverage: module {rel} is fully undocumented — none of its "
            f"{len(file_units)} public unit(s) has a docstring, a drift-map "
            f"sources glob match, or a whole-word mention in a doc scope. Add a "
            f"docstring to any unit, or waive with a top-of-file "
            f"'# doc-coverage-ok: <reason>' marker.",
        )
        failing += 1

    output.summary(
        f"doc-coverage: {len(units)} public unit(s) across {len(by_file)} "
        f"module(s), {failing} fully-undocumented module(s), "
        f"{waived} waived via doc-coverage-ok"
    )
    return failing
