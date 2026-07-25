"""Fixture-repo tests for the static checks."""

from pathlib import Path

from jk_standards.checks import (
    behavioral_claims,
    count_drift,
    doc_taxonomy,
    file_line_refs,
    generated_freshness,
    status_prose,
)
from jk_standards.config import Config, GeneratedDoc, SourceRoot, ClaimSource


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- doc-taxonomy -----------------------------------------------------------


def test_missing_class_flagged(tmp_path):
    write(tmp_path, "docs/a.md", "# No front matter\n")
    assert doc_taxonomy.run(tmp_path, Config()) == 1


def test_invalid_class_flagged(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: bogus\n---\n# Doc\n")
    assert doc_taxonomy.run(tmp_path, Config()) == 1


def test_valid_class_passes(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\n# Doc\n")
    write(tmp_path, "docs/b.md", "---\nclass: archived\n---\n# Old\n")
    assert doc_taxonomy.run(tmp_path, Config()) == 0


# --- status-prose -----------------------------------------------------------


def test_undated_status_flagged(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nStatus: proposed\n")
    assert status_prose.run(tmp_path, Config()) == 1


def test_dated_status_passes(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nStatus: adopted (2026-07-25)\n")
    assert status_prose.run(tmp_path, Config()) == 0


def test_forbidden_phrase_flagged(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nThis is not yet implemented.\n")
    assert status_prose.run(tmp_path, Config()) == 1


def test_archived_docs_exempt_from_status_prose(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: archived\n---\nStatus: proposed\n")
    assert status_prose.run(tmp_path, Config()) == 0


# --- file-line-refs ---------------------------------------------------------


def test_file_line_ref_in_doc_flagged(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nSee engine.cpp:42 for details.\n")
    assert file_line_refs.run(tmp_path, Config()) == 1


def test_file_line_ok_marker_exempts(tmp_path):
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\n---\nPinned permalink engine.cpp:42 [file-line-ok]\n",
    )
    assert file_line_refs.run(tmp_path, Config()) == 0


def test_source_comment_scanned_code_ignored(tmp_path):
    write(
        tmp_path,
        "src/x.cpp",
        'auto s = "engine.cpp:42";\n// rotted ref engine.cpp:42\n',
    )
    cfg = Config(file_line_source_roots=[SourceRoot("src", [".cpp"])])
    assert file_line_refs.run(tmp_path, cfg) == 1


# --- count-drift ------------------------------------------------------------

TRIGGERS = [r"factory\s+presets?", r"chapters?\s+in\s+total"]


def test_hardcoded_count_flagged(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nShips 14 factory presets.\n")
    assert count_drift.run(tmp_path, Config(count_triggers=TRIGGERS)) == 1


def test_counts_ok_marker_exempts(tmp_path):
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\n---\n<!-- counts-ok: worked example -->\nShips 14 factory presets.\n",
    )
    assert count_drift.run(tmp_path, Config(count_triggers=TRIGGERS)) == 0


def test_code_fence_exempt(tmp_path):
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\n---\n```\n14 factory presets\n```\n",
    )
    assert count_drift.run(tmp_path, Config(count_triggers=TRIGGERS)) == 0


def test_counts_template_passes(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\n{counts.presets} factory presets.\n")
    assert count_drift.run(tmp_path, Config(count_triggers=TRIGGERS)) == 0


# --- behavioral-claims ------------------------------------------------------


def claims_config() -> Config:
    return Config(claim_sources=[ClaimSource("pytest", "checks_tests")])


def test_unresolved_citation_flagged(tmp_path):
    write(tmp_path, "checks_tests/test_a.py", "def test_real():\n    pass\n")
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nClamps [verified: test_a::test_ghost]\n")
    assert behavioral_claims.run(tmp_path, claims_config()) == 1


def test_resolved_citation_passes(tmp_path):
    write(tmp_path, "checks_tests/test_a.py", "def test_real():\n    pass\n")
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nClamps [verified: test_a::test_real]\n")
    assert behavioral_claims.run(tmp_path, claims_config()) == 0


def test_gtest_index_resolves(tmp_path):
    write(tmp_path, "cpp_tests/t.cpp", "TEST(HostTests, Determinism) {}\n")
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\n---\nDeterministic [verified: HostTests.Determinism]\n",
    )
    cfg = Config(claim_sources=[ClaimSource("gtest", "cpp_tests")])
    assert behavioral_claims.run(tmp_path, cfg) == 0


def test_unverified_marker_is_warning_not_error(tmp_path):
    write(tmp_path, "checks_tests/test_a.py", "def test_real():\n    pass\n")
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nSwings hard [⚠ unverified]\n")
    assert behavioral_claims.run(tmp_path, claims_config()) == 0


# --- generated-freshness ----------------------------------------------------


def test_stale_generated_doc_flagged_and_restored(tmp_path):
    doc = write(tmp_path, "docs/gen.md", "---\nclass: generated\n---\nstale\n")
    cfg = Config(
        generated=[
            GeneratedDoc(
                "docs/gen.md", "printf -- '---\\nclass: generated\\n---\\nfresh\\n' > docs/gen.md"
            )
        ]
    )
    assert generated_freshness.run(tmp_path, cfg) == 1
    assert "stale" in doc.read_text()  # tracked content restored


def test_fresh_generated_doc_passes(tmp_path):
    write(tmp_path, "docs/gen.md", "fresh\n")
    cfg = Config(generated=[GeneratedDoc("docs/gen.md", "printf 'fresh\\n' > docs/gen.md")])
    assert generated_freshness.run(tmp_path, cfg) == 0
