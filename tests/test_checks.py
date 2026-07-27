"""Fixture-repo tests for the static checks."""

from pathlib import Path

from jk_standards.checks import (
    action_pinning,
    behavioral_claims,
    count_drift,
    doc_taxonomy,
    file_line_refs,
    generated_freshness,
    snippet_regions,
    status_prose,
)
from jk_standards.config import (
    ClaimSource,
    Config,
    DocRoot,
    GeneratedDoc,
    SnippetMarkerSyntax,
    SourceRoot,
)


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


# --- action-pinning ---------------------------------------------------------

_WF = ".github/workflows/ci.yml"


def test_action_pinning_floating_ref_flagged(tmp_path):
    write(tmp_path, _WF, "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v6\n")
    assert action_pinning.run(tmp_path, Config()) == 1


def test_action_pinning_sha_pinned_passes(tmp_path):
    sha = "a" * 40
    write(tmp_path, _WF, f"jobs:\n  build:\n    steps:\n      - uses: actions/checkout@{sha}\n")
    assert action_pinning.run(tmp_path, Config()) == 0


def test_action_pinning_marker_same_line_exempts(tmp_path):
    write(
        tmp_path,
        _WF,
        "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v6  # action-pin-ok: pending SHA\n",
    )
    assert action_pinning.run(tmp_path, Config()) == 0


def test_action_pinning_marker_line_above_exempts(tmp_path):
    write(
        tmp_path,
        _WF,
        "jobs:\n  build:\n    steps:\n      # action-pin-ok: pending SHA\n      - uses: actions/checkout@v6\n",
    )
    assert action_pinning.run(tmp_path, Config()) == 0


def test_action_pinning_local_ref_accepted(tmp_path):
    write(tmp_path, _WF, "jobs:\n  build:\n    steps:\n      - uses: ./.github/actions/foo\n")
    assert action_pinning.run(tmp_path, Config()) == 0


def test_action_pinning_docker_image_flagged(tmp_path):
    # A `uses:` with no `@rev` at all (docker image / malformed) is not pinned.
    write(tmp_path, _WF, "jobs:\n  build:\n    steps:\n      - uses: docker://alpine\n")
    assert action_pinning.run(tmp_path, Config()) == 1


def test_action_pinning_missing_workflows_dir_skipped(tmp_path):
    assert action_pinning.run(tmp_path, Config()) == 0


def test_action_pinning_multiple_unpinned_counted(tmp_path):
    write(
        tmp_path,
        _WF,
        "jobs:\n  build:\n    steps:\n      - uses: actions/checkout@v6\n      - uses: actions/setup-node@main\n",
    )
    assert action_pinning.run(tmp_path, Config()) == 2


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


# --- snippet-regions --------------------------------------------------------


def snippet_config() -> Config:
    """Docs scan .md + .mdx; source roots cover poly-style shell/C++ markers."""
    return Config(
        snippet_doc_roots=[DocRoot("docs", [".md", ".mdx"])],
        snippet_source_roots=[SourceRoot("src", [".sh", ".cpp"])],
    )


def test_snippet_regions_codesnippet_mdx_resolves(tmp_path):
    # nfr-review-style <CodeSnippet region=...> resolves against its own file=.
    write(tmp_path, "src/host.cpp", "// region:determinism\nint x;\n// endregion\n")
    write(
        tmp_path,
        "docs/guide.mdx",
        'See below.\n<CodeSnippet file="src/host.cpp" region="determinism" />\n',
    )
    assert snippet_regions.run(tmp_path, snippet_config()) == 0


def test_snippet_regions_prose_resolves_shell_and_cpp(tmp_path):
    # poly-style `# region:` in shell and `// region:` in C++ both feed the
    # union that prose mentions resolve against.
    write(tmp_path, "src/build.sh", "# region:setup\necho hi\n")
    write(tmp_path, "src/host.cpp", "// region:render\nint y;\n")
    write(
        tmp_path,
        "docs/guide.md",
        "The setup lives at region:setup and rendering at region:render\n",
    )
    assert snippet_regions.run(tmp_path, snippet_config()) == 0


def test_snippet_regions_dangling_codesnippet_flagged_with_path_line(tmp_path, capsys):
    write(tmp_path, "src/host.cpp", "// region:real\nint z;\n")
    write(
        tmp_path,
        "docs/guide.mdx",
        'Intro line.\n<CodeSnippet file="src/host.cpp" region="ghost" />\n',
    )
    assert snippet_regions.run(tmp_path, snippet_config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/guide.mdx,line=2::" in err
    assert "ghost" in err


def test_snippet_regions_dangling_prose_flagged_with_path_line(tmp_path, capsys):
    write(tmp_path, "src/build.sh", "# region:setup\necho hi\n")
    write(tmp_path, "docs/guide.md", "First line.\nRefers to region:missing here\n")
    assert snippet_regions.run(tmp_path, snippet_config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/guide.md,line=2::" in err
    assert "missing" in err


def test_snippet_regions_codesnippet_missing_file_flagged(tmp_path, capsys):
    write(tmp_path, "docs/guide.mdx", '<CodeSnippet file="src/gone.cpp" region="x" />\n')
    assert snippet_regions.run(tmp_path, snippet_config()) == 1
    err = capsys.readouterr().err
    assert "src/gone.cpp" in err


def test_snippet_regions_escape_hatch_same_line(tmp_path):
    write(
        tmp_path,
        "docs/guide.md",
        "Refers to region:missing  <!-- snippet-region-ok: worked example -->\n",
    )
    assert snippet_regions.run(tmp_path, snippet_config()) == 0


def test_snippet_regions_escape_hatch_line_above(tmp_path):
    write(
        tmp_path,
        "docs/guide.mdx",
        "{/* snippet-region-ok: template placeholder */}\n"
        '<CodeSnippet file="src/gone.cpp" region="x" />\n',
    )
    assert snippet_regions.run(tmp_path, snippet_config()) == 0


def test_snippet_regions_no_source_roots_skips_prose(tmp_path):
    # With no source roots configured there is nothing to resolve prose against,
    # so bare `region:` mentions are not flagged.
    write(tmp_path, "docs/guide.md", "Mentions region:anything freely\n")
    cfg = Config(snippet_doc_roots=[DocRoot("docs", [".md"])])
    assert snippet_regions.run(tmp_path, cfg) == 0


def test_snippet_regions_per_file_type_marker_syntax(tmp_path):
    # A SQL file's `-- region:` marker is only recognized when the file type is
    # mapped to the `--` prefix via snippet_regions.markers.
    write(tmp_path, "src/schema.sql", "-- region:tables\nSELECT 1;\n")
    write(tmp_path, "docs/guide.md", "Schema at region:tables\n")
    cfg = Config(
        snippet_doc_roots=[DocRoot("docs", [".md"])],
        snippet_source_roots=[SourceRoot("src", [".sql"])],
        snippet_markers=[SnippetMarkerSyntax(extensions=[".sql"], prefixes=["--"])],
    )
    assert snippet_regions.run(tmp_path, cfg) == 0
    # Without the marker mapping, the default prefixes miss `--` and the mention
    # dangles.
    cfg_default = Config(
        snippet_doc_roots=[DocRoot("docs", [".md"])],
        snippet_source_roots=[SourceRoot("src", [".sql"])],
    )
    assert snippet_regions.run(tmp_path, cfg_default) == 1


# --- nfr-review parity ------------------------------------------------------
#
# These fixtures re-express nfr-review's portable scripts/lint_docs.py doc
# checks as jk-standards toolkit config, proving the toolkit produces the same
# pass/fail behavior lint_docs.py produces — without depending on the external
# nfr-review checkout (D003). Everything below is a tmp_path fixture:
#   * lint_docs.py check #3 (compliance.mdx "**N rules**" numeral vs the
#     compliance mapping) -> count-drift with a `rules\b` trigger over .mdx docs.
#   * lint_docs.py check #2 (CodeSnippet region markers resolve to real regions)
#     -> snippet-regions resolving <CodeSnippet region=...> against the source
#     tree.
# (lint_docs.py check #1 — rules.json length == rule_registry length — is a
# non-portable residual nfr-review keeps; it is documented, not tested here.)


def _nfr_count_config() -> Config:
    """nfr-review's compliance.mdx count check: a `rules\\b` trigger over the
    .mdx doc root that holds compliance.mdx."""
    return Config(
        doc_roots=[DocRoot("docs", [".mdx"])],
        count_triggers=[r"rules\b"],
    )


def test_nfr_count_drift_flags_hardcoded_rules_numeral(tmp_path):
    # Mirrors lint_docs.py #3 failing: a bare "**85 rules**" numeral drifts from
    # the compliance mapping the moment a rule is added or removed.
    write(
        tmp_path,
        "docs/compliance.mdx",
        "---\nclass: gated\n---\nThe registry enforces **85 rules** in total.\n",
    )
    assert count_drift.run(tmp_path, _nfr_count_config()) == 1


def test_nfr_count_drift_interpolated_rules_passes(tmp_path):
    # Mirrors lint_docs.py #3 passing once the numeral is interpolated from the
    # generated source of truth.
    write(
        tmp_path,
        "docs/compliance.mdx",
        "---\nclass: gated\n---\nThe registry enforces **{counts.rules} rules** in total.\n",
    )
    assert count_drift.run(tmp_path, _nfr_count_config()) == 0


def test_nfr_count_drift_counts_ok_marker_passes(tmp_path):
    # The `counts-ok` escape hatch matches lint_docs.py's worked-example allowance.
    write(
        tmp_path,
        "docs/compliance.mdx",
        "---\nclass: gated\n---\n<!-- counts-ok: worked example -->\n"
        "The registry enforces **85 rules** in total.\n",
    )
    assert count_drift.run(tmp_path, _nfr_count_config()) == 0


def _nfr_snippet_config() -> Config:
    """nfr-review's CodeSnippet region check: .mdx docs resolving
    <CodeSnippet region=...> against the rule-registry source tree."""
    return Config(
        snippet_doc_roots=[DocRoot("docs", [".mdx"])],
        snippet_source_roots=[SourceRoot("rules", [".ts"])],
    )


def test_nfr_snippet_regions_codesnippet_resolves(tmp_path):
    # Mirrors lint_docs.py #2 passing: the referenced region marker exists.
    write(
        tmp_path,
        "rules/registry.ts",
        "// region:enforcement\nexport const rules = [];\n// endregion\n",
    )
    write(
        tmp_path,
        "docs/compliance.mdx",
        'Enforcement lives here:\n<CodeSnippet file="rules/registry.ts" region="enforcement" />\n',
    )
    assert snippet_regions.run(tmp_path, _nfr_snippet_config()) == 0


def test_nfr_snippet_regions_dangling_codesnippet_flagged(tmp_path, capsys):
    # Mirrors lint_docs.py #2 failing: the referenced region marker is missing,
    # so the snippet silently rots. The finding carries the doc path and line.
    write(
        tmp_path,
        "rules/registry.ts",
        "// region:enforcement\nexport const rules = [];\n",
    )
    write(
        tmp_path,
        "docs/compliance.mdx",
        'Enforcement lives here:\n<CodeSnippet file="rules/registry.ts" region="ghost" />\n',
    )
    assert snippet_regions.run(tmp_path, _nfr_snippet_config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/compliance.mdx,line=2::" in err
    assert "ghost" in err
