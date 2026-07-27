# Changelog

All notable changes to jk-standards are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.4.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.4.0
[0.3.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.3.0
[0.2.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.2.0
[0.1.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.1.0
