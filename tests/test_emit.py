"""Emitter tests: byte-idempotency, registry completeness, fixture parity."""

from __future__ import annotations

import json
import subprocess
from dataclasses import fields
from pathlib import Path

import pytest
import yaml

from jk_standards import emit
from jk_standards.checks import CHECKS, doc_coverage
from jk_standards.config import Config

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = REPO_ROOT / "site" / "src" / "generated"


def test_each_emitter_is_byte_idempotent():
    # Skip 'coverage' — running it inside pytest would either recurse (no
    # .coverage → subprocess spawns pytest → this test again) or emit
    # different bytes on successive runs as the outer coverage measurement
    # changes. Its determinism is exercised by the fixture-round-trip helper
    # below, which drives _coverage_payload directly.
    for name, (fn, _filename) in emit.EMITTERS.items():
        if name == "coverage":
            continue
        first = fn(REPO_ROOT)
        second = fn(REPO_ROOT)
        assert first == second, f"emitter '{name}' is not byte-idempotent"


# --- committed-fixture parity (schema-drift guards) ---------------------------


@pytest.mark.parametrize("name", ["checks", "config-schema", "skills", "doc-coverage"])
def test_deterministic_emitters_match_committed_fixture(name):
    """Fresh emission must equal the committed fixture, byte for byte.

    Without this test, renaming a JSON key or adding a field silently passes
    every other emitter test — only `generated-freshness` in CI would catch
    it, and only when running the full dogfood suite.
    """
    fn, filename = emit.EMITTERS[name]
    fresh = fn(REPO_ROOT)
    committed = (GENERATED_DIR / filename).read_bytes()
    assert fresh == committed, (
        f"{filename} drifted from source — run `jk-standards emit {name}` and commit"
    )


def test_checks_json_covers_every_registered_check():
    data = json.loads((GENERATED_DIR / "checks.json").read_text(encoding="utf-8"))
    emitted = {entry["name"] for entry in data["checks"]}
    assert emitted == set(CHECKS)


def test_config_schema_json_covers_every_dataclass_field():
    data = json.loads((GENERATED_DIR / "config-schema.json").read_text(encoding="utf-8"))
    emitted = {entry["name"] for entry in data["fields"]}
    assert emitted == {f.name for f in fields(Config)}


def test_config_schema_types_are_source_strings_not_class_repr():
    """`from __future__ import annotations` in config.py keeps f.type as the
    literal source string ('list[DocRoot]'). If that import is ever removed,
    f.type would become a runtime class object and str(f.type) would emit
    "<class 'list'>" — silently rewriting every type in the fixture.
    """
    data = json.loads((GENERATED_DIR / "config-schema.json").read_text(encoding="utf-8"))
    for entry in data["fields"]:
        assert not entry["type"].startswith("<class "), (
            f"field {entry['name']!r} has type={entry['type']!r} — config.py must "
            f"keep `from __future__ import annotations` so f.type stays a source string"
        )


def test_skills_json_covers_every_skill_dir():
    data = json.loads((GENERATED_DIR / "skills.json").read_text(encoding="utf-8"))
    emitted = {entry["name"] for entry in data["skills"]}
    on_disk = {p.parent.name for p in (REPO_ROOT / "skills").glob("*/SKILL.md")}
    assert emitted == on_disk


def test_coverage_json_totals_shape():
    data = json.loads((GENERATED_DIR / "coverage.json").read_text(encoding="utf-8"))
    totals = data["totals"]
    assert isinstance(totals["percent_covered"], (int, float))
    assert totals["percent_covered"] >= 80.0
    assert totals["num_statements"] > 0


# --- generated: <-> EMITTERS pairing -----------------------------------------


def test_generated_yaml_pairs_every_deterministic_emitter():
    """Every deterministic emitter must appear in jk-standards.yaml's
    `generated:` section so `generated-freshness` gates it. `coverage` is
    intentionally excluded (see comment in jk-standards.yaml).
    """
    yaml_data = yaml.safe_load((REPO_ROOT / "jk-standards.yaml").read_text(encoding="utf-8"))
    gated_paths = {entry["doc"] for entry in yaml_data.get("generated", [])}
    expected = {
        f"site/src/generated/{filename}"
        for name, (_, filename) in emit.EMITTERS.items()
        if name not in emit.NON_DETERMINISTIC
    }
    assert gated_paths == expected


# --- coverage payload determinism (unit-tested, no subprocess) ----------------


_FAKE_COVERAGE_RAW = {
    "totals": {
        "percent_covered": 88.7654,
        "num_statements": 500,
        "missing_lines": 55,
        "covered_lines": 445,
    },
    "files": {
        "b.py": {"summary": {"percent_covered": 75.0, "missing_lines": 5}},
        "a.py": {"summary": {"percent_covered": 100.0, "missing_lines": 0}},
    },
}


def test_coverage_payload_is_deterministic_and_stable():
    first = emit._serialize(emit._coverage_payload(_FAKE_COVERAGE_RAW))
    second = emit._serialize(emit._coverage_payload(_FAKE_COVERAGE_RAW))
    assert first == second
    parsed = json.loads(first)
    assert parsed["totals"]["percent_covered"] == 88.77
    # files must be sorted so JSON output is stable regardless of dict order.
    assert list(parsed["files"].keys()) == ["a.py", "b.py"]


def test_coverage_payload_survives_empty_totals():
    """Empty totals dict shouldn't crash — every derived field must default."""
    payload = emit._coverage_payload({})
    assert payload["totals"]["percent_covered"] == 0.0
    assert payload["totals"]["num_statements"] == 0
    assert payload["files"] == {}


# --- skill frontmatter: robustness bugs the review surfaced -------------------


def test_skill_frontmatter_rejects_non_mapping(tmp_path):
    """A YAML list at the top level must not crash emit_skills."""
    skill_dir = tmp_path / "skills" / "bogus"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("---\n- one\n- two\n---\n# body\n", encoding="utf-8")
    # Would crash before the fix with `AttributeError: 'list' object has no attribute 'get'`.
    result = emit.emit_skills(tmp_path)
    parsed = json.loads(result)
    assert parsed["skills"][0]["name"] == "bogus"  # falls back to dir name


def test_skill_frontmatter_ignores_midline_triple_dash(tmp_path):
    """A `---` inside a block scalar must NOT be treated as the closing fence."""
    skill_dir = tmp_path / "skills" / "example"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: example\n"
        "description: |\n"
        "  Multi-line description\n"
        "  with a --- inside it\n"
        "  spanning several lines.\n"
        "---\n"
        "# body\n",
        encoding="utf-8",
    )
    result = emit.emit_skills(tmp_path)
    parsed = json.loads(result)
    entry = parsed["skills"][0]
    assert entry["name"] == "example"
    assert "spanning several lines" in entry["description"]


# --- _default_repr: cycle guard and non-data-object handling -----------------


def test_default_repr_survives_cycle():
    a: list = []
    a.append(a)
    # Would previously RecursionError. The recursive reference is caught the
    # first time we walk into it, so the outer list contains one "<cycle>".
    result = emit._default_repr(a)
    assert result == ["<cycle>"]


def test_default_repr_does_not_walk_functions_or_types():
    """Functions and classes have __dict__ but aren't plain data objects."""
    assert emit._default_repr(len) == repr(len)
    assert emit._default_repr(int) == repr(int)


# --- run() edge cases ---------------------------------------------------------


def test_run_all_returns_zero_on_empty_emitters(monkeypatch, tmp_path):
    """`run(root, 'all', ...)` must not crash when EMITTERS is empty."""
    monkeypatch.setattr(emit, "EMITTERS", {})
    # Would previously raise `ValueError: max() arg is an empty sequence`.
    assert emit.run(tmp_path, "all", check_only=True) == 0


def test_check_mode_for_coverage_does_not_shell_out(monkeypatch, tmp_path):
    """`emit --check coverage` must be read-only — no subprocess, no recursion.

    Guards against the review finding that check-mode invoked the full
    coverage subprocess pipeline before comparing bytes.
    """
    fixture_path = tmp_path / "site" / "src" / "generated" / "coverage.json"
    fixture_path.parent.mkdir(parents=True)
    fixture_path.write_text('{"stub": true}\n', encoding="utf-8")

    def _no_subprocess(*_args, **_kwargs):
        raise AssertionError("emit --check coverage must not shell out to subprocess.run")

    monkeypatch.setattr(subprocess, "run", _no_subprocess)
    assert emit.run(tmp_path, "coverage", check_only=True) == 0


def test_check_mode_for_coverage_fails_when_fixture_missing(tmp_path):
    """Missing fixture is still a hard error — the gate isn't a no-op."""
    assert emit.run(tmp_path, "coverage", check_only=True) == 1


# --- emit_doc_coverage: symbol-level worklist contract ------------------------
#
# doc-coverage is a DETERMINISTIC emitter (unlike coverage): it must NOT be in
# NON_DETERMINISTIC, its fresh output must equal the committed fixture, and its
# `--check` path recomputes-and-diffs rather than short-circuiting on presence.
# These tests lock the JSON shape (S03 + downstream remediation consume it),
# the sort, the per-signal fields, and the two-run determinism guarantee.


def _fresh_doc_coverage() -> dict:
    """Parse the emitter's live output (not the committed file) so these tests
    assert the contract the emitter produces, not just fixture bytes on disk."""
    return json.loads(emit.emit_doc_coverage(REPO_ROOT).decode("utf-8"))


def test_doc_coverage_is_not_marked_non_deterministic():
    """MEM043: doc-coverage is deterministic and must be diff-gated. If it ever
    leaks into NON_DETERMINISTIC, `emit --check` would degrade to a presence
    check and stop catching stale worklists."""
    assert "doc-coverage" not in emit.NON_DETERMINISTIC


def test_non_deterministic_emitters_run_last():
    """`emit all` walks EMITTERS in dict order, and emit_coverage shells out to
    the full pytest suite -- which itself asserts the *other* generated fixtures
    are fresh. Right after a version bump every `toolkit_version`-carrying
    fixture is stale, so a coverage run scheduled before the deterministic
    emitters dies inside the subprocess and surfaces as a CalledProcessError
    naming pytest, never the actual staleness. Keep coverage (and any future
    non-deterministic emitter) in the final slots."""
    order = list(emit.EMITTERS)
    assert set(order) >= emit.NON_DETERMINISTIC, order
    tail = order[len(order) - len(emit.NON_DETERMINISTIC) :]
    assert set(tail) == set(emit.NON_DETERMINISTIC), order


def test_doc_coverage_top_level_shape():
    data = _fresh_doc_coverage()
    assert set(data) == {"toolkit_version", "units"}
    assert isinstance(data["toolkit_version"], str) and data["toolkit_version"]
    assert isinstance(data["units"], list) and data["units"]


def test_doc_coverage_every_unit_has_the_full_field_set():
    """Every row is a concrete file+symbol remediation target: it must carry the
    locus (file/kind/name/lineno), the rolled-up `documented` verdict, and all
    three per-signal booleans nested under `signals`."""
    for row in _fresh_doc_coverage()["units"]:
        assert set(row) == {"file", "kind", "name", "lineno", "documented", "signals"}
        assert isinstance(row["file"], str)
        assert row["kind"] in {"module", "class", "function", "method"}
        assert isinstance(row["name"], str)
        assert isinstance(row["lineno"], int)
        assert isinstance(row["documented"], bool)
        assert set(row["signals"]) == {"docstring", "drift", "mention"}
        assert all(isinstance(v, bool) for v in row["signals"].values())


def test_doc_coverage_documented_is_the_or_of_the_three_signals():
    """`documented` is exactly the disjunction the S01 gate consumes — never a
    stored field that could drift from the per-signal booleans."""
    for row in _fresh_doc_coverage()["units"]:
        s = row["signals"]
        assert row["documented"] == (s["docstring"] or s["drift"] or s["mention"])


def test_doc_coverage_units_are_sorted_by_file_name_lineno():
    """Byte-stable output depends on the (file, name, lineno) sort — an unsorted
    walk would make the fixture reorder nondeterministically across runs."""
    units = _fresh_doc_coverage()["units"]
    keys = [(r["file"], r["name"], r["lineno"]) for r in units]
    assert keys == sorted(keys)


def test_doc_coverage_is_byte_idempotent_across_two_runs():
    """The determinism guarantee, asserted at the byte level on real source."""
    assert emit.emit_doc_coverage(REPO_ROOT) == emit.emit_doc_coverage(REPO_ROOT)


def test_doc_coverage_carries_the_undocumented_backlog():
    """The worklist's whole point: fully-undocumented symbols (all three signals
    false → documented false) surface as targets. The backlog is emitter-derived
    — we assert its shape and known members, never a hardcoded count."""
    units = _fresh_doc_coverage()["units"]
    undocumented = [r for r in units if not r["documented"]]
    assert undocumented, "expected a non-empty undocumented backlog"
    # A `documented: false` row must have every signal off — the invariant that
    # makes it an honest remediation target.
    for row in undocumented:
        assert not any(row["signals"].values())
    # The known bare files from the slice contract (gitutil.py + skills_install.py).
    undocumented_files = {r["file"] for r in undocumented}
    assert any(f.endswith("gitutil.py") for f in undocumented_files)
    assert any(f.endswith("skills_install.py") for f in undocumented_files)


def test_doc_coverage_check_path_is_fresh_against_committed_fixture():
    """`emit --check doc-coverage` recomputes and diffs (deterministic branch),
    returning 0 when the committed worklist is fresh. This is the CI signal."""
    assert emit.run(REPO_ROOT, "doc-coverage", check_only=True) == 0


def test_doc_coverage_check_path_detects_a_stale_fixture(tmp_path, monkeypatch):
    """The deterministic `--check` branch must return 1 when bytes drift — proof
    the gate diffs content rather than merely asserting the file exists."""
    out_path = tmp_path / emit.GENERATED_DIR / "doc-coverage.json"
    out_path.parent.mkdir(parents=True)
    out_path.write_text('{"stale": true}\n', encoding="utf-8")
    monkeypatch.setitem(
        emit.EMITTERS, "doc-coverage", (lambda _root: b'{"fresh": true}\n', "doc-coverage.json")
    )
    assert emit.run(tmp_path, "doc-coverage", check_only=True) == 1


# --- self-heal invariant: `emit all` must never touch the ratchet baseline ----
#
# The load-bearing M011 guarantee (D016) is that baselines/doc-coverage.json can
# never be freshened by `emit all` — if it could, a coverage regression would
# silently heal itself into the new floor and the ratchet would gate nothing.
# That exclusion is enforced structurally: the baseline is absent from
# emit.EMITTERS (nothing emits it) AND from jk-standards.yaml's `generated:`
# list (generated-freshness never regenerates it). The three tests below pin
# both halves plus a live write-mode proof, so the exclusion cannot be undone
# without a red test.


def test_baseline_path_is_not_a_registered_emitter_output():
    """No emitter targets the baseline. `emit all` only ever writes
    root/GENERATED_DIR/<filename> for a registered emitter, so a path absent
    from that set is structurally unreachable — the ratchet floor cannot
    self-heal. The baseline also lives OUTSIDE the emitted GENERATED_DIR."""
    baseline = (REPO_ROOT / doc_coverage.BASELINE_PATH).resolve()
    emitter_outputs = {
        (REPO_ROOT / emit.GENERATED_DIR / filename).resolve()
        for _, (_, filename) in emit.EMITTERS.items()
    }
    assert baseline not in emitter_outputs
    assert (REPO_ROOT / emit.GENERATED_DIR).resolve() not in baseline.parents


def test_baseline_path_is_absent_from_generated_freshness_gate():
    """generated-freshness re-runs each `generated:` command and diffs the
    result against the tracked file; listing the baseline there would let CI
    regenerate (self-heal) it. It must be absent so the explicit --update-baseline
    writer stays the ONLY path that mutates the floor."""
    yaml_data = yaml.safe_load((REPO_ROOT / "jk-standards.yaml").read_text(encoding="utf-8"))
    gated = {entry["doc"] for entry in yaml_data.get("generated", [])}
    assert doc_coverage.BASELINE_PATH not in gated


def test_emit_all_write_mode_leaves_the_baseline_byte_identical(monkeypatch):
    """The invariant proven dynamically: a real write-mode `emit all` pass leaves
    baselines/doc-coverage.json byte-for-byte unchanged. `coverage` is dropped
    (non-deterministic, and would recurse inside pytest). Every fixture the pass
    would write is snapshotted and restored in a finally, so the test is hermetic
    — it never leaves a tracked file modified even if one was stale on entry."""
    deterministic = {k: v for k, v in emit.EMITTERS.items() if k != "coverage"}
    targets = {
        REPO_ROOT / emit.GENERATED_DIR / filename: (
            REPO_ROOT / emit.GENERATED_DIR / filename
        ).read_bytes()
        for _, (_, filename) in deterministic.items()
    }
    baseline_path = REPO_ROOT / doc_coverage.BASELINE_PATH
    baseline_before = baseline_path.read_bytes()
    monkeypatch.setattr(emit, "EMITTERS", deterministic)
    try:
        assert emit.run(REPO_ROOT, "all", check_only=False) == 0
        assert baseline_path.read_bytes() == baseline_before
    finally:
        for path, data in targets.items():
            path.write_bytes(data)
