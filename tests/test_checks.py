"""Fixture-repo tests for the static checks."""

from pathlib import Path

from jk_standards.checks import (
    action_pinning,
    behavioral_claims,
    boundaries,
    count_drift,
    doc_taxonomy,
    file_line_refs,
    generated_freshness,
    research_provenance,
    snippet_regions,
    status_prose,
)
from jk_standards.config import (
    BoundaryRule,
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


# --- boundaries -------------------------------------------------------------


def _boundary_config(**overrides) -> Config:
    """A single rule: files under src/jk_standards/checks must not import cli."""
    params = {
        "from_dir": "src/jk_standards/checks",
        "forbid": r"jk_standards\.cli",
        "name": "checks-must-not-import-cli",
        "extensions": [".py"],
        "hint": "a check must not reach back into the CLI",
    }
    params.update(overrides)
    return Config(boundaries=[BoundaryRule(**params)])


def test_boundaries_no_rules_configured_skips(tmp_path):
    # With no boundaries section, the check is a clean no-op (T03 dogfood state).
    write(tmp_path, "src/jk_standards/checks/x.py", "from jk_standards.cli import main\n")
    assert boundaries.run(tmp_path, Config()) == 0


def test_boundaries_forbidden_reference_flagged_with_file_line(tmp_path, capsys):
    write(
        tmp_path,
        "src/jk_standards/checks/x.py",
        "import os\nfrom jk_standards.cli import main\n",
    )
    assert boundaries.run(tmp_path, _boundary_config()) == 1
    err = capsys.readouterr().err
    assert "::error file=src/jk_standards/checks/x.py,line=2::" in err
    assert "a check must not reach back into the CLI" in err


def test_boundaries_clean_tree_passes(tmp_path):
    write(tmp_path, "src/jk_standards/checks/x.py", "import os\n\n\ndef run():\n    pass\n")
    assert boundaries.run(tmp_path, _boundary_config()) == 0


def test_boundaries_extensions_filter_ignores_other_files(tmp_path):
    # A non-.py file carrying the forbidden text is not scanned.
    write(tmp_path, "src/jk_standards/checks/note.md", "mentions jk_standards.cli here\n")
    assert boundaries.run(tmp_path, _boundary_config()) == 0


def test_boundaries_ok_marker_same_line_suppresses(tmp_path):
    write(
        tmp_path,
        "src/jk_standards/checks/x.py",
        "from jk_standards.cli import main  # boundary-ok: bootstrap shim\n",
    )
    assert boundaries.run(tmp_path, _boundary_config()) == 0


def test_boundaries_ok_marker_line_above_suppresses(tmp_path):
    write(
        tmp_path,
        "src/jk_standards/checks/x.py",
        "# boundary-ok: bootstrap shim\nfrom jk_standards.cli import main\n",
    )
    assert boundaries.run(tmp_path, _boundary_config()) == 0


def test_boundaries_suppression_count_reported_in_summary(tmp_path, capsys):
    write(
        tmp_path,
        "src/jk_standards/checks/x.py",
        "from jk_standards.cli import main  # boundary-ok: shim\n",
    )
    assert boundaries.run(tmp_path, _boundary_config()) == 0
    out = capsys.readouterr().out
    assert "1 suppression(s) via boundary-ok" in out


def test_boundaries_missing_from_dir_skips_rule(tmp_path):
    # No source tree at all — the rule skips rather than crashing.
    assert boundaries.run(tmp_path, _boundary_config()) == 0


def test_boundaries_invalid_forbid_regex_is_a_violation(tmp_path, capsys):
    write(tmp_path, "src/jk_standards/checks/x.py", "import os\n")
    assert boundaries.run(tmp_path, _boundary_config(forbid="(unclosed")) == 1
    out = capsys.readouterr().out
    assert "invalid forbid pattern" in out


def test_boundaries_multiple_violations_counted(tmp_path):
    write(
        tmp_path,
        "src/jk_standards/checks/x.py",
        "from jk_standards.cli import main\nimport jk_standards.cli as c\n",
    )
    assert boundaries.run(tmp_path, _boundary_config()) == 2


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


# --- poly boundaries parity -------------------------------------------------
#
# poly's ARCHITECTURE.md states two boundary invariants its reusable DSP engine
# must hold. These fixtures re-express them as jk-standards boundary rules and
# prove the check generalizes beyond this repo's own two-rule dogfood — flagging
# real violations with file:line, honoring the C/C++ `// boundary-ok:` and
# shell/python `# boundary-ok:` escape hatches, and passing a clean tree —
# without depending on the external poly checkout (D003, mirroring the
# nfr-review parity precedent above).
#   * engine-isolation: engine/src MUST NOT reference the VST3 SDK. poly names
#     four forbidden header namespaces, enforced as one multi-pattern regex
#     alternation `vst3sdk|vstgui|public\.sdk|pluginterfaces`, so the DSP engine
#     stays plugin-format-agnostic and hostable under any wrapper.
#   * drumcore-independence: nothing under engine/ may reference `drumcore` —
#     the reusable engine cannot depend on the app-specific drumcore layer.

_VST3_FORBID = r"vst3sdk|vstgui|public\.sdk|pluginterfaces"

# The four forbidden VST3-SDK header namespaces poly's alternation guards, each
# as a realistic `#include` line under engine/src.
_VST3_INCLUDES = [
    "#include <vst3sdk/vst.h>",
    "#include <vstgui/lib/cview.h>",
    "#include <public.sdk/source/vst/vstaudioeffect.h>",
    "#include <pluginterfaces/base/funknown.h>",
]


def _poly_engine_isolation_config() -> Config:
    """poly's engine-isolation invariant: engine/src C/C++ sources must not
    reference the VST3 SDK (multi-pattern alternation over four headers)."""
    return Config(
        boundaries=[
            BoundaryRule(
                from_dir="engine/src",
                forbid=_VST3_FORBID,
                name="engine-isolation",
                extensions=[".cpp", ".h", ".hpp"],
                hint="the DSP engine must stay VST3-SDK-agnostic",
            )
        ]
    )


def _poly_drumcore_config(**overrides) -> Config:
    """poly's drumcore-independence invariant: nothing under engine/ may
    reference the app-specific drumcore layer. No extensions filter — the rule
    scans every file under engine/, including build scripts."""
    params = {
        "from_dir": "engine",
        "forbid": r"drumcore",
        "name": "drumcore-independence",
        "hint": "the reusable engine must not depend on drumcore",
    }
    params.update(overrides)
    return Config(boundaries=[BoundaryRule(**params)])


def test_poly_engine_isolation_flags_vst3_include_with_file_line(tmp_path, capsys):
    # A real engine-isolation violation: an engine source pulls in the VST3 SDK.
    # The finding carries the exact engine/src path, line, and the rule hint.
    write(
        tmp_path,
        "engine/src/render.cpp",
        "#include <cmath>\n#include <public.sdk/source/vst/vstaudioeffect.h>\n",
    )
    assert boundaries.run(tmp_path, _poly_engine_isolation_config()) == 1
    err = capsys.readouterr().err
    assert "::error file=engine/src/render.cpp,line=2::" in err
    assert "the DSP engine must stay VST3-SDK-agnostic" in err


def test_poly_engine_isolation_alternation_matches_each_header(tmp_path):
    # Each of the four forbidden header namespaces trips the alternation, proving
    # the multi-pattern `forbid` regex generalizes past a single literal.
    for i, include in enumerate(_VST3_INCLUDES):
        write(tmp_path, f"engine/src/dsp_{i}.cpp", f"{include}\nvoid process();\n")
    assert boundaries.run(tmp_path, _poly_engine_isolation_config()) == 4


def test_poly_engine_isolation_clean_tree_passes(tmp_path):
    # A format-agnostic engine tree — only standard-library and internal headers.
    write(tmp_path, "engine/src/render.cpp", '#include <cmath>\n#include "engine/dsp.h"\n')
    write(tmp_path, "engine/src/dsp.h", "#pragma once\nvoid process();\n")
    assert boundaries.run(tmp_path, _poly_engine_isolation_config()) == 0


def test_poly_engine_isolation_ok_marker_same_line_suppresses(tmp_path, capsys):
    # A genuinely-necessary SDK crossing waived in place on the `#include` line
    # with the C/C++ `// boundary-ok:` form.
    write(
        tmp_path,
        "engine/src/shim.cpp",
        "#include <pluginterfaces/base/funknown.h>  // boundary-ok: thin format shim\n",
    )
    assert boundaries.run(tmp_path, _poly_engine_isolation_config()) == 0
    assert "1 suppression(s) via boundary-ok" in capsys.readouterr().out


def test_poly_engine_isolation_ok_marker_line_above_suppresses(tmp_path):
    # The C/C++ `// boundary-ok:` marker on the line above the `#include` also
    # suppresses — matching the two-line escape-hatch contract.
    write(
        tmp_path,
        "engine/src/shim.cpp",
        "// boundary-ok: thin format shim\n#include <vstgui/lib/cview.h>\n",
    )
    assert boundaries.run(tmp_path, _poly_engine_isolation_config()) == 0


def test_poly_drumcore_independence_flags_with_file_line(tmp_path, capsys):
    # The drumcore-independence invariant: an engine source reaches into the
    # app-specific drumcore layer. Flagged with the engine/ path and line.
    write(
        tmp_path,
        "engine/src/voice.cpp",
        '#include "engine/dsp.h"\n#include "drumcore/kit.h"\n',
    )
    assert boundaries.run(tmp_path, _poly_drumcore_config()) == 1
    err = capsys.readouterr().err
    assert "::error file=engine/src/voice.cpp,line=2::" in err
    assert "the reusable engine must not depend on drumcore" in err


def test_poly_drumcore_ok_marker_shell_and_python_suppress(tmp_path, capsys):
    # The `# boundary-ok:` escape-hatch form works for shell and Python build
    # helpers under engine/ — proving the `.sh`/`.py` comment syntax is honored,
    # not just C/C++ `//`. Both crossings are waived, so the tree is clean and
    # the summary reports two live suppressions.
    write(
        tmp_path,
        "engine/scripts/gen.sh",
        "#!/usr/bin/env bash\npython drumcore/gen.py  # boundary-ok: build-time codegen only\n",
    )
    write(
        tmp_path,
        "engine/scripts/gen.py",
        "import drumcore  # boundary-ok: build-time codegen only\n",
    )
    assert boundaries.run(tmp_path, _poly_drumcore_config()) == 0
    assert "2 suppression(s) via boundary-ok" in capsys.readouterr().out


# --- research-provenance ----------------------------------------------------

BIB = "docs/references.md"


def _provenance_config(**overrides) -> Config:
    return Config(provenance_bib_file=BIB, **overrides)


def _write_bib(root: Path, *anchors: str) -> None:
    entries = "\n".join(f'- <span id="{a}">Author (Year). *Title*.</span>' for a in anchors)
    write(root, BIB, f"---\nclass: gated\n---\n# References\n\n{entries}\n")


def test_provenance_unconfigured_skips(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nSee [X](#ref-nowhere).\n")
    assert research_provenance.run(tmp_path, Config()) == 0


def test_provenance_missing_bib_file_flagged(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nProse.\n")
    assert research_provenance.run(tmp_path, _provenance_config()) == 1


def test_provenance_duplicate_bib_ids_flagged_with_file_line(tmp_path, capsys):
    _write_bib(tmp_path, "ref-keil-1987", "ref-keil-1987")
    assert research_provenance.run(tmp_path, _provenance_config()) == 1
    assert f"::error file={BIB},line=7::" in capsys.readouterr().err


def test_provenance_dangling_citation_flagged_with_path_line(tmp_path, capsys):
    _write_bib(tmp_path, "ref-arom-1991")
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\n---\nThe referent concept is [Arom's](#fr-arom-1991).\n",
    )
    assert research_provenance.run(tmp_path, _provenance_config()) == 1
    assert "::error file=docs/a.md,line=4::" in capsys.readouterr().err


def test_provenance_resolved_citation_passes(tmp_path):
    _write_bib(tmp_path, "fr-arom-1991", "ref-1")
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\n---\nSee [Arom 1991](references.md#fr-arom-1991) and [1](#ref-1).\n",
    )
    assert research_provenance.run(tmp_path, _provenance_config()) == 0


def test_provenance_research_page_missing_sentence_flagged(tmp_path):
    _write_bib(tmp_path, "ref-1")
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\nprovenance: research\n---\n"
        "Rules here.\n\n**Attribution:** Rule 1 is [1](#ref-1) summarised.\n",
    )
    assert research_provenance.run(tmp_path, _provenance_config()) == 1


def test_provenance_research_page_missing_attribution_flagged(tmp_path):
    _write_bib(tmp_path, "ref-1")
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\nprovenance: research\n---\n"
        "Summarised from published scholarship — not original theory.\n",
    )
    assert research_provenance.run(tmp_path, _provenance_config()) == 1


def test_provenance_conformant_research_page_passes(tmp_path):
    _write_bib(tmp_path, "ref-1")
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\nprovenance: research\n---\n"
        "Prior work restated — not original research.\n\n"
        "**Attribution:** Rule 1 is [1](#ref-1) summarised; all values are ours.\n",
    )
    assert research_provenance.run(tmp_path, _provenance_config()) == 0


def test_provenance_unmarked_page_needs_no_markers(tmp_path):
    # Citation resolution applies everywhere, but the sentence/Attribution
    # requirements bind only pages that opt in via `provenance: research`.
    _write_bib(tmp_path, "ref-1")
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nPlain prose citing [1](#ref-1).\n")
    assert research_provenance.run(tmp_path, _provenance_config()) == 0


def test_provenance_archived_docs_exempt(tmp_path):
    _write_bib(tmp_path, "ref-1")
    write(tmp_path, "docs/old.md", "---\nclass: archived\n---\nRotted cite [9](#ref-9).\n")
    assert research_provenance.run(tmp_path, _provenance_config()) == 0


def test_provenance_ok_marker_same_line_exempts(tmp_path):
    _write_bib(tmp_path, "ref-1")
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\n---\n"
        "External page [anchor](https://example.com/#ref-x) "
        "<!-- provenance-ok: not our bibliography -->\n",
    )
    assert research_provenance.run(tmp_path, _provenance_config()) == 0


def test_provenance_ok_marker_line_above_exempts(tmp_path):
    _write_bib(tmp_path, "ref-1")
    write(
        tmp_path,
        "docs/a.md",
        "---\nclass: gated\n---\n"
        "<!-- provenance-ok: not our bibliography -->\n"
        "External page [anchor](https://example.com/#ref-x).\n",
    )
    assert research_provenance.run(tmp_path, _provenance_config()) == 0


def test_provenance_custom_anchor_pattern(tmp_path):
    write(tmp_path, BIB, '---\nclass: gated\n---\n<span id="bib-arom"></span>\n')
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\nSee [Arom](#bib-nope).\n")
    cfg = _provenance_config(provenance_anchor_pattern=r"bib-[a-z]+")
    assert research_provenance.run(tmp_path, cfg) == 1


def test_provenance_invalid_anchor_pattern_is_a_violation(tmp_path):
    _write_bib(tmp_path, "ref-1")
    cfg = _provenance_config(provenance_anchor_pattern=r"(unclosed")
    assert research_provenance.run(tmp_path, cfg) == 1
