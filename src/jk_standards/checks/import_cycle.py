"""import-cycle: no module-level import cycle within a package.

A circular *runtime* import between two modules of the same package is a latent
crash waiting for an import-order change to trigger it, and it couples the two
files so neither can be understood — or moved — alone. This check builds the
module import graph from the package's own module-level imports, finds every
strongly-connected component larger than one module (a cycle), and reports it.

The detector is split into three seams so each can be proven in isolation:

1. **extract_edges** (this task) — a per-language dispatch that turns one
   module's source into the :class:`ImportEdge` records for its module-level
   imports, resolved to candidate dotted module paths. Only Python is wired
   today; the seam is where a future language extractor registers.
2. **the SCC engine** (S01/T02) — Tarjan's algorithm over the graph those edges
   build, returning each cycle as a component of >1 module.
3. **run(root, cfg)** (S01/T03) — walks the package, assembles the graph,
   filters edges to the package's own modules, and emits one annotation per
   cycle at file:line in deterministic order.

Only *module-level* imports form edges: an import nested inside a function or a
class body is deferred at runtime and cannot cause an import-time cycle, and an
import guarded by ``if TYPE_CHECKING:`` never executes at runtime at all. Both
are therefore excluded here, so the graph reflects only the edges that a real
import actually traverses.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path

from jk_standards import output
from jk_standards.config import Config

# `import-cycle-ok` after any common comment opener. Requiring an opener keeps
# the marker from matching source that merely mentions the phrase. Mirrors the
# `boundaries` escape hatch: a marker on an in-cycle import line (or the line
# immediately above it) waives the whole cycle, and the summary reports the live
# suppression count so rising waiver usage stays visible in CI logs.
_MARKER_RE = re.compile(r"(?:#|//|/\*|<!--|--|;)\s*import-cycle-ok\b")


@dataclass(frozen=True)
class ImportEdge:
    """One directed module-level import edge ``source`` -> ``target``.

    ``source`` and ``target`` are dotted module paths (e.g. ``pkg.a``);
    ``target`` is a *candidate* path — the extractor does not yet know which
    modules belong to the package, so ``run()`` filters edges to the package's
    own module set before building the graph. ``lineno`` is the 1-based line of
    the import statement, retained so a reported cycle can anchor at file:line.
    Frozen so edges are hashable and de-duplicable.
    """

    source: str
    target: str
    lineno: int


def _is_type_checking_guard(test: ast.expr) -> bool:
    """True when an ``if`` test is a ``TYPE_CHECKING`` guard.

    Matches both the bare ``if TYPE_CHECKING:`` (imported name) and the dotted
    ``if typing.TYPE_CHECKING:`` (attribute) forms. Imports inside such a block
    never run at import time, so they must not form a runtime edge.
    """
    if isinstance(test, ast.Name):
        return test.id == "TYPE_CHECKING"
    if isinstance(test, ast.Attribute):
        return test.attr == "TYPE_CHECKING"
    return False


def _iter_module_level_imports(body: list[ast.stmt]) -> list[ast.Import | ast.ImportFrom]:
    """Collect the ``import`` / ``from``-``import`` statements that run at import time.

    Descends through the compound statements that still execute at module load —
    ``if`` (except a ``TYPE_CHECKING`` guard, which is skipped), ``try`` and its
    handlers/else/finally (the ``try: import x except ImportError:`` fallback is
    a real runtime edge), and ``with`` — but deliberately stops at ``def`` /
    ``async def`` / ``class`` bodies, whose imports are deferred until the unit
    is called and so cannot cause an import-time cycle.
    """
    found: list[ast.Import | ast.ImportFrom] = []
    for node in body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            found.append(node)
        elif isinstance(node, ast.If):
            if _is_type_checking_guard(node.test):
                continue
            found.extend(_iter_module_level_imports(node.body))
            found.extend(_iter_module_level_imports(node.orelse))
        elif isinstance(node, ast.Try):
            found.extend(_iter_module_level_imports(node.body))
            for handler in node.handlers:
                found.extend(_iter_module_level_imports(handler.body))
            found.extend(_iter_module_level_imports(node.orelse))
            found.extend(_iter_module_level_imports(node.finalbody))
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            found.extend(_iter_module_level_imports(node.body))
        # FunctionDef / AsyncFunctionDef / ClassDef bodies are intentionally not
        # descended into: their imports are function-local, not module-level.
    return found


def _resolve_relative(module_name: str, level: int, sub: str | None) -> str | None:
    """Resolve a relative ``from`` import to its absolute base module path.

    ``module_name`` is treated as a regular module, so ``level`` 1 anchors at
    the current package (drop the module's own trailing component), ``level`` 2
    at the parent package, and so on. ``sub`` is the module named after the
    dots (``from ..pkg import x`` -> ``sub == "pkg"``). Returns ``None`` when the
    level climbs above the top-level package (an unresolvable import).
    """
    parts = module_name.split(".")
    if level > len(parts):
        return None
    anchor = parts[: len(parts) - level]
    if sub:
        anchor = anchor + sub.split(".")
    return ".".join(anchor) if anchor else None


def _extract_python_edges(module_name: str, source: str) -> list[ImportEdge]:
    """Return the module-level import edges from one Python module's source.

    ``module_name`` is the dotted path of the module the source belongs to (the
    edge ``source``). For each module-level import the extractor emits candidate
    ``target`` paths:

    * ``import a.b.c`` -> ``a.b.c`` (the imported submodule path).
    * ``from X import a, b`` -> ``X``, ``X.a``, ``X.b`` — both the package
      ``X`` (whose ``__init__`` runs) and each ``X.<name>`` submodule candidate,
      because ``from X import a`` may bind either a submodule or an attribute.
      ``run()`` keeps only the candidates that are real package modules.
    * relative imports (``from . import x``) are resolved against
      ``module_name``; an import that climbs above the top package is dropped.

    Raises :class:`SyntaxError` when the source does not parse — the orchestrator
    (T03) catches it and surfaces the offending file in a summary line rather
    than dropping it silently.
    """
    tree = ast.parse(source)
    edges: list[ImportEdge] = []
    for node in _iter_module_level_imports(tree.body):
        if isinstance(node, ast.Import):
            for alias in node.names:
                edges.append(ImportEdge(module_name, alias.name, node.lineno))
        else:  # ast.ImportFrom
            if node.level:
                base = _resolve_relative(module_name, node.level, node.module)
            else:
                base = node.module
            if base is None:
                continue
            edges.append(ImportEdge(module_name, base, node.lineno))
            for alias in node.names:
                if alias.name == "*":
                    continue
                edges.append(ImportEdge(module_name, f"{base}.{alias.name}", node.lineno))
    return edges


# Per-language extractor dispatch seam. Keyed by a language tag; today only
# Python is wired. A future language adds one entry here plus its extractor,
# and the rest of the detector (graph build, SCC engine, run) is unchanged.
_LANGUAGE_EXTRACTORS = {
    "python": _extract_python_edges,
}


def _language_for(rel: str) -> str | None:
    """Map a repo-relative source path to its extractor language tag, or None."""
    if rel.endswith(".py"):
        return "python"
    return None


def extract_edges(module_name: str, rel: str, source: str) -> list[ImportEdge]:
    """Dispatch one source file to its per-language edge extractor.

    Files with no registered extractor (``_language_for`` returns ``None``)
    contribute zero edges, so a mixed-language tree degrades cleanly to the
    languages the detector understands.
    """
    language = _language_for(rel)
    if language is None:
        return []
    return _LANGUAGE_EXTRACTORS[language](module_name, source)


# --- SCC engine (S01/T02) ----------------------------------------------------
#
# The extractor over-generates candidate targets that may name modules outside
# the package (``import os``) or attributes that are not modules at all. The
# graph is where those candidates are pruned: only edges whose *both* endpoints
# are real modules of the package under analysis survive, so the adjacency
# reflects exactly the runtime import edges internal to the package. Tarjan's
# algorithm then returns every strongly-connected component of more than one
# module — each such component is an import cycle.


def _build_graph(edges: list[ImportEdge], module_set: set[str]) -> dict[str, list[str]]:
    """Build the internal module adjacency graph from candidate edges.

    ``module_set`` is the set of dotted paths that are real modules of the
    package under analysis. An edge survives only when both its ``source`` and
    ``target`` are in that set, which discards the extractor's over-generated
    candidates (stdlib/third-party targets, and ``X.name`` candidates that name
    an attribute rather than a submodule). Self-edges (a module importing
    itself) are dropped: they are not a cycle between distinct modules.

    Returns a mapping from every module in ``module_set`` to its sorted list of
    in-package import targets. Every module is a key even with no out-edges, so
    the SCC pass can iterate the full node set; neighbor lists are sorted so the
    graph — and thus the reported cycles — are deterministic.
    """
    adjacency: dict[str, set[str]] = {m: set() for m in module_set}
    for edge in edges:
        if (
            edge.source in module_set
            and edge.target in module_set
            and edge.source != edge.target
        ):
            adjacency[edge.source].add(edge.target)
    return {module: sorted(targets) for module, targets in adjacency.items()}


def _tarjan_sccs(graph: dict[str, list[str]]) -> list[list[str]]:
    """Return every strongly-connected component of more than one node.

    Tarjan's algorithm, implemented iteratively with an explicit work stack so a
    deep import chain cannot overflow Python's recursion limit on a large
    package. Single-node components (the acyclic common case) are omitted — only
    components of size >= 2, which are exactly the import cycles, are returned.

    Determinism: root nodes are visited in sorted order, each returned component
    is sorted, and the list of components is sorted, so the same graph always
    yields the same cycles in the same order regardless of dict iteration order.
    """
    order: dict[str, int] = {}  # DFS discovery index per node
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    scc_stack: list[str] = []
    counter = 0
    components: list[list[str]] = []

    for root in sorted(graph):
        if root in order:
            continue
        # Explicit DFS stack of (node, next-neighbor-index) frames.
        work: list[tuple[str, int]] = [(root, 0)]
        while work:
            node, next_i = work[-1]
            if next_i == 0:
                order[node] = counter
                lowlink[node] = counter
                counter += 1
                scc_stack.append(node)
                on_stack[node] = True

            neighbors = graph[node]
            descended = False
            i = next_i
            while i < len(neighbors):
                nbr = neighbors[i]
                if nbr not in order:
                    # Resume this frame after the child, then descend.
                    work[-1] = (node, i + 1)
                    work.append((nbr, 0))
                    descended = True
                    break
                if on_stack.get(nbr):
                    lowlink[node] = min(lowlink[node], order[nbr])
                i += 1
            if descended:
                continue

            # All neighbors processed: node is a root of its SCC iff its lowlink
            # equals its own discovery index. Pop the component off the stack.
            if lowlink[node] == order[node]:
                component: list[str] = []
                while True:
                    member = scc_stack.pop()
                    on_stack[member] = False
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))

            work.pop()
            if work:  # propagate lowlink up to the parent frame
                parent = work[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])

    return sorted(components)


# --- run() orchestration (S01/T03) -------------------------------------------
#
# The orchestrator ties the extractor and the SCC engine together into a
# check-shaped entry point. It walks each package's ``.py`` files, assigns every
# file its dotted module name (so the extractor's candidate targets can be
# matched against real in-package modules), assembles the candidate edges,
# builds the internal graph, and turns each strongly-connected component into a
# reported cycle anchored at the file:line of one of its import statements.


@dataclass(frozen=True)
class Cycle:
    """One detected import cycle, ready to emit at file:line.

    ``members`` is the full sorted set of dotted module names in the cycle (the
    chain a reader needs to see to understand the loop). The ``anchor_*`` fields
    name one concrete in-cycle edge — ``anchor_source`` imports ``anchor_target``
    at ``anchor_file``:``anchor_lineno`` — so the annotation lands on a real
    import statement a maintainer can go delete. The anchor is the
    deterministically smallest in-cycle edge, so the same cycle always reports at
    the same line.
    """

    members: tuple[str, ...]
    anchor_source: str
    anchor_target: str
    anchor_file: str
    anchor_lineno: int
    suppressed: bool = False


@dataclass(frozen=True)
class AnalysisResult:
    """The outcome of one :func:`_analyze` pass over a set of packages.

    ``cycles`` are the detected import cycles in deterministic order;
    ``parse_failures`` are the repo-relative paths of files whose source did not
    parse (a :class:`SyntaxError` from the extractor), retained so ``run()`` can
    surface them in a summary line rather than dropping them silently.

    ``__len__``/``__iter__`` are defined over ``cycles`` alone, so a caller can
    treat the result as "the cycles" — ``bool(result)`` is true iff at least one
    cycle was found, and iterating yields the cycles.
    """

    cycles: tuple[Cycle, ...]
    parse_failures: tuple[str, ...]

    def __len__(self) -> int:
        return len(self.cycles)

    def __iter__(self):
        return iter(self.cycles)


def _module_name(pkg_dir: Path, path: Path) -> str:
    """Dotted module path for ``path`` within the package rooted at ``pkg_dir``.

    The name is taken relative to the package's *parent* directory, so the
    top-level package component is included (``src/jk_standards/checks/x.py`` ->
    ``jk_standards.checks.x``). A package ``__init__.py`` collapses to the
    package name itself (``pkg/__init__.py`` -> ``pkg``), matching how the
    extractor names the ``from pkg import ...`` target.
    """
    rel = path.relative_to(pkg_dir.parent)
    parts = list(rel.parts)
    parts[-1] = parts[-1].removesuffix(".py")
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _edge_is_waived(edge: ImportEdge, module_lines: dict[str, list[str]]) -> bool:
    """True when an ``# import-cycle-ok:`` marker waives this in-cycle import.

    The marker is honored on the import's own line or the line immediately above
    it (mirroring the ``boundaries`` escape hatch), so a waiver can sit inline or
    on a dedicated comment line just above the offending ``import``.
    """
    lines = module_lines.get(edge.source)
    if not lines:
        return False
    idx = edge.lineno - 1
    if 0 <= idx < len(lines) and _MARKER_RE.search(lines[idx]):
        return True
    return idx - 1 >= 0 and bool(_MARKER_RE.search(lines[idx - 1]))


def _find_cycles(
    sccs: list[list[str]],
    edges: list[ImportEdge],
    module_files: dict[str, str],
    module_lines: dict[str, list[str]],
) -> list[Cycle]:
    """Turn each strongly-connected component into a reportable :class:`Cycle`.

    For each component of >1 module, the in-cycle edges (both endpoints in the
    component) are collected and the smallest by ``(source, target, lineno)`` is
    chosen as the anchor — a component of size >= 2 always has at least one such
    edge. A cycle is marked ``suppressed`` when *any* of its in-cycle import lines
    carries an ``# import-cycle-ok:`` marker, so the loop can be waived at any one
    of its edges. Cycles are returned sorted by their member tuple so the report
    order is deterministic.
    """
    cycles: list[Cycle] = []
    for scc in sccs:
        members = set(scc)
        internal = sorted(
            (
                e
                for e in edges
                if e.source in members and e.target in members and e.source != e.target
            ),
            key=lambda e: (e.source, e.target, e.lineno),
        )
        anchor = internal[0]
        suppressed = any(_edge_is_waived(e, module_lines) for e in internal)
        cycles.append(
            Cycle(
                members=tuple(sorted(members)),
                anchor_source=anchor.source,
                anchor_target=anchor.target,
                anchor_file=module_files[anchor.source],
                anchor_lineno=anchor.lineno,
                suppressed=suppressed,
            )
        )
    return sorted(cycles, key=lambda c: c.members)


def _analyze(root: Path, packages: list[str]) -> AnalysisResult:
    """Walk ``packages`` under ``root`` and return the import cycles found.

    ``packages`` are package paths relative to ``root`` (e.g. ``pkg`` or
    ``src/jk_standards``). Every ``.py`` file is read once, named with its dotted
    module path, and run through :func:`extract_edges`; a file that does not
    parse is recorded in ``parse_failures`` instead of aborting the walk. The
    candidate edges are then filtered to the discovered module set and reduced to
    strongly-connected components by the SCC engine.
    """
    edges: list[ImportEdge] = []
    module_files: dict[str, str] = {}
    module_lines: dict[str, list[str]] = {}
    parse_failures: list[str] = []
    for pkg in packages:
        pkg_dir = root / pkg
        if not pkg_dir.is_dir():
            continue
        for path in sorted(pkg_dir.rglob("*.py")):
            if not path.is_file():
                continue
            module = _module_name(pkg_dir, path)
            rel = path.relative_to(root).as_posix()
            module_files[module] = rel
            source = path.read_text(encoding="utf-8", errors="replace")
            module_lines[module] = source.splitlines()
            try:
                edges.extend(extract_edges(module, rel, source))
            except SyntaxError:
                parse_failures.append(rel)
    module_set = set(module_files)
    graph = _build_graph(edges, module_set)
    sccs = _tarjan_sccs(graph)
    cycles = _find_cycles(sccs, edges, module_files, module_lines)
    return AnalysisResult(cycles=tuple(cycles), parse_failures=tuple(sorted(parse_failures)))


def run(root: Path, cfg: Config) -> int:
    """Check entry point: report each module-level import cycle, return the count.

    Shaped to the CHECKS contract (``run(root, cfg) -> int`` error count).
    Package selection is config-driven and *skip-when-unconfigured*, mirroring
    ``boundaries``: with no ``import_cycle.packages`` set the check emits a skip
    summary and returns 0. An out-of-shape ``import_cycle`` value never reaches
    here — ``load_config`` raises :class:`ConfigError` and the CLI maps it to
    exit 2 (D010) — so this function only ever sees a validated package list.

    Each detected cycle is emitted as one ``output.error`` at the file:line of a
    real in-cycle import, naming the full member chain so the loop is diagnosable
    straight from CI logs. A cycle waived by an ``# import-cycle-ok:`` marker is
    counted toward the live suppression total in the summary instead of erroring,
    so rising waiver usage stays visible even on an otherwise-green run.
    Unparseable files are surfaced in a summary line rather than dropped. Output
    is deterministic and carries no environment-sensitive values.
    """
    packages = cfg.import_cycle_packages
    if not packages:
        output.summary("import-cycle: no packages configured — skipped")
        return 0

    result = _analyze(root, packages)
    violations = 0
    suppressions = 0
    for cycle in result.cycles:
        if cycle.suppressed:
            suppressions += 1
            continue
        chain = " -> ".join(cycle.members)
        output.error(
            cycle.anchor_file,
            cycle.anchor_lineno,
            f"import-cycle: module-level import cycle among {len(cycle.members)} "
            f"module(s) [{chain}] — e.g. {cycle.anchor_source} imports "
            f"{cycle.anchor_target} at this line. Break the cycle by moving one of "
            f"its imports inside the function/method that uses it, or add "
            f"# import-cycle-ok: <reason> on the import line.",
        )
        violations += 1
    for rel in result.parse_failures:
        output.summary(f"import-cycle: could not parse {rel} — skipped (SyntaxError)")

    # Always emit the suppression count so rising escape-hatch usage is visible
    # in CI logs even when the run is otherwise green.
    output.summary(
        f"import-cycle: {len(packages)} package(s), {violations} cycle(s), "
        f"{suppressions} suppression(s) via import-cycle-ok, "
        f"{len(result.parse_failures)} unparseable file(s)"
    )
    return violations
