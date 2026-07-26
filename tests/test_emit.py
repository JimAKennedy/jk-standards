"""Emitter tests: byte-idempotency + registry completeness."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path

from jk_standards import emit
from jk_standards.checks import CHECKS
from jk_standards.config import Config

REPO_ROOT = Path(__file__).resolve().parent.parent
GENERATED_DIR = REPO_ROOT / "site" / "src" / "generated"


def test_each_emitter_is_byte_idempotent():
    for name, (fn, _filename) in emit.EMITTERS.items():
        first = fn(REPO_ROOT)
        second = fn(REPO_ROOT)
        assert first == second, f"emitter '{name}' is not byte-idempotent"


def test_checks_json_covers_every_registered_check():
    data = json.loads((GENERATED_DIR / "checks.json").read_text(encoding="utf-8"))
    emitted = {entry["name"] for entry in data["checks"]}
    assert emitted == set(CHECKS)


def test_config_schema_json_covers_every_dataclass_field():
    data = json.loads((GENERATED_DIR / "config-schema.json").read_text(encoding="utf-8"))
    emitted = {entry["name"] for entry in data["fields"]}
    assert emitted == {f.name for f in fields(Config)}


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
