"""Emitter tests: byte-idempotency, registry completeness, fixture parity."""

from __future__ import annotations

import json
import subprocess
from dataclasses import fields
from pathlib import Path

import pytest
import yaml

from jk_standards import emit
from jk_standards.checks import CHECKS
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


@pytest.mark.parametrize("name", ["checks", "config-schema", "skills"])
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
