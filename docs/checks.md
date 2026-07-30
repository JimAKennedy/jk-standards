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

The map also carries a `cannot_drift` registry: docs that legitimately have
no touch-correlation source, each recording a required, non-empty `reason` so
a deliberate exemption is distinguishable from an accidental omission (the
distinction doc-completeness keys off). A valid entry parses
[verified: test_doc_drift::test_cannot_drift_valid_entry_parses]; an entry
missing its reason
[verified: test_doc_drift::test_cannot_drift_missing_reason_rejected], with a
blank reason
[verified: test_doc_drift::test_cannot_drift_empty_reason_rejected], or missing
its `doc` key
[verified: test_doc_drift::test_cannot_drift_missing_doc_rejected] is a config
error surfaced as exit 2
[verified: test_doc_drift::test_cannot_drift_invalid_entry_cli_exit_2]. The
worked example is `site/src/content/docs/reference/skills.mdx`: it renders its
catalog by importing `site/src/generated/skills.json` at build time — nothing
on the page is hand-maintained — so a skill add or rename updates the
generated JSON (freshness-gated by generated-freshness and the emit `--check`)
and the page reflects it with no source edit to mirror. Mapping a
touch-correlation rule at a build-time-generated page would only manufacture a
false positive on every skill change, so it is declared cannot_drift instead.

## doc-completeness

Every doc `iter_docs` enumerates under a configured `doc_root` must be
accounted for in the drift map — either as a mapping's `doc:` target or as a
`cannot_drift` entry. A page that is neither is an accidental omission, and
this check names it: it emits `::error file=<doc>,line=1::` for each
unregistered doc and fails
[verified: test_doc_completeness::test_unregistered_doc_fails_naming_it], while
a doc that is mapped
[verified: test_doc_completeness::test_mapped_only_passes] or declared
un-driftable
[verified: test_doc_completeness::test_cannot_drift_only_passes] passes. The
remediation names both escape routes — add a mappings entry or a cannot_drift
entry — and deliberately does not name the docs already accounted for. On
success it prints `doc-completeness: all N doc(s) mapped or declared`
[verified: test_doc_completeness::test_success_emits_summary].

Unlike doc-drift it needs no git base ref: the working tree and the map are
its only inputs, so it runs unconditionally as a static check under
`jk-standards all` and as a pre-commit hook. It honors the same `doc_roots`,
extensions, and `exempt_dirs` as every other doc check — a file outside the
configured extensions is never enumerated
[verified: test_doc_completeness::test_multiple_doc_roots_and_extensions] and
an `exempt_dirs` path is skipped
[verified: test_doc_completeness::test_exempt_dirs_excluded].

It reuses doc-drift's `cannot_drift` parser, so a malformed registry — an entry
missing its required `reason` — surfaces as the same `config error:` (exit 2)
rather than a traceback
[verified: test_doc_completeness::test_malformed_cannot_drift_cli_exit_2], and a
mappings entry missing its `doc` key fails the same way
[verified: test_doc_completeness::test_mapping_missing_doc_key_cli_exit_2]. A
missing drift map is itself a failure
[verified: test_doc_completeness::test_missing_drift_map_fails].

## doc-coverage

The doc-drift family catches a doc that lies about code; this check catches the
opposite gap — code that no doc, and no docstring, describes at all. It walks the
configured Python source roots and enumerates each module's public documentable
units (the module itself, its top-level public classes and functions, and those
classes' public methods), then asks of every unit whether ANY of three
independent OR-signals holds:

- **docstring** — the unit carries a non-empty docstring.
- **drift** — the unit's file matches a `sources:` glob in the drift map, so a
  change to it is already touch-correlated to a doc.
- **mention** — the unit's bare symbol name appears as a whole word in one of the
  configured doc scopes.

A unit is documented iff at least one signal fires — the disjunction, not the
conjunction [verified: test_doc_coverage::test_docunit_documented_is_disjunction].
A docstring on the module alone keeps the module green
[verified: test_doc_coverage::test_module_docstring_alone_keeps_module_green], a
`sources:` glob match documents it via the drift signal
[verified: test_doc_coverage::test_drift_map_glob_documents_module], and a
whole-word symbol mention in a doc scope documents it via the mention signal
[verified: test_doc_coverage::test_symbol_mention_in_doc_scope_documents_module].
The mention is a whole-word match, not a substring — a symbol embedded in a
longer token does not count
[verified: test_doc_coverage::test_mention_is_whole_word_not_substring].

The gate is deliberately lenient: it fails at **module granularity**. A module is
flagged only when EVERY one of its public units is undocumented by all three
signals — a genuinely bare file that nothing, anywhere, describes
[verified: test_doc_coverage::test_fully_bare_module_fails]. One
`::error file=<module>,line=1::` is emitted per fully-undocumented module so it
surfaces inline on PRs
[verified: test_doc_coverage::test_bare_module_emits_error_with_path_and_line],
and the summary line reports the unit count, module count, undocumented count,
and live-waiver count
[verified: test_doc_coverage::test_clean_run_summary_reports_unit_and_module_counts].

**Baseline ratchet.** Beyond the binary bare-module gate, the check enforces a
per-module floor: it recomputes each module's live documented-unit ratio and
compares it against the committed floor recorded at `baselines/doc-coverage.json`,
hard-failing any module that slipped below its recorded ratio and naming the
module with its before/after ratio
[verified: test_doc_coverage::test_ratchet_regression_below_floor_fails_naming_module_and_ratio].
The ratchet composes with — it does not replace — the binary gate
[verified: test_doc_coverage::test_ratchet_composes_with_binary_gate]: holding at
the floor passes
[verified: test_doc_coverage::test_ratchet_holding_at_floor_passes], improving
above it passes
[verified: test_doc_coverage::test_ratchet_improvement_above_floor_passes], and a
module not yet in the baseline is first-seen-passes
[verified: test_doc_coverage::test_ratchet_new_module_not_in_baseline_passes]. With
no baseline committed yet the ratchet is inert and the summary line says so
[verified: test_doc_coverage::test_ratchet_no_baseline_passes_and_reports_first_run].
The floor map is recorded — and ratcheted up — only through the explicit
`doc-coverage --update-baseline` CLI flag (never `emit all`, so a floor can never
silently self-heal); a write that would *lower* an existing floor is refused
unless `--allow-regression` is also passed
[verified: test_doc_coverage::test_update_baseline_lowering_refused_without_allow_regression],
and re-recording an unchanged tree reproduces the file byte-for-byte
[verified: test_doc_coverage::test_update_baseline_is_byte_idempotent].

**Advisory floor.** An optional `doc_coverage.module_min_percent` sets a soft
per-module target: a module whose live documented-unit ratio is below that
percentage emits a `::warning` (surfaced inline on the PR) and is tallied in the
summary line, but the advisory never fails the build — it is strictly additive to
the binary gate and the ratchet
[verified: test_doc_coverage::test_advisory_below_floor_warns_but_exit_stays_zero].
A module exactly at the floor is not flagged
[verified: test_doc_coverage::test_advisory_at_floor_not_flagged], and when the
field is unset the summary line is byte-identical to before, with no advisory
clause and no warnings
[verified: test_doc_coverage::test_advisory_unset_adds_no_clause_and_no_warning].

Escape hatch: a `# doc-coverage-ok: <reason>` marker in the file's leading comment
block (before the first code) waives the whole module in place
[verified: test_doc_coverage::test_escape_hatch_waives_module]; a shebang above
the marker is fine
[verified: test_doc_coverage::test_escape_hatch_after_shebang_still_waives], but a
marker buried in code or a docstring does not waive
[verified: test_doc_coverage::test_marker_buried_in_code_does_not_waive]. Live
waivers are counted in the summary line so rising escape-hatch usage stays visible
in CI logs.

Scope: Python and C++. The default enumerator is an `ast` walk over the
configured source roots; sources with a C++ suffix (`.cpp`, `.cc`, `.cxx`,
`.c++`, `.hpp`, `.hh`, `.hxx`, `.h++`, `.h`, `.c`) are instead parsed with
tree-sitter-cpp and enumerated by a public-declaration heuristic:

- **function** — a named function declaration or definition at namespace scope
  (recursing into `namespace`/`extern "C"` bodies so the true name is used).
- **class** / **struct** — a named `class` or `struct` specifier; anonymous ones
  are skipped since no doc could name them.
- **method** — a *public* member function, resolved with C++ default-access
  rules: a `class` starts private and a `struct` starts public, and each
  `public:`/`private:`/`protected:` label flips visibility for the members that
  follow, so only currently-public methods are enumerated.

The `has_docstring` signal fires when a Doxygen doc comment — one opening with
`///`, `//!`, `/**`, or `/*!` — sits on the line immediately above the
declaration; a plain `//` or `/* */` comment does not count, mirroring how a
Python docstring (not any comment) is the signal. The drift and mention
OR-signals, the disjunction rule, and the module-granular gate all carry over
unchanged — a C++ unit is documented iff it has a doc comment, its file matches a
drift-map `sources:` glob, or its bare name is mentioned in a doc scope.

Known limits: the native grammar ships only in the optional `jk-standards[cpp]`
extra. When a C++ source root is configured but tree-sitter-cpp is not installed,
the check degrades gracefully rather than failing — the C++ files contribute zero
units and a single summary line reports how many were skipped and points at
`jk-standards[cpp]`, so a grammar-less repo keeps working on the PyYAML-only
zero-dependency default. A C++ file that fails to parse into a translation unit
likewise contributes zero units instead of raising. With no source roots
configured the check skips cleanly.

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
