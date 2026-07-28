"""Whole-module tests for the doc-coverage check.

Covers the ast enumerator (`enumerate_units` / `_units_for_file`), each of the
three OR-signals (docstring, drift-map glob, whole-word mention), the
module-granular gate (`run`), and the top-of-file `# doc-coverage-ok:` escape
hatch — plus the negative surface: unparseable files, binary bytes in a doc
scope, a missing drift map, a non-directory source root, and private units.
"""

from pathlib import Path

from jk_standards.checks import doc_coverage
from jk_standards.checks.doc_coverage import DocUnit
from jk_standards.config import Config, SourceRoot


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def cfg(
    *,
    source: str = "src",
    scopes: list[str] | None = None,
    drift_map: str = ".github/docs-drift-map.yml",
) -> Config:
    """A doc-coverage config walking `source/*.py`, scanning `scopes` for mentions."""
    return Config(
        doc_coverage_source_roots=[SourceRoot(source, [".py"])],
        doc_coverage_doc_scopes=scopes or [],
        drift_map=drift_map,
    )


_DRIFT_MAP = (
    "version: 1\n"
    "mappings:\n"
    "  - sources:\n"
    '      - "src/**"\n'
    '    doc: "docs/spec.md"\n'
    '    reason: "spec describes src"\n'
)


# --- DocUnit.documented (the OR disjunction) --------------------------------


def test_docunit_documented_is_disjunction():
    base = dict(file="src/x.py", kind="module", name="x", lineno=1)
    assert not DocUnit(**base, has_docstring=False, drift_match=False, mention=False).documented
    assert DocUnit(**base, has_docstring=True, drift_match=False, mention=False).documented
    assert DocUnit(**base, has_docstring=False, drift_match=True, mention=False).documented
    assert DocUnit(**base, has_docstring=False, drift_match=False, mention=True).documented


# --- enumerate_units: the ast walk ------------------------------------------


def test_enumerate_units_module_class_function_method(tmp_path):
    write(
        tmp_path,
        "src/mod.py",
        '"""Module doc."""\n\n\n'
        "def public_fn():\n"
        '    """fn doc."""\n\n\n'
        "def _private_fn():\n"
        "    pass\n\n\n"
        "class Widget:\n"
        "    def method(self):\n"
        "        pass\n\n"
        "    def _hidden(self):\n"
        "        pass\n\n\n"
        "class _Internal:\n"
        "    pass\n",
    )
    units = doc_coverage.enumerate_units(tmp_path, cfg())
    by = {(u.kind, u.name): u for u in units}

    # Module + public function + public class + public method are enumerated.
    assert set(by) == {
        ("module", "mod"),
        ("function", "public_fn"),
        ("class", "Widget"),
        ("method", "method"),
    }
    # Private top-level defs, private methods, and private classes are skipped.
    assert ("function", "_private_fn") not in by
    assert ("method", "_hidden") not in by
    assert ("class", "_Internal") not in by

    # Docstring signal is per-unit.
    assert by[("module", "mod")].has_docstring
    assert by[("function", "public_fn")].has_docstring
    assert not by[("class", "Widget")].has_docstring
    assert not by[("method", "method")].has_docstring
    # The module unit anchors at line 1; the class carries its real lineno.
    assert by[("module", "mod")].lineno == 1
    assert by[("class", "Widget")].lineno > 1


def test_enumerate_units_async_function_enumerated(tmp_path):
    write(tmp_path, "src/a.py", "async def handler():\n    pass\n")
    units = doc_coverage.enumerate_units(tmp_path, cfg())
    assert ("function", "handler") in {(u.kind, u.name) for u in units}


def test_enumerate_units_syntax_error_degrades_to_module(tmp_path):
    # An unparseable file degrades to a single bare module unit rather than
    # raising — the enumerator must never traceback on bad source.
    write(tmp_path, "src/broken.py", "def (:\n  not python\n")
    units = doc_coverage.enumerate_units(tmp_path, cfg())
    assert len(units) == 1
    assert units[0].kind == "module"
    assert units[0].name == "broken"
    assert not units[0].has_docstring


# --- source-root walking ----------------------------------------------------


def test_missing_source_root_dir_yields_no_units(tmp_path):
    # A configured root that does not exist on disk is skipped, not an error.
    units = doc_coverage.enumerate_units(tmp_path, cfg(source="nonexistent"))
    assert units == []


def test_non_py_files_are_not_walked(tmp_path):
    write(tmp_path, "src/keep.py", "x = 1\n")
    write(tmp_path, "src/notes.md", "mentions keep\n")
    write(tmp_path, "src/data.txt", "x = 1\n")
    files = {u.file for u in doc_coverage.enumerate_units(tmp_path, cfg())}
    assert files == {"src/keep.py"}


# --- signal 1: docstring ----------------------------------------------------


def test_module_docstring_alone_keeps_module_green(tmp_path):
    # The lenient gate: a module docstring documents the module unit, so even
    # with bare undocumented functions the module does not fail.
    write(tmp_path, "src/m.py", '"""Present."""\n\n\ndef bare():\n    pass\n')
    assert doc_coverage.run(tmp_path, cfg()) == 0


def test_fully_bare_module_fails(tmp_path):
    write(tmp_path, "src/bare.py", "x = 1\n")
    assert doc_coverage.run(tmp_path, cfg()) == 1


# --- signal 2: drift-map sources glob ---------------------------------------


def test_drift_map_glob_documents_module(tmp_path):
    # No docstring, no mention — but the file matches a drift-map `sources:`
    # glob, so a change to it is already touch-correlated to a doc.
    write(tmp_path, "src/engine.py", "x = 1\n")
    write(tmp_path, ".github/docs-drift-map.yml", _DRIFT_MAP)
    units = doc_coverage.enumerate_units(tmp_path, cfg())
    assert all(u.drift_match for u in units)
    assert doc_coverage.run(tmp_path, cfg()) == 0


def test_missing_drift_map_leaves_drift_signal_off(tmp_path):
    # With no drift map on disk the drift signal is simply always off; the
    # bare module then falls through to a finding.
    write(tmp_path, "src/engine.py", "x = 1\n")
    units = doc_coverage.enumerate_units(tmp_path, cfg())
    assert not any(u.drift_match for u in units)
    assert doc_coverage.run(tmp_path, cfg()) == 1


# --- signal 3: whole-word mention in a doc scope ----------------------------


def test_symbol_mention_in_doc_scope_documents_module(tmp_path):
    write(tmp_path, "src/thing.py", "x = 1\n\n\ndef compute_total():\n    pass\n")
    # The module stem `thing` is not mentioned, but the public function name is —
    # one documented unit is enough to keep the module green.
    write(tmp_path, "docs/guide.md", "The compute_total helper sums the batch.\n")
    units = doc_coverage.enumerate_units(tmp_path, cfg(scopes=["docs"]))
    by = {(u.kind, u.name): u for u in units}
    assert by[("function", "compute_total")].mention
    assert not by[("module", "thing")].mention
    assert doc_coverage.run(tmp_path, cfg(scopes=["docs"])) == 0


def test_mention_is_whole_word_not_substring(tmp_path):
    # `compute_total` must not be "mentioned" by a substring like
    # `precompute_totals` — the corpus is whole-word `\w+` tokens.
    write(tmp_path, "src/thing.py", "def compute_total():\n    pass\n")
    write(tmp_path, "docs/guide.md", "See precompute_totals elsewhere.\n")
    units = doc_coverage.enumerate_units(tmp_path, cfg(scopes=["docs"]))
    by = {(u.kind, u.name): u for u in units}
    assert not by[("function", "compute_total")].mention


def test_missing_doc_scope_dir_is_skipped(tmp_path):
    write(tmp_path, "src/bare.py", "x = 1\n")
    # A configured scope that does not exist contributes no tokens and does not
    # raise; the module stays a finding.
    assert doc_coverage.run(tmp_path, cfg(scopes=["docs", "conventions"])) == 1


def test_binary_bytes_in_doc_scope_do_not_raise(tmp_path):
    write(tmp_path, "src/bare.py", "x = 1\n")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\xff\xfe")
    # errors="replace" means undecodable bytes are tolerated, not fatal.
    assert doc_coverage.run(tmp_path, cfg(scopes=["docs"])) == 1


# --- the module-granular gate + escape hatch --------------------------------


def test_no_source_roots_configured_skips(tmp_path):
    write(tmp_path, "src/bare.py", "x = 1\n")
    assert doc_coverage.run(tmp_path, Config()) == 0


def test_bare_module_emits_error_with_path_and_line(tmp_path, capsys):
    write(tmp_path, "src/bare.py", "x = 1\n")
    assert doc_coverage.run(tmp_path, cfg()) == 1
    err = capsys.readouterr().err
    assert "::error file=src/bare.py,line=1::" in err
    assert "fully undocumented" in err
    assert "doc-coverage-ok" in err  # the finding advertises the escape hatch


def test_multiple_bare_modules_each_counted(tmp_path, capsys):
    write(tmp_path, "src/a.py", "x = 1\n")
    write(tmp_path, "src/b.py", "y = 2\n")
    assert doc_coverage.run(tmp_path, cfg()) == 2
    err = capsys.readouterr().err
    assert "file=src/a.py" in err
    assert "file=src/b.py" in err


def test_escape_hatch_waives_module(tmp_path, capsys):
    write(tmp_path, "src/gen.py", "# doc-coverage-ok: generated shim, no public API\nx = 1\n")
    assert doc_coverage.run(tmp_path, cfg()) == 0
    out = capsys.readouterr().out
    assert "1 waived via doc-coverage-ok" in out


def test_escape_hatch_after_shebang_still_waives(tmp_path):
    # The marker anywhere in the leading comment block counts — a shebang above
    # it does not break the top-of-file scan.
    write(
        tmp_path,
        "src/tool.py",
        "#!/usr/bin/env python\n# doc-coverage-ok: cli entrypoint\nx = 1\n",
    )
    assert doc_coverage.run(tmp_path, cfg()) == 0


def test_marker_buried_in_code_does_not_waive(tmp_path):
    # Once the first non-comment line is seen the leading block is over: a marker
    # below it (here after `x = 1`) is not a top-of-file waiver.
    write(tmp_path, "src/x.py", "x = 1\n# doc-coverage-ok: too late\n")
    assert doc_coverage.run(tmp_path, cfg()) == 1


def test_clean_run_summary_reports_unit_and_module_counts(tmp_path, capsys):
    write(tmp_path, "src/m.py", '"""Documented."""\n')
    assert doc_coverage.run(tmp_path, cfg()) == 0
    out = capsys.readouterr().out
    assert "public unit(s)" in out
    assert "0 fully-undocumented module(s)" in out
