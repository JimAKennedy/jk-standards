---
class: gated
---

# Checks reference

Status: current (2026-07-30)

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

## action-pinning

Every GitHub Actions `uses:` reference under `.github/workflows/**/*.yml`
(and `*.yaml`) must be pinned to a full 40-char commit SHA. A floating ref
(`actions/checkout@v6`, `@main`, a bare tag) lets the upstream owner — or
anyone who compromises their account — change what runs in your CI without a
diff on your side, so it is flagged with `file:line`
[verified: test_checks::test_action_pinning_floating_ref_flagged]; a
40-hex-SHA pin passes
[verified: test_checks::test_action_pinning_sha_pinned_passes]. A `docker://`
image with no digest is unpinned and flagged too
[verified: test_checks::test_action_pinning_docker_image_flagged], and every
unpinned ref adds to the returned error count
[verified: test_checks::test_action_pinning_multiple_unpinned_counted].

Local `uses: ./…` (or `../…`) action and reusable-workflow refs are accepted
— they live in your own tree and move with it
[verified: test_checks::test_action_pinning_local_ref_accepted].

Escape hatch: a `# action-pin-ok: <reason>` marker on the offending line
[verified: test_checks::test_action_pinning_marker_same_line_exempts] or the
line immediately above it
[verified: test_checks::test_action_pinning_marker_line_above_exempts]
suppresses the finding, for the rare ref that genuinely cannot be SHA-pinned.
With no `.github/workflows` directory the check skips cleanly
[verified: test_checks::test_action_pinning_missing_workflows_dir_skipped].

The workflow directory and scanned extensions are configurable via the
`action_pinning` config section. The shipped `templates/dependabot.yml` is
the companion that keeps pinned SHAs current by surfacing each upstream
update as a reviewable Dependabot PR — pinning without update automation
rots.

## snippet-regions

Docs point readers at slices of source two ways: an MDX
`<CodeSnippet file=… region=… />` component that renders the named region,
and prose `region:<name>` mentions. Each reference must resolve to a
`region:<name>` marker that actually exists in the declared source tree —
otherwise the snippet silently rots when the region is renamed or deleted,
with no diff on the doc side to warn anyone.

A `<CodeSnippet>` names its own `file=`; that file must exist
[verified: test_checks::test_snippet_regions_codesnippet_missing_file_flagged]
and must define the region
[verified: test_checks::test_snippet_regions_codesnippet_mdx_resolves]. A
region with no matching marker is flagged with `path:line`
[verified: test_checks::test_snippet_regions_dangling_codesnippet_flagged_with_path_line].

Prose mentions carry no file, so they resolve against the union of markers
across the configured `snippet_regions.source_roots` — poly-style
`# region:` in shell and `// region:` in C++ both feed that union
[verified: test_checks::test_snippet_regions_prose_resolves_shell_and_cpp],
and a mention matching no marker is flagged with `path:line`
[verified: test_checks::test_snippet_regions_dangling_prose_flagged_with_path_line].
With no source roots configured there is nothing to resolve against, so
prose scanning is skipped
[verified: test_checks::test_snippet_regions_no_source_roots_skips_prose];
CodeSnippet references, which name their own file, are still validated.

Marker syntax mirrors `site/src/components/CodeSnippet.astro`, the three
forms the repo already renders — `// region:`, `# region:`, and
`<!-- region: -->` — and is per-file-type overridable via
`snippet_regions.markers`, so a repo can map its own comment style (a SQL
`-- region:`, say) onto a file extension
[verified: test_checks::test_snippet_regions_per_file_type_marker_syntax].

Escape hatch: a `# snippet-region-ok: <reason>` marker on the reference line
[verified: test_checks::test_snippet_regions_escape_hatch_same_line] or the
line immediately above it
[verified: test_checks::test_snippet_regions_escape_hatch_line_above]
suppresses the finding — the same two-line window used by action-pinning,
count-drift, and file-line-refs.

## boundaries

A *boundary* is a directed constraint between components — one directory
**MUST NOT** reference another (the CLI may call the check registry, but a
check must not reach back into the CLI). It is the most common architectural
invariant and the easiest to break by accident, so this check turns a stated
boundary into a grep-level gate: each configured rule names a `from` directory,
an optional file-`extensions` filter, and a `forbid` regex, and any line under
that directory matching the regex is flagged with `file:line`
[verified: test_checks::test_boundaries_forbidden_reference_flagged_with_file_line].
A clean tree passes
[verified: test_checks::test_boundaries_clean_tree_passes], and every matching
line adds to the returned violation count
[verified: test_checks::test_boundaries_multiple_violations_counted]. This is a
line-level textual gate, not an import graph — it catches the reference forms
you name and nothing subtler.

The `extensions` filter narrows the scan to the relevant source files, so a
prose mention of the forbidden path in a neighbouring `.md` note is not a
violation
[verified: test_checks::test_boundaries_extensions_filter_ignores_other_files].
A rule whose `from` directory is absent skips cleanly rather than crashing
[verified: test_checks::test_boundaries_missing_from_dir_skips_rule], and a
malformed `forbid` regex is surfaced as a violation so a broken rule fails
loudly instead of silently passing
[verified: test_checks::test_boundaries_invalid_forbid_regex_is_a_violation].
With no `boundaries` rules configured the check is a clean no-op
[verified: test_checks::test_boundaries_no_rules_configured_skips].

Escape hatch: a `# boundary-ok: <reason>` marker on the offending line
[verified: test_checks::test_boundaries_ok_marker_same_line_suppresses] or the
line immediately above it
[verified: test_checks::test_boundaries_ok_marker_line_above_suppresses]
suppresses the finding, honoring any language-appropriate comment opener
(`#`, `//`, `/*`, `<!--`, `--`, `;`). Unlike the other escape hatches, live
suppressions are counted and reported in the check's summary line
[verified: test_checks::test_boundaries_suppression_count_reported_in_summary],
so rising escape-hatch usage is visible in CI logs rather than silent. Rules
are declared in the `boundaries` config section.

## research-provenance

Documentation that summarises published scholarship must make its
provenance mechanically visible, so summarised prior work can never be
mistaken for original research. The check is opted in by configuring
`research_provenance.bib_file`; with no bibliography configured it is
skipped [verified: test_checks::test_provenance_unconfigured_skips], and a
configured path that doesn't exist is flagged rather than silently passing
[verified: test_checks::test_provenance_missing_bib_file_flagged].

Citation resolution applies to every non-archived doc: a citation link
(`#ref-*` / `#fr-*`, or whatever `anchor_pattern` matches) must resolve to
an `id="..."` defined in the bibliography file — a dangling anchor is
flagged with `path:line`
[verified: test_checks::test_provenance_dangling_citation_flagged_with_path_line],
a resolving one passes
[verified: test_checks::test_provenance_resolved_citation_passes], and a
bibliography id defined twice is flagged at its redefinition
[verified: test_checks::test_provenance_duplicate_bib_ids_flagged_with_file_line]
— entries are stable anchors, never renumbered. The anchor pattern is
configurable
[verified: test_checks::test_provenance_custom_anchor_pattern], and a
malformed pattern is surfaced as a violation so a broken config fails
loudly
[verified: test_checks::test_provenance_invalid_anchor_pattern_is_a_violation].

Pages opted in via `provenance: research` front-matter must additionally
carry a provenance sentence matching the configured `phrase` regex
(default `not original (research|theory)`)
[verified: test_checks::test_provenance_research_page_missing_sentence_flagged]
and an `**Attribution:**` note assigning claims to the three provenance
classes — sourced claim, practical distillation, project-specific value
[verified: test_checks::test_provenance_research_page_missing_attribution_flagged].
A page carrying both passes
[verified: test_checks::test_provenance_conformant_research_page_passes];
pages without the front-matter marker get citation checking only
[verified: test_checks::test_provenance_unmarked_page_needs_no_markers],
and archived docs are exempt throughout
[verified: test_checks::test_provenance_archived_docs_exempt]. The prose
discipline behind the markers is the `research-provenance` skill.

Escape hatch: a `# provenance-ok: <reason>` marker on the citing line
[verified: test_checks::test_provenance_ok_marker_same_line_exempts] or the
line immediately above it
[verified: test_checks::test_provenance_ok_marker_line_above_exempts]
suppresses citation-resolution findings, for links that legitimately point
outside the project's bibliography — the same two-line window used by
action-pinning, count-drift, and snippet-regions. The page-level
requirements have no marker hatch: a page that shouldn't carry them
shouldn't declare `provenance: research`.
