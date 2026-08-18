"""Tests for the tree-sitter-cpp doc-coverage enumerator and its dispatch.

Two branches are exercised:

* **parser-present** (requires the ``jk-standards[cpp]`` extra — tree-sitter +
  tree-sitter-cpp — installed in the dev/CI env; skipped otherwise): the C++
  enumerator returns :class:`DocUnit` records with correct file/kind/name/lineno
  and a Doxygen doc-comment ``has_docstring`` signal, honours C++ access rules
  (class members private-by-default, struct members public-by-default), and the
  drift/mention OR-signals apply to C++ units identically to Python units.
* **parser-absent** (simulated by monkeypatching the grammar import to raise, or
  the parser getter to return ``None``): ``cpp_units_for_file`` returns zero
  units without raising and ``enumerate_units`` skips the C++ files while
  emitting a single graceful-degradation summary line, so a misconfigured or
  grammar-less repo is diagnosable from CI logs rather than crashing.

The negative surface — anonymous declarations, private members, plain (non-Doxygen)
comments, the import-failure fallback, and the skip-and-warn path — is asserted
alongside the happy path.
"""

import builtins
from pathlib import Path

import pytest

from jk_standards.checks import doc_coverage, doc_coverage_cpp
from jk_standards.config import Config, SourceRoot

FIX = Path(__file__).parent / "fixtures" / "doc-coverage-cpp"

# The parser-present tests need the native grammar; skip the whole module's
# present-branch cases cleanly in a zero-dependency env.
cpp_grammar = pytest.importorskip("tree_sitter_cpp")


def cpp_cfg(
    *,
    source: str = "src",
    scopes: list[str] | None = None,
    drift_map: str = ".github/docs-drift-map.yml",
    exts: list[str] | None = None,
) -> Config:
    """A doc-coverage config walking a C++ source root under `source`."""
    return Config(
        doc_coverage_source_roots=[SourceRoot(source, exts or [".hpp", ".cpp"])],
        doc_coverage_doc_scopes=scopes or [],
        drift_map=drift_map,
    )


def stage(tmp_path: Path, *names: str, dest: str = "src") -> Path:
    """Copy checked-in fixtures into `tmp_path/dest`, returning `tmp_path`."""
    d = tmp_path / dest
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        (d / n).write_text((FIX / n).read_text(encoding="utf-8"), encoding="utf-8")
    return tmp_path


def write(tmp_path: Path, rel: str, text: str) -> Path:
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- parser presence --------------------------------------------------------


def test_parser_is_available_in_dev_env():
    # The [cpp] extra is installed, so the parser builds (not the None fallback).
    assert doc_coverage_cpp._get_cpp_parser() is not None


# --- parser-present enumeration over checked-in fixtures ---------------------


def test_documented_fixture_enumerates_public_units_with_doc_signal(tmp_path):
    stage(tmp_path, "documented.hpp")
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    by = {(u.kind, u.name): u for u in units}

    # Class, its public method, and a namespace-scope function are enumerated.
    assert set(by) == {
        ("class", "Widget"),
        ("method", "run"),
        ("function", "add"),
    }
    # The private method carries no public unit.
    assert ("method", "secret") not in by

    # Each Doxygen `///` comment sets the has_docstring signal.
    assert by[("class", "Widget")].has_docstring
    assert by[("method", "run")].has_docstring
    assert by[("function", "add")].has_docstring

    # file / lineno are populated from the real source.
    assert by[("class", "Widget")].file == "src/documented.hpp"
    assert by[("class", "Widget")].lineno == 2  # after the /// comment on line 1
    assert by[("function", "add")].lineno == 14


def test_documented_fixture_is_green(tmp_path):
    stage(tmp_path, "documented.hpp")
    assert doc_coverage.run(tmp_path, cpp_cfg()) == 0


def test_bare_fixture_flags_module(tmp_path, capsys):
    stage(tmp_path, "bare.hpp")
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    # Enumerated, but no doc comment -> has_docstring is False for every unit.
    assert units and not any(u.has_docstring for u in units)
    assert doc_coverage.run(tmp_path, cpp_cfg()) == 1
    err = capsys.readouterr().err
    assert "::error file=src/bare.hpp,line=1::" in err


def test_waived_fixture_is_waived_via_line_comment(tmp_path, capsys):
    # A leading `// doc-coverage-ok:` comment waives a bare C++ header exactly
    # like a Python `# doc-coverage-ok:` marker, even after a `#pragma once`.
    stage(tmp_path, "waived.hpp")
    assert doc_coverage.run(tmp_path, cpp_cfg()) == 0
    out = capsys.readouterr().out
    assert "1 waived via doc-coverage-ok" in out


# --- access rules: class vs struct defaults ---------------------------------


def test_struct_members_are_public_by_default(tmp_path):
    write(tmp_path, "src/s.hpp", "struct Point {\n  void translate();\n};\n")
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    by = {(u.kind, u.name) for u in units}
    assert ("struct", "Point") in by
    assert ("method", "translate") in by  # public with no access label


def test_class_members_are_private_by_default(tmp_path):
    write(tmp_path, "src/c.hpp", "class Box {\n  void hidden();\n};\n")
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    by = {(u.kind, u.name) for u in units}
    assert ("class", "Box") in by
    assert ("method", "hidden") not in by  # private with no public: label


def test_anonymous_struct_yields_no_units(tmp_path):
    # An anonymous struct names nothing a doc could reference, so it (and its
    # members) contribute no units rather than an unnamed record.
    write(tmp_path, "src/anon.hpp", "struct {\n  void f();\n} inst;\n")
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    assert units == []


def test_namespace_scoped_function_enumerated_at_bare_name(tmp_path):
    write(
        tmp_path,
        "src/ns.hpp",
        "namespace geo {\n/// Area of a shape.\ndouble area();\n}\n",
    )
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    by = {(u.kind, u.name): u for u in units}
    assert ("function", "area") in by
    assert by[("function", "area")].has_docstring


def test_plain_comment_is_not_a_doc_comment(tmp_path):
    # A `//` line comment (not `///`/`//!`) does not set has_docstring.
    write(tmp_path, "src/p.hpp", "// just a note\nint helper();\n")
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    by = {(u.kind, u.name): u for u in units}
    assert ("function", "helper") in by
    assert not by[("function", "helper")].has_docstring


# --- OR-signals apply to C++ identically to Python --------------------------


def test_drift_map_glob_documents_cpp_module(tmp_path):
    stage(tmp_path, "bare.hpp")
    write(
        tmp_path,
        ".github/docs-drift-map.yml",
        "version: 1\n"
        "mappings:\n"
        "  - sources:\n"
        '      - "src/**"\n'
        '    doc: "docs/spec.md"\n'
        '    reason: "spec describes src"\n',
    )
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    assert units and all(u.drift_match for u in units)
    assert doc_coverage.run(tmp_path, cpp_cfg()) == 0


def test_symbol_mention_in_doc_scope_documents_cpp_module(tmp_path):
    stage(tmp_path, "bare.hpp")
    # `compute` and `Gadget` are named in a doc scope -> mention keeps the
    # module green even without a doc comment or drift match.
    write(tmp_path, "docs/guide.md", "The compute() helper drives the Gadget.\n")
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg(scopes=["docs"]))
    by = {(u.kind, u.name): u for u in units}
    assert by[("function", "compute")].mention
    assert by[("class", "Gadget")].mention  # bare.hpp declares `class Gadget`
    assert doc_coverage.run(tmp_path, cpp_cfg(scopes=["docs"])) == 0


def test_mention_is_whole_word_not_substring(tmp_path):
    write(tmp_path, "src/m.hpp", "int compute();\n")
    write(tmp_path, "docs/guide.md", "See precompute_totals elsewhere.\n")
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg(scopes=["docs"]))
    by = {(u.kind, u.name): u for u in units}
    assert not by[("function", "compute")].mention


# --- mixed Python + C++ under one root: Python path untouched ---------------


def test_python_and_cpp_coexist_under_one_root(tmp_path):
    write(tmp_path, "src/py_mod.py", '"""Documented python module."""\n')
    stage(tmp_path, "documented.hpp")
    cfg = cpp_cfg(exts=[".py", ".hpp"])
    files = {u.file for u in doc_coverage.enumerate_units(tmp_path, cfg)}
    assert files == {"src/py_mod.py", "src/documented.hpp"}
    # Both languages green: python via docstring, C++ via doc comments.
    assert doc_coverage.run(tmp_path, cfg) == 0


# --- parser-absent branch: graceful degradation -----------------------------


def test_cpp_units_for_file_returns_empty_when_parser_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(doc_coverage_cpp, "_get_cpp_parser", lambda: None)
    src = b"/// doc\nint add(int a);\nclass W { public: void m(); };\n"
    assert doc_coverage_cpp.cpp_units_for_file("src/x.hpp", src, False, set()) == []


def test_enumerate_units_skips_cpp_and_warns_when_parser_absent(tmp_path, capsys):
    stage(tmp_path, "documented.hpp", "bare.hpp")
    import pytest as _pytest

    mp = _pytest.MonkeyPatch()
    mp.setattr(doc_coverage_cpp, "_get_cpp_parser", lambda: None)
    try:
        units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    finally:
        mp.undo()
    # No C++ units contributed, and the degradation is announced (not silent).
    assert units == []
    out = capsys.readouterr().out
    assert "tree-sitter-cpp not installed" in out
    assert "install jk-standards[cpp]" in out
    assert "skipping 2 C++ file(s)" in out


def test_import_failure_degrades_parser_to_none(monkeypatch):
    # Simulate the [cpp] extra being absent: the grammar import raises, so the
    # parser getter caches None (the graceful-degradation sentinel) rather than
    # propagating the ImportError.
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("tree_sitter"):
            raise ImportError("simulated missing grammar")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(doc_coverage_cpp, "_PARSER", False)  # reset the cache
    assert doc_coverage_cpp._get_cpp_parser() is None


# --- exotic declarator forms: the shapes _name_of exists to normalise --------
#
# The enumerator's raison d'être is turning a nested/qualified/operator/
# pointer declarator back into the bare name a doc scope would mention. Issue
# #49: the golden-count cpp-dogfood job asserts a single total against a real
# corpus, so a regression that mangles ONE of these forms while preserving the
# count passes unseen. Each row below pins a specific declaration form to the
# unit(s) it must produce, so a mis-parse is caught at the name, not the total.
#
# `expected` is the sorted (kind, name) set enumerate_units must yield.


@pytest.mark.parametrize(
    ("label", "source", "expected"),
    [
        # _name_of: destructor_name — the trailing name of a `~Foo` definition.
        ("destructor", "Foo::~Foo() {}\n", [("function", "~Foo")]),
        # _name_of: operator_name — an out-of-line `operator==` definition.
        (
            "operator",
            "bool operator==(const Foo& a, const Foo& b) { return true; }\n",
            [("function", "operator==")],
        ),
        # _name_of: qualified_identifier — `ns::Foo::bar` yields the leaf `bar`.
        ("qualified", "void ns::Foo::bar() {}\n", [("function", "bar")]),
        # _name_of: pointer/parenthesised unwrap + named_children fallback — a
        # function returning a pointer-to-function (`void (*signal(int))(int)`)
        # nests the real name two declarators deep.
        (
            "func_returning_func_ptr",
            "void (*signal(int sig))(int);\n",
            [("function", "signal")],
        ),
        # _class_units: a bodyless forward declaration names the class but emits
        # no members (there is no body to walk).
        ("forward_class", "class Fwd;\n", [("class", "Fwd")]),
        # _walk_container: a container-level function_definition (not wrapped in
        # a `declaration`) still yields its name.
        ("top_level_definition", "void top() {}\n", [("function", "top")]),
        # _walk_container: a `declaration` that is neither class nor function
        # (`extern int counter;`) contributes nothing — the 271->291 fall-through.
        ("non_callable_declaration", "extern int counter;\n", []),
        # _function_name: a declaration with no function_declarator at all
        # (a type alias) returns None, so no unit is emitted.
        ("type_alias", "using Alias = int;\n", []),
    ],
)
def test_declarator_form_enumerates_expected_units(tmp_path, label, source, expected):
    write(tmp_path, "src/decl.hpp", source)
    units = doc_coverage.enumerate_units(tmp_path, cpp_cfg())
    assert sorted((u.kind, u.name) for u in units) == expected


# --- defensive guards reachable only via a constructed node ------------------
#
# Three branches guard structures tree-sitter never emits from valid top-level
# source (the outer declarator always matches first, or the node is degenerate).
# They are real correctness guards, so we exercise them against a directly
# constructed node rather than leaving the claim untested.


def _parse_root(src: bytes):
    parser = doc_coverage_cpp._get_cpp_parser()
    assert parser is not None
    return parser.parse(src).root_node


def _first_node_of_type(root, node_type: str):
    stack = [root]
    while stack:
        node = stack.pop()
        if node.type == node_type:
            return node
        stack.extend(node.named_children)
    return None


def test_find_function_declarator_skips_parameter_list():
    # The docstring claims _find_function_declarator "skips the parameter list
    # so a function-typed parameter never masquerades as the declaration's own
    # name" (the `void install(int (*cb)(void))` hazard). A trailing-return
    # function returning a function pointer is the one real form that nests an
    # `abstract_function_declarator` — a param-list-bearing declarator with no
    # nested function_declarator of its own. Fed directly, the guard must skip
    # the parameter_list and return None rather than mistaking a parameter for
    # the name.
    root = _parse_root(b"auto f(int x) -> int (*)(int);")
    abstract = _first_node_of_type(root, "abstract_function_declarator")
    assert abstract is not None
    assert doc_coverage_cpp._find_function_declarator(abstract) is None


def test_walk_container_skips_bodyless_namespace(monkeypatch):
    # _walk_container recurses into namespace/linkage bodies; a body-less node
    # (child_by_field_name("body") is None) must be skipped, not crash. Valid
    # C++ always gives a namespace a body, so drive the branch with a namespace
    # whose body lookup is forced to None.
    root = _parse_root(b"namespace geo { int area(); }\n")
    ns = _first_node_of_type(root, "namespace_definition")
    assert ns is not None

    class _BodylessProxy:
        # A namespace node that reports no body — every other attribute delegates
        # to the real node so _walk_container sees a genuine namespace_definition.
        type = "namespace_definition"
        named_children = ()

        def child_by_field_name(self, _field):
            return None

    class _RootProxy:
        named_children = (_BodylessProxy(),)

    units = doc_coverage_cpp._walk_container(_RootProxy(), "src/x.hpp", b"", False, set())
    assert units == []


def test_name_of_returns_none_when_no_child_resolves():
    # _name_of's final fall-through: a node that is not an identifier/special
    # form, has no "declarator" field, and whose named children yield no name
    # (a struct's field_declaration_list) returns None rather than a bogus name.
    root = _parse_root(b"struct X {};\n")
    field_list = _first_node_of_type(root, "field_declaration_list")
    assert field_list is not None
    assert doc_coverage_cpp._name_of(field_list) is None


def test_walk_container_skips_unnamed_top_level_definition():
    # A container-level function_definition whose declarator resolves to no name
    # (_function_name is None) is skipped — the 282->291 fall-through — rather
    # than emitting an unnamed unit.
    root = _parse_root(b"struct X {};\nvoid X::() {}\n")
    bad_def = _first_node_of_type(root, "function_definition")
    assert bad_def is not None
    assert doc_coverage_cpp._function_name(bad_def) is None
    units = doc_coverage_cpp._walk_container(root, "src/x.hpp", b"", False, set())
    # Only the struct is enumerated; the nameless definition contributes nothing.
    assert [(u.kind, u.name) for u in units] == [("struct", "X")]


def test_cpp_units_for_file_returns_empty_when_root_is_none(monkeypatch):
    # cpp_units_for_file guards against a parse whose root_node is None — a
    # defensive path that a healthy grammar never hits. Force it by handing back
    # a tree whose root_node is None.
    class _NoRootTree:
        root_node = None

    class _NoRootParser:
        def parse(self, _source):
            return _NoRootTree()

    monkeypatch.setattr(doc_coverage_cpp, "_get_cpp_parser", lambda: _NoRootParser())
    assert doc_coverage_cpp.cpp_units_for_file("src/x.hpp", b"int f();\n", False, set()) == []
