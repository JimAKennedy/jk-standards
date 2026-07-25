---
class: gated
---

# Checks reference

Status: current (2026-07-25)

Each check is exposed as a CLI subcommand (`jk-standards <name>`), and the
doc-facing ones also ship as pre-commit hooks. All checks emit
GitHub-Actions `::error` annotations and exit non-zero on violations.

## doc-taxonomy

Every doc under the configured roots must carry YAML front-matter
`class: <value>` from the configured vocabulary (default `generated`,
`gated`, `archived`). A doc with no front-matter fails
[verified: test_checks::test_missing_class_flagged], as does an unknown
class value [verified: test_checks::test_invalid_class_flagged].

The class is the contract the other checks key off: gated docs are linted
and drift-mapped, archived docs are exempt, generated docs are
freshness-checked.

## status-prose

Applies only to `class: gated` docs; archived docs are exempt
[verified: test_checks::test_archived_docs_exempt_from_status_prose].

Rule 1 — a `Status:` line must carry a `(YYYY-MM-DD)` anchor. Undated
status fails [verified: test_checks::test_undated_status_flagged]; a dated
one passes [verified: test_checks::test_dated_status_passes].

Rule 2 — progress-tracking phrases (the not-yet-implemented family, phase
tracking, TODO-count claims) are rejected outright
[verified: test_checks::test_forbidden_phrase_flagged]. That state belongs
in the changelog, issues, or generated dashboards. Extra project-specific
phrases can be added via `status_prose.forbidden_extra`.

## file-line-refs

Enduring docs and source comments must cite symbols or region names, not
line numbers — references like `engine.cpp:42` <!-- [file-line-ok] this literal is the check's own worked example -->
rot on the next edit and are flagged
[verified: test_checks::test_file_line_ref_in_doc_flagged].

Docs are scanned on every line. Configured source roots are scanned only
inside comments — the same reference in a string literal is code, not
commentary, and is ignored
[verified: test_checks::test_source_comment_scanned_code_ignored].

Escape hatch: a `[file-line-ok]` marker on the line
[verified: test_checks::test_file_line_ok_marker_exempts], for
consciously-pinned references such as commit-SHA permalinks. Dated review
records belong in `exempt_dirs` — their line refs are frozen by the
review's date anchor.

## count-drift

A numeral (Arabic or spelled out) adjacent to a configured inventory
trigger phrase is flagged
[verified: test_checks::test_hardcoded_count_flagged] — the fact belongs in
a generated source of truth, interpolated as `{counts.x}`, which is never
flagged [verified: test_checks::test_counts_template_passes].

Triggers are project-supplied and should be inventory-scoped phrases, not
bare nouns, so compositional prose never matches. With no triggers
configured the check is skipped.

Exemptions: archived docs; fenced code blocks
[verified: test_checks::test_code_fence_exempt]; markdown table rows; and
`counts-ok` markers on the line, the preceding line, or whole-file before
the first heading [verified: test_checks::test_counts_ok_marker_exempts].

## behavioral-claims

Opt-in markers make prose claims machine-checkable:

- A `verified:` marker must cite an entry in the scraped test index — an
  unresolved citation fails
  [verified: test_checks::test_unresolved_citation_flagged], a resolving
  one passes [verified: test_checks::test_resolved_citation_passes].
- The ⚠-unverified marker is allowed but counted and warned — the
  honest-state metric
  [verified: test_checks::test_unverified_marker_is_warning_not_error].

Citation formats by index source: `Suite.TestName` for gtest
[verified: test_checks::test_gtest_index_resolves], `filestem/slug` for js
test files, `filestem::test_name` for pytest.

## generated-freshness

For each configured (doc, command) pair the check snapshots the tracked
content, runs the generator, diffs, and restores the snapshot — a stale doc
is flagged and the working tree is left untouched
[verified: test_checks::test_stale_generated_doc_flagged_and_restored]; a
fresh doc passes [verified: test_checks::test_fresh_generated_doc_passes].

## doc-drift

Diff-scoped: needs a git base ref (`--base`, or `GITHUB_BASE_REF` in CI).
Reads the drift map; if the change touches a mapping's sources without
touching its doc, the check fails
[verified: test_doc_drift::test_source_change_without_doc_flagged].
Touching the doc in the same range satisfies the mapping
[verified: test_doc_drift::test_source_change_with_doc_passes], unmapped
changes pass untouched
[verified: test_doc_drift::test_unmapped_change_passes], and a
`Docs-Not-Affected: <reason>` commit trailer bypasses with the
justification recorded in history
[verified: test_doc_drift::test_trailer_bypasses].

The trailer is a range-level assertion: one trailer satisfies every
triggered mapping in the PR.

Manifests listed in `doc_drift.deps_only_manifests` are excluded from
triggering mappings when their diff touches only version strings inside
`dependencies`/`devDependencies`
[verified: test_doc_drift::test_deps_only_bump_does_not_trigger] — a
Dependabot bump is not a taxonomy change. A `scripts`-block edit in the
same file still triggers
[verified: test_doc_drift::test_scripts_block_change_still_triggers], and
manifests not listed get no exemption
[verified: test_doc_drift::test_unlisted_manifest_still_triggers_on_deps_bump].
