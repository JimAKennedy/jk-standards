"""Whole-module tests for the doc-coverage check.

Covers the ast enumerator (`enumerate_units` / `_units_for_file`), each of the
three OR-signals (docstring, drift-map glob, whole-word mention), the
module-granular gate (`run`), and the top-of-file `# doc-coverage-ok:` escape
hatch — plus the negative surface: unparseable files, binary bytes in a doc
scope, a missing drift map, a non-directory source root, and private units.
"""

import json
from pathlib import Path

import pytest

from jk_standards.checks import doc_coverage
from jk_standards.checks.doc_coverage import DocUnit
from jk_standards.config import Config, ConfigError, SourceRoot


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


# --- per-module baseline ratchet: aggregation -------------------------------


def write_baseline(root: Path, modules: dict[str, tuple[int, int]]) -> Path:
    """Write a floor map in the loader's schema (fraction, not float ratio)."""
    payload = {"modules": {m: {"documented": d, "total": t} for m, (d, t) in modules.items()}}
    return write(root, doc_coverage.BASELINE_PATH, json.dumps(payload, indent=2) + "\n")


def test_per_module_counts_aggregates_documented_and_total(tmp_path):
    # One documented function, one bare function → module unit(no doc) + 2 fns.
    write(
        tmp_path,
        "src/mixed.py",
        "def a():\n"
        '    """doc."""\n\n\n'
        "def b():\n"
        "    pass\n",
    )
    units = doc_coverage.enumerate_units(tmp_path, cfg())
    counts = doc_coverage.per_module_counts(units)
    # module unit (no docstring), a (documented), b (bare) → 1 of 3 documented.
    assert counts == {"src/mixed.py": (1, 3)}


# --- baseline loader (_load_baseline) ---------------------------------------


def test_load_baseline_missing_file_is_first_run_none(tmp_path):
    assert doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH) is None


def test_load_baseline_valid_returns_fraction_map(tmp_path):
    write_baseline(tmp_path, {"src/x.py": (3, 6)})
    floors = doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)
    assert floors == {"src/x.py": (3, 6)}


def test_load_baseline_malformed_json_raises_config_error(tmp_path):
    write(tmp_path, doc_coverage.BASELINE_PATH, "{not: valid json,,,}")
    with pytest.raises(ConfigError):
        doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)


def test_load_baseline_wrong_shape_raises_config_error(tmp_path):
    # A JSON list, or a dict without a "modules" object, is a config error.
    write(tmp_path, doc_coverage.BASELINE_PATH, "[1, 2, 3]")
    with pytest.raises(ConfigError):
        doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)


def test_load_baseline_bad_module_entry_raises_config_error(tmp_path):
    write(
        tmp_path,
        doc_coverage.BASELINE_PATH,
        json.dumps({"modules": {"src/x.py": {"documented": "three", "total": 6}}}),
    )
    with pytest.raises(ConfigError):
        doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)


# --- ratchet compare/fail wired into run() ----------------------------------


def test_ratchet_no_baseline_passes_and_reports_first_run(tmp_path, capsys):
    write(tmp_path, "src/m.py", '"""Documented."""\n')
    assert doc_coverage.run(tmp_path, cfg()) == 0
    assert "no committed baseline" in capsys.readouterr().out


def test_ratchet_holding_at_floor_passes(tmp_path, capsys):
    # Module documents module-unit + fn (2/2 today); floor recorded at 1/2.
    write(tmp_path, "src/m.py", '"""Doc."""\n\n\ndef f():\n    """d."""\n')
    write_baseline(tmp_path, {"src/m.py": (1, 2)})
    assert doc_coverage.run(tmp_path, cfg()) == 0
    assert "1 module(s) evaluated against baseline, 0 ratchet failure(s)" in capsys.readouterr().out


def test_ratchet_regression_below_floor_fails_naming_module_and_ratio(tmp_path, capsys):
    # Live is 1/2 (only module docstring), floor demands 2/2 → regression.
    write(tmp_path, "src/m.py", '"""Doc."""\n\n\ndef f():\n    pass\n')
    write_baseline(tmp_path, {"src/m.py": (2, 2)})
    assert doc_coverage.run(tmp_path, cfg()) == 1
    err = capsys.readouterr().err
    assert "::error file=src/m.py,line=1::" in err
    assert "regressed below its baseline floor" in err
    assert "was 2/2" in err
    assert "now 1/2" in err


def test_ratchet_improvement_above_floor_passes(tmp_path):
    # Live 2/2 exceeds a 1/2 floor — ratchet never punishes an improvement.
    write(tmp_path, "src/m.py", '"""Doc."""\n\n\ndef f():\n    """d."""\n')
    write_baseline(tmp_path, {"src/m.py": (1, 2)})
    assert doc_coverage.run(tmp_path, cfg()) == 0


def test_ratchet_new_module_not_in_baseline_passes(tmp_path, capsys):
    # `src/new.py` is in the tree but absent from the floor map → first-seen,
    # not evaluated, passes. Only the baselined module is evaluated.
    write(tmp_path, "src/known.py", '"""Doc."""\n')
    write(tmp_path, "src/new.py", '"""Also doc."""\n')
    write_baseline(tmp_path, {"src/known.py": (1, 1)})
    assert doc_coverage.run(tmp_path, cfg()) == 0
    assert "1 module(s) evaluated against baseline" in capsys.readouterr().out


def test_ratchet_deleted_module_in_baseline_not_evaluated(tmp_path):
    # `src/gone.py` is in the floor map but not on disk → not evaluated, no
    # error (a deleted module cannot regress).
    write(tmp_path, "src/present.py", '"""Doc."""\n')
    write_baseline(tmp_path, {"src/present.py": (1, 1), "src/gone.py": (5, 5)})
    assert doc_coverage.run(tmp_path, cfg()) == 0


def test_ratchet_composes_with_binary_gate(tmp_path, capsys):
    # One fully-bare module (binary gate) AND one regressed module (ratchet):
    # both fire, and the return value sums both classes of failure.
    write(tmp_path, "src/bare.py", "x = 1\n")
    write(tmp_path, "src/reg.py", '"""Doc."""\n\n\ndef f():\n    pass\n')
    write_baseline(tmp_path, {"src/reg.py": (2, 2)})
    assert doc_coverage.run(tmp_path, cfg()) == 2
    err = capsys.readouterr().err
    assert "file=src/bare.py" in err  # binary gate finding
    assert "file=src/reg.py" in err  # ratchet finding
    assert "fully undocumented" in err
    assert "regressed below its baseline floor" in err


def test_ratchet_malformed_baseline_raises_config_error_from_run(tmp_path):
    # A malformed baseline surfaces as ConfigError (CLI maps it to exit 2),
    # not a traceback.
    write(tmp_path, "src/m.py", '"""Doc."""\n')
    write(tmp_path, doc_coverage.BASELINE_PATH, "{bad json")
    with pytest.raises(ConfigError):
        doc_coverage.run(tmp_path, cfg())


# --- update_baseline: the explicit record/ratchet writer (D015) -------------


def test_update_baseline_first_run_records_and_passes(tmp_path, capsys):
    # No committed baseline yet → records the live distribution, exits 0, and
    # the written file round-trips back through the loader unchanged.
    write(tmp_path, "src/m.py", '"""Doc."""\n\n\ndef f():\n    """d."""\n')
    assert doc_coverage.update_baseline(tmp_path, cfg()) == 0
    floors = doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)
    assert floors == {"src/m.py": (2, 2)}
    assert "baseline recorded" in capsys.readouterr().out


def test_update_baseline_is_byte_idempotent(tmp_path):
    # Recording the same tree twice reproduces the file byte-for-byte — the
    # committed baseline (T04) is produced by this writer, so a later
    # --update-baseline or byte-comparison test must not drift.
    write(tmp_path, "src/a.py", '"""A."""\n\n\ndef f():\n    pass\n')
    write(tmp_path, "src/b.py", '"""B."""\n')
    path = tmp_path / doc_coverage.BASELINE_PATH
    doc_coverage.update_baseline(tmp_path, cfg())
    first = path.read_bytes()
    doc_coverage.update_baseline(tmp_path, cfg())
    assert path.read_bytes() == first
    # Stable shape: sorted module keys, 2-space indent, trailing newline.
    text = first.decode("utf-8")
    assert text.endswith("}\n")
    assert text.index('"src/a.py"') < text.index('"src/b.py"')


def test_update_baseline_raising_a_floor_is_allowed(tmp_path):
    # Live 2/2 exceeds a recorded 1/2 floor → ratchet up freely, no opt-in.
    write(tmp_path, "src/m.py", '"""Doc."""\n\n\ndef f():\n    """d."""\n')
    write_baseline(tmp_path, {"src/m.py": (1, 2)})
    assert doc_coverage.update_baseline(tmp_path, cfg()) == 0
    floors = doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)
    assert floors == {"src/m.py": (2, 2)}


def test_update_baseline_lowering_refused_without_allow_regression(tmp_path, capsys):
    # Live 1/2 is below a recorded 2/2 floor → refuse, leave the file untouched,
    # name the offending module, and return non-zero.
    write(tmp_path, "src/m.py", '"""Doc."""\n\n\ndef f():\n    pass\n')
    write_baseline(tmp_path, {"src/m.py": (2, 2)})
    before = (tmp_path / doc_coverage.BASELINE_PATH).read_bytes()
    assert doc_coverage.update_baseline(tmp_path, cfg()) == 1
    assert (tmp_path / doc_coverage.BASELINE_PATH).read_bytes() == before
    captured = capsys.readouterr()
    assert "::error file=src/m.py,line=1::" in captured.err
    assert "refusing to lower the baseline floor" in captured.err
    assert "baseline NOT written" in captured.out


def test_update_baseline_lowering_allowed_with_allow_regression(tmp_path):
    # The explicit --allow-regression opt-in records the lower floor.
    write(tmp_path, "src/m.py", '"""Doc."""\n\n\ndef f():\n    pass\n')
    write_baseline(tmp_path, {"src/m.py": (2, 2)})
    assert doc_coverage.update_baseline(tmp_path, cfg(), allow_regression=True) == 0
    floors = doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)
    assert floors == {"src/m.py": (1, 2)}


def test_update_baseline_new_module_recorded_freely(tmp_path):
    # A module absent from the floor map is recorded without any opt-in, and an
    # existing (unchanged) floor is preserved.
    write(tmp_path, "src/known.py", '"""Doc."""\n')
    write(tmp_path, "src/new.py", '"""Also doc."""\n')
    write_baseline(tmp_path, {"src/known.py": (1, 1)})
    assert doc_coverage.update_baseline(tmp_path, cfg()) == 0
    floors = doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)
    assert floors == {"src/known.py": (1, 1), "src/new.py": (1, 1)}


def test_update_baseline_deleted_module_dropped(tmp_path):
    # A module in the floor map but no longer on disk cannot regress; the writer
    # records only the live distribution, so it is dropped from the new baseline.
    write(tmp_path, "src/present.py", '"""Doc."""\n')
    write_baseline(tmp_path, {"src/present.py": (1, 1), "src/gone.py": (5, 5)})
    assert doc_coverage.update_baseline(tmp_path, cfg()) == 0
    floors = doc_coverage._load_baseline(tmp_path / doc_coverage.BASELINE_PATH)
    assert floors == {"src/present.py": (1, 1)}


def test_update_baseline_no_source_roots_does_not_write(tmp_path):
    write(tmp_path, "src/bare.py", "x = 1\n")
    assert doc_coverage.update_baseline(tmp_path, Config()) == 0
    assert not (tmp_path / doc_coverage.BASELINE_PATH).exists()


def test_update_baseline_malformed_existing_raises_config_error(tmp_path):
    # Cannot ratchet on top of a garbage baseline — surfaces as ConfigError
    # (CLI exit 2), even with --allow-regression.
    write(tmp_path, "src/m.py", '"""Doc."""\n')
    write(tmp_path, doc_coverage.BASELINE_PATH, "{bad json")
    with pytest.raises(ConfigError):
        doc_coverage.update_baseline(tmp_path, cfg(), allow_regression=True)
