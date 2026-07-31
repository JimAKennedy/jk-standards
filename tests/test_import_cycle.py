"""Direct tests for the import-cycle detector core (S01).

Exercises the detector through its own seams — the Python edge extractor
(`_extract_python_edges` / `extract_edges`), the graph builder (`_build_graph`),
the Tarjan SCC engine (`_tarjan_sccs`), the `_analyze` walk, and the `run`
entry point — NOT through the CLI or the check registry (those are S02).

The demo cases from the slice plan are covered: a module-level A<->B cycle is
reported at file:line naming both members; making the import function-local
yields zero; a transitive A->B->C->A chain is detected; an acyclic graph
returns none; a `TYPE_CHECKING`-guarded import forms no edge. The golden
fixture pair is derived from the real `doc_coverage` <-> `doc_coverage_cpp`
modules: their shipped lazy-import form is green, and a reverted eager-import
copy is red.
"""

from pathlib import Path

import pytest

from jk_standards.checks import import_cycle as ic
from jk_standards.checks.import_cycle import ImportEdge
from jk_standards.config import Config

_REPO_ROOT = Path(__file__).resolve().parents[1]
_REAL_CHECKS = _REPO_ROOT / "src" / "jk_standards" / "checks"


def write(root: Path, rel: str, text: str) -> Path:
    """Write ``text`` to ``root/rel``, creating parent dirs; return the path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def make_pkg(root: Path, name: str, modules: dict[str, str]) -> None:
    """Create package ``name`` under ``root`` with ``{module: source}`` files.

    A ``__init__.py`` is always written (empty unless supplied in ``modules``)
    so the directory is a discoverable package.
    """
    write(root, f"{name}/__init__.py", modules.get("__init__", ""))
    for mod, source in modules.items():
        if mod == "__init__":
            continue
        write(root, f"{name}/{mod}.py", source)


# --- extractor: what does and does not form a module-level edge --------------


def test_module_level_from_import_yields_base_and_submodule_candidates():
    edges = ic._extract_python_edges("pkg.a", "from pkg import b\n")
    targets = {e.target for e in edges}
    assert "pkg" in targets  # the package whose __init__ runs
    assert "pkg.b" in targets  # the submodule candidate
    assert all(e.source == "pkg.a" and e.lineno == 1 for e in edges)


def test_plain_import_yields_the_dotted_submodule_path():
    edges = ic._extract_python_edges("pkg.a", "import pkg.b.c\n")
    assert [e.target for e in edges] == ["pkg.b.c"]


def test_function_local_import_is_not_an_edge():
    src = "def f():\n    from pkg import c\n"
    assert ic._extract_python_edges("pkg.a", src) == []


def test_class_body_import_is_not_an_edge():
    src = "class K:\n    from pkg import c\n"
    assert ic._extract_python_edges("pkg.a", src) == []


def test_type_checking_guard_bare_name_forms_no_edge():
    src = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from pkg import b\n"
    assert not any(e.target.startswith("pkg") for e in ic._extract_python_edges("pkg.a", src))


def test_type_checking_guard_dotted_attribute_forms_no_edge():
    src = "import typing\nif typing.TYPE_CHECKING:\n    from pkg import b\n"
    assert not any(e.target.startswith("pkg") for e in ic._extract_python_edges("pkg.a", src))


def test_try_except_import_is_a_real_runtime_edge():
    src = "try:\n    from pkg import fast\nexcept ImportError:\n    from pkg import slow\n"
    targets = {e.target for e in ic._extract_python_edges("pkg.a", src)}
    assert "pkg.fast" in targets and "pkg.slow" in targets


def test_relative_import_resolves_against_the_module_name():
    edges = ic._extract_python_edges("pkg.sub.a", "from . import b\n")
    assert any(e.target == "pkg.sub.b" for e in edges)


def test_relative_import_climbing_above_top_package_is_dropped():
    # `from .. import x` from a two-component module climbs to the top and past it.
    edges = ic._extract_python_edges("pkg.a", "from .. import x\n")
    assert edges == []


def test_star_import_forms_only_the_base_edge():
    edges = ic._extract_python_edges("pkg.a", "from pkg import *\n")
    assert [e.target for e in edges] == ["pkg"]


def test_extract_edges_dispatch_ignores_non_python_sources():
    assert ic.extract_edges("mod", "mod.rs", "use foo::bar;") == []


def test_extract_edges_dispatch_routes_python():
    edges = ic.extract_edges("pkg.a", "pkg/a.py", "from pkg import b\n")
    assert any(e.target == "pkg.b" for e in edges)


def test_unparseable_source_raises_syntaxerror():
    with pytest.raises(SyntaxError):
        ic._extract_python_edges("pkg.a", "def (:\n")


# --- graph builder: pruning to the in-package module set ---------------------


def test_build_graph_prunes_out_of_package_targets():
    edges = [ImportEdge("pkg.a", "os", 1), ImportEdge("pkg.a", "pkg.b", 2)]
    graph = ic._build_graph(edges, {"pkg.a", "pkg.b"})
    assert graph["pkg.a"] == ["pkg.b"]  # `os` dropped, not a package module


def test_build_graph_drops_self_edges_and_keys_every_module():
    edges = [ImportEdge("pkg.a", "pkg.a", 1)]
    graph = ic._build_graph(edges, {"pkg.a", "pkg.b"})
    assert graph == {"pkg.a": [], "pkg.b": []}  # self-edge dropped, b is a key


def test_build_graph_sorts_neighbors_for_determinism():
    edges = [ImportEdge("pkg.a", "pkg.c", 1), ImportEdge("pkg.a", "pkg.b", 2)]
    graph = ic._build_graph(edges, {"pkg.a", "pkg.b", "pkg.c"})
    assert graph["pkg.a"] == ["pkg.b", "pkg.c"]


# --- Tarjan SCC engine -------------------------------------------------------


def test_tarjan_two_cycle():
    edges = [ImportEdge("pkg.a", "pkg.b", 1), ImportEdge("pkg.b", "pkg.a", 1)]
    graph = ic._build_graph(edges, {"pkg.a", "pkg.b"})
    assert ic._tarjan_sccs(graph) == [["pkg.a", "pkg.b"]]


def test_tarjan_transitive_three_cycle():
    edges = [
        ImportEdge("pkg.a", "pkg.b", 1),
        ImportEdge("pkg.b", "pkg.c", 1),
        ImportEdge("pkg.c", "pkg.a", 1),
    ]
    graph = ic._build_graph(edges, {"pkg.a", "pkg.b", "pkg.c"})
    assert ic._tarjan_sccs(graph) == [["pkg.a", "pkg.b", "pkg.c"]]


def test_tarjan_acyclic_returns_no_component():
    graph = ic._build_graph([ImportEdge("pkg.a", "pkg.b", 1)], {"pkg.a", "pkg.b"})
    assert ic._tarjan_sccs(graph) == []


def test_tarjan_reports_disjoint_cycles_sorted():
    edges = [
        ImportEdge("pkg.a", "pkg.b", 1),
        ImportEdge("pkg.b", "pkg.a", 1),
        ImportEdge("pkg.x", "pkg.y", 1),
        ImportEdge("pkg.y", "pkg.x", 1),
    ]
    mods = {"pkg.a", "pkg.b", "pkg.x", "pkg.y"}
    assert ic._tarjan_sccs(ic._build_graph(edges, mods)) == [
        ["pkg.a", "pkg.b"],
        ["pkg.x", "pkg.y"],
    ]


def test_tarjan_is_iterative_on_a_deep_chain():
    # A long acyclic chain must not overflow Python's recursion limit; the
    # engine is iterative precisely so a large package cannot crash it.
    n = 3000
    edges = [ImportEdge(f"pkg.m{i}", f"pkg.m{i + 1}", 1) for i in range(n - 1)]
    mods = {f"pkg.m{i}" for i in range(n)}
    assert ic._tarjan_sccs(ic._build_graph(edges, mods)) == []


# --- _analyze: the demo cases over real files --------------------------------


def test_analyze_reports_module_level_two_cycle_at_file_line(tmp_path):
    make_pkg(tmp_path, "pkg", {"a": "from pkg import b\n", "b": "from pkg import a\n"})
    result = ic._analyze(tmp_path, ["pkg"])
    assert len(result) == 1
    (cycle,) = result.cycles
    assert cycle.members == ("pkg.a", "pkg.b")
    # Anchors on a real import statement (line 1 of one of the members).
    assert cycle.anchor_file in {"pkg/a.py", "pkg/b.py"}
    assert cycle.anchor_lineno == 1


def test_analyze_zero_when_the_cycle_import_is_function_local(tmp_path):
    make_pkg(
        tmp_path,
        "pkg",
        {"a": "from pkg import b\n", "b": "def use():\n    from pkg import a\n"},
    )
    assert list(ic._analyze(tmp_path, ["pkg"])) == []


def test_analyze_detects_transitive_three_module_chain(tmp_path):
    make_pkg(
        tmp_path,
        "pkg",
        {
            "a": "from pkg import b\n",
            "b": "from pkg import c\n",
            "c": "from pkg import a\n",
        },
    )
    result = ic._analyze(tmp_path, ["pkg"])
    assert len(result) == 1
    assert result.cycles[0].members == ("pkg.a", "pkg.b", "pkg.c")


def test_analyze_acyclic_graph_returns_no_cycle(tmp_path):
    make_pkg(
        tmp_path,
        "pkg",
        {"a": "from pkg import b\n", "b": "import os\n", "c": "from pkg import a\n"},
    )
    assert list(ic._analyze(tmp_path, ["pkg"])) == []


def test_analyze_type_checking_guarded_import_forms_no_cycle(tmp_path):
    guarded = (
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from pkg import a\n"
    )
    make_pkg(tmp_path, "pkg", {"a": "from pkg import b\n", "b": guarded})
    assert list(ic._analyze(tmp_path, ["pkg"])) == []


def test_analyze_self_importing_module_is_not_a_cycle(tmp_path):
    make_pkg(tmp_path, "pkg", {"a": "from pkg import a\n"})
    assert list(ic._analyze(tmp_path, ["pkg"])) == []


# --- _analyze: negative surface (parse failures, missing packages) -----------


def test_analyze_records_parse_failure_and_keeps_walking(tmp_path):
    # A broken file must surface as a parse failure, not abort the walk — the
    # A<->B cycle in the sibling files is still found.
    make_pkg(
        tmp_path,
        "pkg",
        {
            "a": "from pkg import b\n",
            "b": "from pkg import a\n",
            "broken": "def (:\n",
        },
    )
    result = ic._analyze(tmp_path, ["pkg"])
    assert result.parse_failures == ("pkg/broken.py",)
    assert len(result.cycles) == 1


def test_analyze_skips_a_missing_package_directory(tmp_path):
    result = ic._analyze(tmp_path, ["does_not_exist"])
    assert list(result) == [] and result.parse_failures == ()


# --- run(): the check-shaped entry point -------------------------------------


def _cfg(*packages: str) -> Config:
    """A Config with ``import_cycle.packages`` set (run() is config-driven)."""
    cfg = Config()
    cfg.import_cycle_packages = list(packages)
    return cfg


def test_run_emits_error_at_file_line_and_returns_cycle_count(tmp_path, capsys):
    make_pkg(tmp_path, "pkg", {"a": "from pkg import b\n", "b": "from pkg import a\n"})
    count = ic.run(tmp_path, _cfg("pkg"))
    assert count == 1
    err = capsys.readouterr().err
    assert "::error" in err
    assert "pkg.a" in err and "pkg.b" in err  # full member chain named
    assert "line=1" in err


def test_run_skips_and_returns_zero_when_no_packages_configured(tmp_path, capsys):
    count = ic.run(tmp_path, Config())
    assert count == 0
    assert "no packages configured" in capsys.readouterr().out


def test_run_surfaces_parse_failures_in_a_summary_line(tmp_path, capsys):
    make_pkg(tmp_path, "pkg", {"a": "def (:\n"})
    count = ic.run(tmp_path, _cfg("pkg"))
    assert count == 0
    out = capsys.readouterr().out
    assert "could not parse pkg/a.py" in out and "SyntaxError" in out


def test_run_output_is_deterministic_across_repeated_runs(tmp_path, capsys):
    make_pkg(
        tmp_path,
        "pkg",
        {
            "a": "from pkg import b\n",
            "b": "from pkg import a\n",
            "x": "from pkg import y\n",
            "y": "from pkg import x\n",
        },
    )
    ic.run(tmp_path, _cfg("pkg"))
    first = capsys.readouterr()
    ic.run(tmp_path, _cfg("pkg"))
    second = capsys.readouterr()
    assert first.out == second.out and first.err == second.err


def test_run_waives_cycle_via_inline_import_cycle_ok_marker(tmp_path, capsys):
    make_pkg(
        tmp_path,
        "pkg",
        {"a": "from pkg import b  # import-cycle-ok: intentional\n", "b": "from pkg import a\n"},
    )
    count = ic.run(tmp_path, _cfg("pkg"))
    assert count == 0
    captured = capsys.readouterr()
    assert "::error" not in captured.err  # the cycle is suppressed, not emitted
    assert "1 suppression(s) via import-cycle-ok" in captured.out


def test_run_honors_import_cycle_ok_marker_on_line_above(tmp_path, capsys):
    make_pkg(
        tmp_path,
        "pkg",
        {"a": "# import-cycle-ok: intentional\nfrom pkg import b\n", "b": "from pkg import a\n"},
    )
    assert ic.run(tmp_path, _cfg("pkg")) == 0
    assert "1 suppression(s) via import-cycle-ok" in capsys.readouterr().out


# --- golden fixture pair: doc_coverage <-> doc_coverage_cpp ------------------
#
# The shipped modules import each other only *lazily* (function-local) to break
# a would-be module-level cycle. The golden test copies their real source into
# an isolated package: the shipped lazy form is green, and a reverted
# eager-import copy — the cross-imports hoisted back to module level — is red.


def _copy_doc_coverage_pair(root: Path, *, eager: bool) -> None:
    """Copy the real doc_coverage pair into ``root`` as an isolated package.

    When ``eager`` is true, a module-level cross-import is added to each file,
    reproducing the eager form the shipped lazy imports were written to avoid.
    """
    write(root, "jk_standards/__init__.py", "")
    write(root, "jk_standards/checks/__init__.py", "")
    extra = {
        "doc_coverage.py": "\nfrom jk_standards.checks.doc_coverage_cpp import DocUnit as _EagerCpp\n",
        "doc_coverage_cpp.py": "\nfrom jk_standards.checks.doc_coverage import DocUnit as _EagerPy\n",
    }
    for name in ("doc_coverage.py", "doc_coverage_cpp.py"):
        source = (_REAL_CHECKS / name).read_text(encoding="utf-8")
        if eager:
            source += extra[name]
        write(root, f"jk_standards/checks/{name}", source)


def test_golden_shipped_lazy_form_is_green(tmp_path):
    _copy_doc_coverage_pair(tmp_path, eager=False)
    result = ic._analyze(tmp_path, ["jk_standards"])
    members = {m for cycle in result.cycles for m in cycle.members}
    assert "jk_standards.checks.doc_coverage" not in members
    assert "jk_standards.checks.doc_coverage_cpp" not in members
    assert list(result) == []


def test_golden_reverted_eager_form_is_red(tmp_path):
    _copy_doc_coverage_pair(tmp_path, eager=True)
    result = ic._analyze(tmp_path, ["jk_standards"])
    assert len(result) == 1
    (cycle,) = result.cycles
    assert cycle.members == (
        "jk_standards.checks.doc_coverage",
        "jk_standards.checks.doc_coverage_cpp",
    )
    assert cycle.anchor_file.endswith(".py") and cycle.anchor_lineno > 0
