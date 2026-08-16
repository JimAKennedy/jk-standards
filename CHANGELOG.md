# Changelog

All notable changes to jk-standards are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.8.0] - 2026-08-16

### Added

- **`import-cycle` check**
  (`src/jk_standards/checks/import_cycle.py`): module-level import-cycle
  detection for configured Python packages. A per-language `extract_edges`
  dispatch seam holds the Python extractor (C++-ready, Python-only here); an
  iterative Tarjan pass turns the resulting edges into every strongly-connected
  component of more than one module, reported at `file:line` with its full
  member chain in deterministic order. Imports guarded by `TYPE_CHECKING` are
  not runtime edges and do not form a cycle; a `try`/`except` import does.
  Escape hatch: `# import-cycle-ok: <reason>` on an in-cycle import line waives
  that cycle, and live suppressions are counted in the summary.
- **`import_cycle` config section** (`src/jk_standards/config.py`): a
  `packages` list of package directories to scan. An absent or empty list
  yields nothing to scan, so the check skips — mirroring `boundaries`'
  skip-when-unconfigured contract. A non-list `packages`, or a non-string
  entry, raises a config error surfaced as exit 2 rather than coercing.
- **`workflow-permissions` check**
  (`src/jk_standards/checks/workflow_permissions.py`): the mechanical gate for
  the reusable-workflow permission ceiling. For every job calling a local
  reusable workflow (`uses: ./…`) it resolves the caller's effective grant —
  the calling job's `permissions:` block, else the workflow's — and compares it
  against the union of the scopes the callee declares at both workflow and job
  level, reporting any shortfall at the `uses:` line. A caller declaring no
  block is skipped, since its grant comes from a repository default no static
  check can see. Escape hatch: `# workflow-permissions-ok: <reason>`.
- **`workflow-concurrency` check**
  (`src/jk_standards/checks/workflow_concurrency.py`): every `concurrency:`
  group, at workflow and job level, must either carry a ref-scoping expression
  or name a lock declared under `workflow_concurrency.global_locks`. This turns
  the distinction between a deliberate repo-wide mutex and a forgotten
  `github.ref` into a diff-time gate rather than a property that only surfaces
  under concurrent load. Escape hatch: `# concurrency-scope-ok: <reason>`.
- **Workflow parsing support module** (`src/jk_standards/workflows.py`):
  composes workflow YAML into plain data alongside a node-path-to-line map, so
  a composition finding can be reported at `file:line`; plus the permission
  level algebra (`none` < `read` < `write`, `read-all`/`write-all` expansion,
  and the distinction between an absent block and `permissions: {}`).
- **`workflow_permissions` and `workflow_concurrency` config sections**
  (`src/jk_standards/config.py`): `workflow_dir` and `extensions` for both,
  plus `global_locks` and `ref_tokens` for the latter. A non-list
  `global_locks`, or a non-string entry within it, raises a config error
  surfaced as exit 2 rather than coercing `[5]` into a lock nobody wrote.
- **Self-host wiring**: all three checks registered in `CHECKS`/`STATIC_CHECKS`
  (`src/jk_standards/checks/__init__.py`), invoked explicitly by the `dogfood`
  CI job (`.github/workflows/ci.yml`) and `scripts/verify.sh`, shipped as
  pre-commit hooks (`.pre-commit-hooks.yaml`) and dogfooded through
  `.pre-commit-config.local.yaml`, configured against this repo in
  `jk-standards.yaml`, and documented in `docs/checks.md`,
  `site/src/content/docs/reference/checks.mdx`, both configuration references,
  and the `ARCHITECTURE.md` invariant table. `MIGRATION-nfr-review.md` carries
  the config-only adoption note for `import-cycle`.

### Changed

- Package version bumped to `0.8.0` in the two source-of-truth files
  (`pyproject.toml` and `src/jk_standards/__init__.py`); the deterministic
  `site/src/generated/*.json` fixtures were regenerated to embed the new
  `toolkit_version` (with `checks.json` gaining the three new checks and
  `config-schema.json` their config fields), `site/src/generated/coverage.json`
  was refreshed from a full run, and RELEASE.md pins moved to `v0.8.0`.

### Fixed

- **`deploy-site.yml` smoke concurrency scoping**
  (`.github/workflows/deploy-site.yml`): the workflow grouped every caller as
  `pages-deploy-${{ inputs.deploy }}`, so all build-only smokes — repo-wide, on
  every ref — shared a single `pages-deploy-false` lock. Because
  `cancel-in-progress: false` makes GitHub cancel the older *pending* entry once
  a third contender queues, any moment with more than two PR runs in flight
  cancelled a smoke and failed `ci-complete` on pull requests that contained no
  defect. A build-only smoke holds no shared resource: `upload-pages-artifact`
  and both the `deploy` and `verify-live` jobs are gated on `inputs.deploy`,
  leaving checkout, `npm ci`, prebuild, and build. Real deploys keep the single
  repo-wide `pages-deploy-true` lock they need; smokes are now scoped per-ref
  and per-`working-directory`, the latter separating the two smoke callers that
  share one CI run (`site` and the Node-only `tests/fixtures/deploy-site`
  fixture). The caller-naming alternative, `github.job`, is unavailable here —
  the runner sets it only inside job steps, not in workflow-level
  `concurrency`, whereas `inputs` resolves.

## [0.7.0] - 2026-07-30

### Added

- **`research-provenance` skill**
  (`skills/research-provenance/SKILL.md`): the discipline for documentation
  that summarises external research, scholarship, or practitioner knowledge —
  every substantive claim is one of three visible classes (sourced claim with
  inline citation, practical distillation flagged in the page's Attribution
  note, or project-specific value declared as the project's own), bibliography
  entries carry stable HTML anchors and are never renumbered, provenance is
  declared at both the bibliography and per-page level, terminology credits
  its coiner, organising frameworks are declared as arrangement rather than
  discovery, and cultural material claims fidelity to cited scholarship only
  ("idiom-aware", never "authentic"). Extracted from the crediting pass on
  Poly's Theory Deep Dives section (JimAKennedy/poly PR #159), the reference
  implementation. Indexed in `docs/skills.md` and projected into
  `site/src/generated/skills.json`.
- **`research-provenance` check**
  (`src/jk_standards/checks/research_provenance.py`): the mechanical gate for
  the skill's checkable subset — every citation link resolves to a defined
  `id="..."` anchor in the configured bibliography, bibliography ids are
  unique, and pages opted in via `provenance: research` front-matter carry a
  provenance sentence matching the configured phrase plus an
  `**Attribution:**` note. Skipped when no bibliography is configured
  (incremental adoption), archived docs exempt, with a
  `# provenance-ok: <reason>` two-line-window escape hatch for links that
  legitimately point outside the project's bibliography. Registered in the
  `CHECKS` registry, exposed as the `research-provenance` CLI subcommand and
  pre-commit hook (`.pre-commit-hooks.yaml`), documented in `docs/checks.md`
  and the site checks reference, and covered by fixture-repo tests in
  `tests/test_checks.py`.
- **`research_provenance` config section** (`src/jk_standards/config.py`):
  four new `Config` fields — `provenance_bib_file` (opts the check in),
  `provenance_anchor_pattern`, `provenance_phrase`, and
  `provenance_doc_roots` (defaulting to the top-level `doc_roots`) — read
  from a `research_provenance:` YAML section and documented in
  `docs/configuration.md` and the site configuration reference.

### Changed

- **`frontmatter.read_field`** (`src/jk_standards/frontmatter.py`): the
  front-matter reader now exposes a generic top-level scalar field reader;
  `read_class` delegates to it, and the `research-provenance` check uses it
  to read the `provenance:` marker.
- **ARCHITECTURE.md invariant table**: added the research-provenance row so
  the new mechanism lands with its stated invariant, per the architecture
  standard's bidirectional rule.
- Package version bumped to `0.7.0` in the two source-of-truth files
  (`pyproject.toml` and `src/jk_standards/__init__.py`); the deterministic
  `site/src/generated/*.json` fixtures were regenerated to embed the new
  `toolkit_version` (with `config-schema.json` also carrying the four new
  `provenance_*` fields), and RELEASE.md pins moved to `v0.7.0`.

## [0.6.0] - 2026-07-30

### Added

- **Per-module documentation-coverage baseline ratchet**
  (`src/jk_standards/checks/doc_coverage.py`): the `doc-coverage` check now
  recomputes each module's live documented-unit ratio on every run and hard-fails
  any module whose ratio drops below its committed floor, emitting an
  `::error file=<module>,line=1` annotation naming the module and its before/after
  ratio. The ratchet composes with — it does not replace — the existing binary
  fully-undocumented-module gate, and both counts are reported on one summary line.
- **`--update-baseline` / `--allow-regression` CLI flags**
  (`src/jk_standards/cli.py`): `jk-standards doc-coverage --update-baseline`
  records (and ratchets up) the per-module floor map into a committed fixture,
  dispatched before the generic check path so a plain `doc-coverage` run stays
  read-only. Lowering an existing floor is refused all-or-nothing unless
  `--allow-regression` is also passed; `--allow-regression` without
  `--update-baseline` is a usage error (exit 2).
- **Committed per-module floor map** (`baselines/doc-coverage.json`): the repo's
  own documentation-coverage floor, produced exclusively by the writer (never
  hand-authored) and deliberately excluded from `emit.EMITTERS` and the
  `jk-standards.yaml` `generated:` list so `jk-standards emit all` leaves it
  byte-identical and the ratchet cannot self-heal.
- **`doc_coverage.module_min_percent` opt-in advisory floor**
  (`src/jk_standards/config.py`, `src/jk_standards/checks/doc_coverage.py`): an
  int-valued (0–100, default off) config field that emits a counted,
  warning-only `::warning file=<module>,line=1` annotation for each module below
  the target and appends an `; advisory: N module(s) below P% floor` clause to
  the summary line. The advisory never changes the exit code on its own; an
  out-of-range, bool, or non-int value surfaces as an exit-2 config error.
- **Reference docs for the ratchet and advisory**
  (`docs/checks.md`, `docs/configuration.md`, and their drift-mapped
  `site/src/content/docs/reference/checks.mdx` and
  `site/src/content/docs/reference/configuration.mdx` pairs): document the
  baseline ratchet, the `--update-baseline` / `--allow-regression` flags (as
  check flags, not `emit` verbs), and the `module_min_percent` advisory field.

### Changed

- Package version bumped to `0.6.0` in the two source-of-truth files
  (`pyproject.toml` and `src/jk_standards/__init__.py`); the
  `site/src/generated/*.json` fixtures were regenerated to embed the new
  `toolkit_version` (with `config-schema.json` also carrying the new
  `doc_coverage_module_min_percent` field), and RELEASE.md pins plus the README
  Status block moved to `v0.6.0`.
## [0.5.0] - 2026-07-27

### Added

- **`realtime-audio-safety` skill**
  (`skills/realtime-audio-safety/SKILL.md`): the toolkit's first native-code
  authoring discipline — teaches how to keep the audio callback thread
  real-time-safe (no heap allocation, locks, blocking syscalls, exceptions, or
  unbounded container growth), documents the `check-realtime-safety.sh` recipe
  and the `RT-SAFE-OK: <reason>` escape hatch, and names RealtimeSanitizer as
  the dynamic backstop. Indexed in `docs/skills.md` and projected into
  `site/src/generated/skills.json`.
- **`check-realtime-safety.sh` scanner**
  (`skills/realtime-audio-safety/check-realtime-safety.sh`): a shipped
  grep-gate that flags forbidden real-time-thread operations in audio-callback
  code with `file:line` reporting and an in-band `RT-SAFE-OK: <reason>` waiver
  whose live suppression count is surfaced on every run — the shell analog of
  the `boundaries` check.
- **Subprocess-driven RT-safety test + fixtures**
  (`tests/test_realtime_safety.py`,
  `tests/fixtures/realtime-audio-safety/violating_callback.cpp`,
  `tests/fixtures/realtime-audio-safety/waived_callback.cpp`): proves the
  scanner flags a violating audio callback (exit 1) and passes an
  `RT-SAFE-OK`-waived one (exit 0).
- **`versioned-state-serialization` skill**
  (`skills/versioned-state-serialization/SKILL.md`): a prose-only native-code
  authoring discipline for serialized state that outlives its writer — write a
  format-version tag first, branch on it when reading so new builds still load
  old data, and never reinterpret unversioned bytes — illustrated with JUCE/VST3
  plugin preset/patch state and the "preset compatibility time bomb"
  anti-pattern. Indexed in `docs/skills.md`.
- **`determinism-testing` skill**
  (`skills/determinism-testing/SKILL.md`): a native-code discipline for making
  DSP output reproducible so golden tests catch regressions — the identical
  `(patch, seed, transport)` → byte-identical output contract, deriving
  oscillator/LFO phase from absolute transport time rather than per-block
  accumulation, and wiring a checked-in golden/snapshot suite into CI as a
  required gate. Indexed in `docs/skills.md` and projected into
  `site/src/generated/skills.json`.
- **`cpp-language-standard` convention**
  (`conventions/cpp-language-standard.md`): the toolkit's first gated C++
  *standard* — a normative, RFC-2119 specification that fixes the single ISO C++
  language revision a consuming repository targets, the per-target selection
  mechanism, and the extensions-off discipline that keeps a build from silently
  outrunning its declared revision.
- **`msvc-portability` convention**
  (`conventions/msvc-portability.md`): the gated MSVC sibling standard — the
  RFC-2119 discipline that keeps C++ which compiles cleanly under Clang and GCC
  from silently failing or miscompiling under the Microsoft Visual C++
  toolchain, so a repository that claims Windows support actually builds there.
- **`warning-flags` convention**
  (`conventions/warning-flags.md`): the third gated native-code standard — the
  RFC-2119 compiler-warning discipline a repository holds its C++ to: which
  diagnostics are enabled, that they are fatal, that the set is identical across
  toolchains, and how a warning is suppressed on the rare occasion it is
  warranted.
- **`jk_warnings.cmake` reference implementation**
  (`cmake/jk_warnings.cmake`): the shared, named warning set the
  `warning-flags` standard describes, encoded as CMake — `jk_target_warnings`
  applies the strict warnings-as-errors set (`-Wall -Wextra` + high-value extras
  on Clang/GCC, `/W4` on MSVC, `-Werror`/`/WX` on both) to a first-party target
  and `jk_suppress_sdk_warnings` isolates a third-party target from it. Gated
  code: a `.github/docs-drift-map.yml` entry pairs it to
  `conventions/warning-flags.md` so the module and its standard must evolve
  together.
- **Governed `conventions/` doc root** (`jk-standards.yaml`): the new
  `conventions/` directory registered as a `doc_root` so its `class: gated`
  standards are actually swept by `doc-taxonomy`, `status-prose`, and
  `count-drift` rather than gated only cosmetically.

### Changed

- Package version bumped to `0.5.0` in the two source-of-truth files
  (`pyproject.toml` and `src/jk_standards/__init__.py`); the
  `site/src/generated/*.json` fixtures were regenerated to embed the new
  `toolkit_version`, and RELEASE.md pins plus the README Status block moved to
  `v0.5.0`.

## [0.4.0] - 2026-07-27

### Added

- **`architecture-standard.md` standard**
  (`docs/architecture-standard.md`): the toolkit's first normative gated
  standard — it defines the ARCHITECTURE.md contract (every stated invariant
  must link to a check or CI job that enforces it, and vice versa) that the
  `boundaries` check and drift map hold projects to.
- **`architecture-definition` skill**
  (`skills/architecture-definition/SKILL.md`): teaches the standard's
  bidirectional invariant↔mechanism rule for authoring or reviewing an
  ARCHITECTURE.md; indexed in `docs/skills.md` and projected into
  `site/src/generated/skills.json`.
- **`boundaries` check** (`src/jk_standards/checks/boundaries.py`): a grep-level
  check that flags forbidden cross-directory references with `file:line`
  reporting and a `# boundary-ok: <reason>` escape hatch whose live suppression
  count is surfaced. Wired into the `CHECKS` registry, `config.py`, the check
  docs (`docs/checks.md`, `docs/configuration.md`), and the site fixtures
  (`site/src/content/docs/reference/checks.mdx`).
- **Root `ARCHITECTURE.md` dogfood exemplar** (`ARCHITECTURE.md`): the toolkit's
  own architecture doc, with every invariant linked to an enforcing check or CI
  job. Wired through `jk-standards.yaml` (`taxonomy.extra_files`, two
  grep-enforced boundary rules) and a `.github/docs-drift-map.yml` entry so the
  file drifts loudly under CI.
- **`boundaries` poly-parity acceptance fixtures**
  (`tests/test_checks.py`): seven poly-derived boundary fixtures proving the
  `boundaries` check generalizes past this repo's own dogfood, plus explicit
  auditable `jk-standards boundaries` invocations in `scripts/verify.sh` and
  `.github/workflows/ci.yml`.
- **`deploy-site.yml` reusable workflow**
  (`.github/workflows/deploy-site.yml`): the repo's Astro/Starlight site
  build-and-deploy, converted from a self-triggered repo-specific workflow into
  a single parameterized `workflow_call` producer. It exposes a caller-supplied
  `prebuild` command plus optional `working-directory`, `node-version`,
  `python-version` (empty skips the Python leg), `python-install`, `verify`, and
  version-source inputs, and a `deploy` boolean that gates the deploy +
  verify-live jobs so a caller can run build-only. One parameterized workflow
  covers both a Python prebuild (this repo's `jk-standards emit all`) and a
  Node-only prebuild (`python-version: ""`) — the research fallback of splitting
  into two named variants was **not** needed.
- **`publish-site.yml` caller** (`.github/workflows/publish-site.yml`): this
  repo's own site publish, re-expressed as a thin `push`/`workflow_dispatch`
  caller of `deploy-site.yml` that holds the `pages`/`id-token` grants and the
  Pages concurrency lock — the same producer/consumer split the repo already
  uses for `doc-discipline` / `pre-commit` / `sanitizer-nightly`.
- **`deploy-site` fixture and smoke callers**: a Node-only scratch
  Astro/Starlight fixture (`tests/fixtures/deploy-site/`) whose `.mjs` prebuild
  emits `rules.json` and builds with no Python leg, a `node --test` structural
  contract over both workflow YAMLs and the fixture
  (`tests/fixtures/deploy-site.contract.test.mjs`), and two build-only
  (`deploy: false`) smoke callers wired into `.github/workflows/ci.yml`
  (`deploy-site-smoke`, `deploy-site-fixture-smoke`) that dogfood the reusable
  shape before a tag ships.
- **`secrets-scan.yml` reusable workflow**
  (`.github/workflows/secrets-scan.yml`): the inline gitleaks secrets-scan job
  extracted into a callable `workflow_call` workflow (full-history
  `fetch-depth: 0` scan); `.github/workflows/ci.yml` now consumes it via `uses:`
  instead of carrying the steps inline.
- **`secrets-scan` pre-commit hook** (`.pre-commit-hooks.yaml`): a region-wrapped
  gitleaks `secrets-scan` hook entry mirroring gitleaks' canonical upstream
  hook, so consumers block hardcoded secrets in staged changes locally; the
  README "Reusable CI workflows" prose now documents `secrets-scan.yml`.

### Changed

- Package version bumped to `0.4.0` in the two source-of-truth files
  (`pyproject.toml` and `src/jk_standards/__init__.py`); the four
  `site/src/generated/*.json` fixtures were regenerated to embed the new
  `toolkit_version`, and RELEASE.md pins plus the README Status block moved to
  `v0.4.0`.

## [0.3.0] - 2026-07-27

### Added

- **`sanitizer-nightly` reusable workflow**
  (`.github/workflows/sanitizer-nightly.yml`): a callable GitHub Actions
  workflow that runs an ASan smoke leg plus UBSan and TSan core jobs and three
  toggle-gated integration-surface legs as separate mutually-exclusive jobs,
  with an `if: always()` notify job that drives a single label-deduped
  `sanitizer-failure` issue (open-or-update on any red leg, close on all-green).
  Consumers schedule it from a pinned tag; the repo dogfoods it through a
  shape-only smoke caller wired into `.github/workflows/ci.yml`.
- **`ci-hygiene` skill** (`skills/ci-hygiene/SKILL.md`): captures the generic,
  language-agnostic CI-structure discipline — layered cost-ordered gates,
  SHA-pinned actions on a weekly dependabot cadence, a single aggregation gate
  for branch protection, and artifact-retention conventions — so projects adopt
  the structure without the native-sanitizer specifics.
- **`branch-discipline` skill** (`skills/branch-discipline/SKILL.md`): documents
  the one-branch-per-milestone workflow — never stacking the next milestone on
  an unmerged one and re-running the full pre-commit suite after every rebase —
  for use when starting, rebasing, or landing a milestone branch.

### Changed

- **`sanitizer-ci-setup` skill** (`skills/sanitizer-ci-setup/SKILL.md`):
  narrowed to the native-code sanitizer and fuzzing layer (sanitizer matrices,
  sanitizer-aware tests, fuzzing, notification path), delegating the generic
  CI-structure discipline it previously carried to the new `ci-hygiene` skill.
- Package version bumped to `0.3.0` in the two source-of-truth files
  (`pyproject.toml` and `src/jk_standards/__init__.py`).

## [0.2.0] - 2026-07-27

### Added

- **`action-pinning` check** (`src/jk_standards/checks/action_pinning.py`):
  fails when a GitHub Actions `uses:` reference is pinned to a tag or branch
  instead of a full-length commit SHA, closing a supply-chain gap in consumer
  workflows.
- **`snippet-regions` check** (`src/jk_standards/checks/snippet_regions.py`):
  verifies every `<CodeSnippet file=… region=… />` reference in the docs
  resolves to a real `region:<name>` marker in the named source file, so the
  site never renders a dangling snippet.
- **`install-skills` subcommand** (`src/jk_standards/skills_install.py`):
  installs and hash-verifies third-party skills from `skills-lock.json` and,
  with `--update-lock`, pins `jkStandardsVersion` to the installed toolkit
  version. Ships inside the package so consumers no longer vendor an installer
  script.
- **`pre-commit.yml` reusable workflow**
  (`.github/workflows/pre-commit.yml`): a callable GitHub Actions workflow that
  runs the jk-standards gates, so consumers adopt the checks by referencing the
  workflow at a pinned tag instead of copying steps.
- **nfr-review adoption path** (`MIGRATION-nfr-review.md`): maps nfr-review's
  portable lint surface onto the toolkit's checks and records the follow-up to
  delete its local `lint_docs.py`.
- **`emit` subcommand** (`src/jk_standards/emit.py`): projects the site's
  generated JSON fixtures (`checks`, `config-schema`, `skills`, `coverage`)
  from Python source; `emit all --check` gates the tracked fixtures against
  drift.

### Changed

- Package version bumped to `0.2.0` in the two source-of-truth sites
  (`pyproject.toml` and `src/jk_standards/__init__.py`); README adoption pins
  and Status prose now reference the `v0.2.0` tag.

### Removed

- **`scripts/install_skills.py` compatibility shim**: superseded by the
  packaged `jk-standards install-skills` subcommand. Consumers should install
  skills through the CLI (see `MIGRATION-poly.md`).

## [0.1.0] - 2026-07-25

### Added

- Initial release: the documentation-discipline check suite
  (`doc-taxonomy`, `status-prose`, `file-line-refs`, `count-drift`,
  `behavioral-claims`, `generated-freshness`, `doc-drift`), the `jk-standards`
  CLI, the self-hosting `jk-standards.yaml` config, and the dogfood CI job.

[0.6.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.6.0
[0.5.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.5.0
[0.4.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.4.0
[0.3.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.3.0
[0.2.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.2.0
[0.1.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.1.0
