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
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from jk_standards import output
from jk_standards.checks import doc_drift
from jk_standards.config import Config, ConfigError

# The per-module floor map. Committed but deliberately OUT of emit.EMITTERS and
# the jk-standards.yaml ``generated:`` list (D016) so ``emit all`` never
# freshens it — that exclusion is what lets the ratchet catch a regression
# instead of silently self-healing. Path is a module constant (not a Config
# field) so S01 adds no config-schema surface.
BASELINE_PATH = "baselines/doc-coverage.json"

# `doc-coverage-ok` after a comment opener. A Python `#` comment or a C++ `//`
# line comment both open a valid waiver, so the same escape hatch works whether
# the module is on the ast path or the tree-sitter path.
_MARKER_RE = re.compile(r"(?:#|//)\s*doc-coverage-ok\b")
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


# C++ source suffixes routed to the tree-sitter enumerator. Everything else
# (notably ``.py``, and any other configured extension) stays on the unchanged
# Python ast path, so dispatch never alters existing Python behaviour.
_CPP_EXTENSIONS = (
    ".cpp",
    ".cc",
    ".cxx",
    ".c++",
    ".hpp",
    ".hh",
    ".hxx",
    ".h++",
    ".h",
    ".c",
)


def _is_cpp(rel: str) -> bool:
    return rel.endswith(_CPP_EXTENSIONS)


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

    Files are dispatched by extension. C++ sources (``.cpp``/``.hpp``/...) go
    through the tree-sitter enumerator in :mod:`doc_coverage_cpp`; everything
    else stays on the Python ast path. Both return identical :class:`DocUnit`
    records, so the drift/mention OR-signals and the downstream emitter are
    unchanged regardless of language.

    Graceful degradation: when a C++ source is configured but tree-sitter-cpp is
    not installed, the C++ files contribute zero units and a single summary line
    names how many files were skipped — so a misconfigured repo is diagnosable
    from CI logs rather than silently dropping files.
    """
    # Imported lazily to avoid a circular import (doc_coverage_cpp imports
    # ``DocUnit`` from this module) and to keep the native grammar off the
    # zero-dependency import path until a C++ file is actually enumerated.
    from jk_standards.checks import doc_coverage_cpp

    patterns = _drift_patterns(root, cfg)
    tokens = _mention_tokens(root, cfg)
    cpp_parser_absent = doc_coverage_cpp._get_cpp_parser() is None
    cpp_skipped = 0
    units: list[DocUnit] = []
    for path in _iter_py_files(root, cfg):
        rel = path.relative_to(root).as_posix()
        drift = any(doc_drift._matches(p, [rel], set()) for p in patterns)
        if _is_cpp(rel):
            if cpp_parser_absent:
                cpp_skipped += 1
                continue
            units.extend(doc_coverage_cpp.cpp_units_for_file(rel, path.read_bytes(), drift, tokens))
        else:
            source = path.read_text(encoding="utf-8", errors="replace")
            units.extend(_units_for_file(rel, source, drift, tokens))
    if cpp_skipped:
        output.summary(
            "doc-coverage: C++ source root configured but tree-sitter-cpp not "
            f"installed — install jk-standards[cpp]; skipping {cpp_skipped} C++ file(s)"
        )
    return units


def _has_waiver(path: Path) -> bool:
    """True if a `doc-coverage-ok:` marker sits in the leading comment block.

    "Top of file" means before the first non-comment, non-blank line — a
    shebang, `#pragma`, or a `# doc-coverage-ok:` / `// doc-coverage-ok:`
    header counts; a mention buried in code or a docstring does not. Both the
    Python `#` and the C++ `//` comment openers are accepted so a bare C++
    header (e.g. a generated one) is waivable exactly like a Python module.
    """
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith(("#", "//")):
            break
        if _MARKER_RE.search(stripped):
            return True
    return False


def per_module_counts(units: list[DocUnit]) -> dict[str, tuple[int, int]]:
    """Aggregate the per-unit records into ``{module: (documented, total)}``.

    The module key is :attr:`DocUnit.file` — the exact repo-relative posix key
    ``run()``'s ``by_file`` and the baseline map both use. Counts are stored as
    an integer fraction (not a rounded float) so the ratchet can compare live
    vs. floor by exact cross-multiplication, immune to float-rounding noise.
    """
    counts: dict[str, tuple[int, int]] = {}
    for u in units:
        documented, total = counts.get(u.file, (0, 0))
        counts[u.file] = (documented + int(u.documented), total + 1)
    return counts


def _load_baseline(path: Path) -> dict[str, tuple[int, int]] | None:
    """Load the committed floor map, or ``None`` when no baseline exists yet.

    Returns ``{module: (documented, total)}``. A missing file is the first-run
    signal (``None``) — not an error. A file that is not valid JSON, or whose
    shape does not match ``{"modules": {mod: {"documented": int, "total":
    int}}}``, raises :class:`ConfigError` so the CLI surfaces it as a config
    error (exit 2) rather than a traceback — mirroring drift-map parse handling.
    """
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as e:  # JSONDecodeError is a ValueError subclass
        raise ConfigError(f"{path}: malformed baseline JSON: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("modules"), dict):
        raise ConfigError(f"{path}: baseline must be a mapping with a 'modules' object")
    floors: dict[str, tuple[int, int]] = {}
    for mod, entry in data["modules"].items():
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("documented"), int)
            or not isinstance(entry.get("total"), int)
            or isinstance(entry.get("documented"), bool)
            or isinstance(entry.get("total"), bool)
        ):
            raise ConfigError(
                f"{path}: module {mod!r} must map to {{'documented': int, 'total': int}}"
            )
        floors[str(mod)] = (entry["documented"], entry["total"])
    return floors


def _ratio(documented: int, total: int) -> float:
    return documented / total if total else 1.0


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

    # Per-module baseline ratchet — composes with (does not replace) the binary
    # gate above. Recompute live per-module ratios, compare each against its
    # committed floor, and hard-fail any module that dropped below it.
    counts = per_module_counts(units)
    floors = _load_baseline(root / BASELINE_PATH)
    regressed = 0
    evaluated = 0
    if floors is None:
        baseline_note = "no committed baseline (run --update-baseline to record a floor)"
    else:
        for rel, (live_doc, live_total) in sorted(counts.items()):
            floor = floors.get(rel)
            if floor is None:
                continue  # new module — not in the baseline, first-seen passes
            evaluated += 1
            base_doc, base_total = floor
            # Exact fraction compare: live < floor iff the cross-products
            # disagree. No float rounding, so no false regression on noise.
            if live_doc * base_total < base_doc * live_total:
                output.error(
                    rel,
                    1,
                    f"doc-coverage: module {rel} documentation coverage regressed "
                    f"below its baseline floor — was {base_doc}/{base_total} "
                    f"({_ratio(base_doc, base_total):.1%}), now {live_doc}/{live_total} "
                    f"({_ratio(live_doc, live_total):.1%}). Restore a docstring, or "
                    f"ratchet the floor with --update-baseline --allow-regression.",
                )
                regressed += 1
        baseline_note = (
            f"{evaluated} module(s) evaluated against baseline, {regressed} ratchet failure(s)"
        )

    output.summary(
        f"doc-coverage: {len(units)} public unit(s) across {len(by_file)} "
        f"module(s), {failing} fully-undocumented module(s), "
        f"{waived} waived via doc-coverage-ok; {baseline_note}"
    )
    return failing + regressed


def _write_baseline(path: Path, counts: dict[str, tuple[int, int]]) -> None:
    """Serialize the live per-module fractions as the committed floor map.

    Byte-idempotent by construction: sorted keys, 2-space indent, trailing
    newline — the same stable shape :func:`emit._serialize` uses, inlined here
    because ``checks/*.py`` may not import :mod:`jk_standards.emit` (the
    ``checks-no-emit`` boundary rule). Re-recording an unchanged tree therefore
    reproduces the file byte-for-byte, so a byte-comparison test cannot drift.
    """
    payload = {
        "modules": {
            mod: {"documented": documented, "total": total}
            for mod, (documented, total) in sorted(counts.items())
        }
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def update_baseline(root: Path, cfg: Config, allow_regression: bool = False) -> int:
    """Record (or ratchet up) the per-module floor map — the explicit writer.

    This is the ONLY path that writes ``baselines/doc-coverage.json``; a plain
    :func:`run` never mutates it, and it is deliberately excluded from
    ``emit all`` (D016) so the floor can never silently self-heal.

    Ratchet-up semantics (D015): recording a floor for a new module, and raising
    or holding an existing floor, are always allowed. **Lowering** an existing
    floor — the live fraction dropped below the recorded one — is refused unless
    ``allow_regression`` is passed, so accidentally blessing a real regression as
    the new floor takes a deliberate, auditable opt-in. When any floor would be
    lowered without the opt-in, the file is left untouched and each offending
    module is named via ``::error`` (exit non-zero); nothing is partially written.

    Returns 0 on a successful write, or the count of would-be-lowered modules
    when the write is refused. A malformed existing baseline bubbles up as
    :class:`ConfigError` (CLI exit 2) — you cannot ratchet on top of garbage.
    """
    if not cfg.doc_coverage_source_roots:
        output.summary("doc-coverage: no source roots configured — baseline not written")
        return 0

    units = enumerate_units(root, cfg)
    counts = per_module_counts(units)
    path = root / BASELINE_PATH
    floors = _load_baseline(path)  # None on first run; ConfigError if malformed

    lowered = 0
    if floors is not None and not allow_regression:
        for rel, (live_doc, live_total) in sorted(counts.items()):
            floor = floors.get(rel)
            if floor is None:
                continue  # new module — recording its floor is always allowed
            base_doc, base_total = floor
            # Exact fraction compare (cross-multiply) — same test the ratchet
            # uses, so "would refuse to lower" mirrors "would fail the gate".
            if live_doc * base_total < base_doc * live_total:
                output.error(
                    rel,
                    1,
                    f"doc-coverage: refusing to lower the baseline floor for module "
                    f"{rel} — floor is {base_doc}/{base_total} "
                    f"({_ratio(base_doc, base_total):.1%}), live is "
                    f"{live_doc}/{live_total} ({_ratio(live_doc, live_total):.1%}). "
                    f"Re-run with --allow-regression to record the lower floor.",
                )
                lowered += 1

    if lowered:
        output.summary(
            f"doc-coverage: baseline NOT written — {lowered} module(s) would drop "
            f"below their recorded floor; pass --allow-regression to override"
        )
        return lowered

    _write_baseline(path, counts)
    action = "recorded" if floors is None else "updated"
    output.summary(
        f"doc-coverage: baseline {action} at {BASELINE_PATH} — "
        f"{len(counts)} module(s), {len(units)} public unit(s)"
    )
    return 0
