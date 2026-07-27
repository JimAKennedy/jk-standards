# Changelog

All notable changes to jk-standards are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[0.3.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.3.0
[0.2.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.2.0
[0.1.0]: https://github.com/JimAKennedy/jk-standards/releases/tag/v0.1.0
