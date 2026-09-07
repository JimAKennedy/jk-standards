# Changelog

All notable changes to jk-standards are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed

- **`sdlc-retro` skill carries the standing-report contract**
  (`skills/sdlc-retro/SKILL.md`, `retro/README.md`, `docs/skills.md`): the
  skill specified collection and interpretation but not what the output is,
  so a run improvised its own report shape. It now defines the update
  contract — one standing report at a stable location, updated in place,
  answering *what happened / major moves / quantified benefits*, with an
  incremental procedure (add the period, extend the timeline only on an era
  transition, refresh only what the period made stale, keep the framing
  rules) — and reads a **report brief** from the snapshot ledger's README
  (audience, framing rules, exclusions, baseline constants, era numbering),
  which `retro/README.md` now records for this portfolio.
- **Snapshot ledger privacy** (`.gitignore`, `retro/README.md`,
  `skills/sdlc-retro/SKILL.md`, `commands/sdlc-retro.md`): snapshots carry
  private telemetry (local filesystem paths, environment manifests, per-repo
  activity), so `retro/snapshots/` is now gitignored in this public repo and
  the tracked baseline snapshot is removed going forward (it remains in git
  history). The skill and command now treat ledger tracking as the brief's
  call and never commit a snapshot the brief marks untracked.

### Added

- **`sdlc-retro` skill with bundled evidence collector**
  (`skills/sdlc-retro/`, `docs/skills.md`, `retro/`): a method for
  reconstructing and periodically measuring a portfolio's AI-assisted
  workflow evolution from evidence rather than memory. Its stdlib-only
  `collect.py` extracts four evidence classes per repo — Co-authored-by
  trailer variants, tooling-marker first-appearance dates, weekly
  commit/line volumes, and ephemeral environment state — into an
  append-only snapshot ledger with enforced collection windows
  (`--since auto` / `--until`), so incremental monthly runs stay cheap and
  their numbers reconcile with prior runs. Unreadable repo directories
  (e.g. orphaned worktrees) are recorded, never silently skipped. The
  `retro/` directory holds this repo's own snapshot ledger, seeded with a
  full-history baseline.
- **`sdlc-retro` effort-split churn classification** (`skills/sdlc-retro/collect.py`
  schema 3, `skills/sdlc-retro/SKILL.md`, `docs/skills.md`): weekly line
  churn is now also split into product / tests / docs / process-guardrail /
  machine-workflow-state categories, classified by file path with rules
  versioned inside the collector (first match wins, so `CLAUDE.md` counts
  as process, not docs; `.gsd*` state gets its own bucket so tool-generated
  churn cannot masquerade as guardrail effort; rename paths are normalized
  to their new name). Lets the report narrate
  the relative effort that went into guardrail development versus core
  product delivery per repo; the skill records the honesty caveats (churn
  is a proxy, boilerplate skews product-ward, and a falling guardrail share
  can mean guardrails are now imported rather than written).
- **`sdlc-retro` token-usage evidence class** (`skills/sdlc-retro/collect.py`
  schema 2, `skills/sdlc-retro/SKILL.md`, `docs/skills.md`): the collector
  now banks weekly per-model token totals (input, output, cache
  read/creation) harvested from Claude Code session transcripts, attributed
  to repos via transcript directory names (worktree sessions merge into
  their repo; out-of-portfolio directories are kept under their raw names).
  Transcripts are deleted after the Claude Code cleanup period, so this
  class ignores the `--since` window and scans everything still readable on
  every run — retention supplies the left edge, and the skill now warns that
  the run cadence must stay inside the cleanup period. Streamed duplicate
  transcript entries are deduplicated by message + request id.
- **`sdlc-retro` workflow command** (`commands/sdlc-retro.md`,
  `docs/commands.md`): drives one cycle of the periodic retrospective —
  locate the installed skill and its collector (refusing rather than
  improvising one), bank an incremental snapshot, interpret in the skill's
  prescribed order, update the standing report, commit. Installs as
  `/jk:sdlc-retro` alongside the delivery-loop commands.
- **jk-standards bootstrapped onto its own ledger workflow**
  (`.jk/validations.yml`, `.claude/commands/jk`): validation tokens
  mirroring the CI job graph (`format`, `unit`, `emit-fresh`, `discipline`,
  `gate`), and the `/jk:` command namespace wired as a tracked symlink to
  the live `commands/` tree — the source repo dogfoods its own commands
  with zero vendoring drift.

## [0.13.2] - 2026-09-01

### Fixed

- **Vendored skills and commands install from a pinned ref**
  (`src/jk_standards/skills_install.py`, `docs/skills.md`,
  `docs/commands.md`): `install-skills` and `install-commands` fetched
  `refs/heads/main` unconditionally, so `skills-lock.json` recorded hashes of
  whatever upstream held the moment it was written. Any commit to a vendored
  asset then broke `install --check` in every consuming repo at once, on pull
  requests that had touched none of it. Worse, a post-download mismatch
  installed the file anyway and exited 0, so `install` succeeded while the
  `--check` on the next line rejected what it had just written — the shape a
  consumer's CI actually hit. The ref now comes from the lock: an entry's own
  `ref` if it has one, otherwise the tag matching the recorded
  `jkStandardsVersion`, and only a lock predating that field falls back to the
  default branch. A mismatch behind a pin is now a failure, because at an
  immutable ref it can no longer mean "upstream released"; the 404 retry
  across `master`/`HEAD` likewise applies only to the unpinned default, since
  answering a missing tag with a branch returns content the lock never saw.

- **`/jk:close` no longer assumes it can push to the default branch**
  (`commands/close.md`, `docs/commands.md`): section 3 said to set the
  milestone's status "on the default branch" and commit there, which any
  repository with branch protection refuses — and protecting the default branch
  is good practice, so this was the common case rather than an edge one. It now
  probes with `gh api repos/<owner>/<repo>/rules/branches/<default>`, which
  needs no admin rights, and takes a pull-request path when a `pull_request`
  rule is present or the probe is unavailable. It also records that
  `git push --dry-run` is **not** a probe for this: repository rules are
  evaluated on receive, so a dry run reports a clean push for a branch that
  rejects the real one a moment later. The recovery for a commit already made
  on the default branch names the branch before resetting, so the commit is
  never reachable only from the reflog. Section 5 gains the consequence: when
  the close is in review the default branch does not carry it, so the next
  milestone's branch is cut from a ledger that still calls the previous
  milestone `in-progress` and needs a rebase once the close merges — cutting it
  from the unmerged close branch instead would be the stacking that section
  already forbids. Section 6 gains a second handoff shape, because a close
  sitting in review must not be reported as a close.

### Changed

- **Adoption pins moved to `v0.13.0`** (`.pre-commit-hooks.yaml`, the five
  reusable workflow headers, `README.md`, `docs/configuration.md`,
  `site/src/content/docs/{reference/configuration,how-to/adopt-in-a-repo,guide/quickstart}`):
  every documented `rev:` and `uses: …@` reference naming this repository now
  points at the current release. This lands after the tag by necessity rather
  than preference — `release-pins` requires every pin to resolve to a tag that
  exists, so bumping them in the release pull request itself would fail the
  check, since the tag is not pushed until that merges. `MIGRATION-poly.md` and
  `MIGRATION-nfr-review.md` keep their original pins, as the record of what
  those projects actually adopted.

- **`/jk:plan` gains a repair mode** (`commands/plan.md`, `commands/next.md`,
  `docs/commands.md`): `/jk:next` stops and points at `/jk:plan` when a plan is
  malformed or a step is wrong, but `/jk:plan` refused any slice that already
  had a plan — so the two commands contradicted each other in exactly the
  situation that needs them to agree. A new section 2 covers repair as distinct
  from re-planning: change only what execution proved wrong, leave ticked task
  boxes ticked, and re-run the self-review afterwards, because correcting what
  a task expects often leaves an earlier step that never set that expectation
  up. It also warns that a defect found in one task is rarely uniform across
  its siblings — a blanket fix breaks the ones that were already right, which
  is what nearly happened in the trial programme. `/jk:next` now asks the
  executor to name the defect precisely, and to say whether siblings share it,
  so the repair can be scoped rather than guessed.

## [0.13.1] - 2026-08-28

### Fixed

- **`ledger` no longer reports a truthful evidence SHA as fabricated in a
  shallow clone** (`src/jk_standards/gitutil.py`, `tests/test_ledger.py`):
  `commit_exists` probed only whether it was inside a work tree, so in a
  truncated checkout — pre-commit.ci, or any `fetch-depth: 1` CI job — a
  commit recorded from a merge months earlier is legitimately absent, and
  `git cat-file -e` failing was read as evidence of fabrication. It now
  distinguishes the two with `git rev-parse --is-shallow-repository` and
  returns `None` (cannot say) rather than `False` (does not exist), which is
  what the tri-state return existed for. The docstring had claimed this case
  was handled since 0.13.0; the implementation never did, because the test
  covering it built a repository and then ran the check *outside* one instead
  of building a shallow clone. The replacement clones over `file://` — a plain
  local-path clone is optimised into hardlinks and ignores `--depth`, so the
  old-style fixture would have silently proved nothing — and asserts
  `--is-shallow-repository` is `true` before trusting the result. Caught by a
  real consumer's CI on the first pull request that used the check.

## [0.13.0] - 2026-08-28

### Added

- **`ledger`: every commit SHA an evidence file names must resolve**
  (`src/jk_standards/checks/ledger.py`, `src/jk_standards/gitutil.py`,
  `tests/test_ledger.py`, `docs/checks.md`,
  `site/src/content/docs/reference/checks.mdx`): evidence is what separates an
  asserted completion from a demonstrated one, so a SHA that resolves to
  nothing is worse than none at all — unlike a `TBD` it is indistinguishable
  from a real commit and a reader has no reason to doubt it, which also means
  the placeholder scan could never have caught it. `gitutil.commit_exists`
  returns `None` rather than `False` when git cannot answer, so a shallow clone
  or a non-repository skips the SHA instead of reporting a truthful record as
  fabricated — the same distinction `list_tags` draws for a checkout with no
  tags fetched.

### Fixed

- **The evidence template no longer asks for a value that cannot exist**
  (`docs/ledger-standard.md`, `commands/next.md`): the standard's example
  recorded ``commit `a1b2c3d` `` while `/jk:next` requires the evidence file to
  ship *inside* that same commit, so the SHA is unknowable at the moment the
  line is written. A field that cannot be filled truthfully gets filled falsely,
  and this one did — a fabricated SHA reached an evidence file in a consuming
  repo before being caught by hand. Evidence written as work lands now omits the
  SHA and leans on the `Slice:` and `Rows:` trailers, which the standard already
  documents as the join in both directions. Backfilled evidence, whose commit
  predates the file, still names it and now must: the new check above enforces
  the half that is mechanically checkable. The rule is about order, not style —
  name a SHA when the commit already exists, never when it does not.


- **A `##` section after the last slice is no longer folded into it**
  (`src/jk_standards/checks/ledger.py`, `tests/test_ledger.py`,
  `docs/ledger-standard.md`): the parser closed a slice's definition-of-done
  checklist at any heading but left the slice itself open to the end of the
  file, so every pipe table below the last slice — a `## Related issues` table,
  a `## Sequencing` table — was absorbed as that slice's rows and reported as
  rows with an empty `Status`. The author could not act on the message, because
  the table was never a row table. A milestone-level (`##`) heading now ends the
  slice, since it is a sibling section rather than part of one; headings deeper
  than `##` still leave the slice open, so a slice may sub-divide its own body.
  The standard now states the slice's extent rather than leaving it implied.

### Changed

- **The `/jk:plan` → `/jk:next` handoff names where task state lives**
  (`commands/plan.md`, `commands/next.md`): `/jk:next` picks its task from "the
  first unchecked box" and commits "the plan's checkbox", but `/jk:plan` never
  required one — while *also* requiring the slice's definition of done to be
  copied into the plan verbatim, which is itself a `- [ ]` list. Every plan ever
  written therefore pointed `/jk:next` at a definition-of-done item instead of a
  task. `/jk:plan` now mandates a **Task status** checklist above the DoD copy
  and forbids a third checklist; `/jk:next` reads that list by name, and treats
  a plan without one as malformed rather than improvising a repair.

- **`/jk:next` stops instead of guessing when the ledger is not on the default
  branch** (`commands/next.md`, `commands/assess.md`): the instruction to create
  a milestone branch "from the current default branch" assumed the ledger and
  its plans were already there. When `/jk:assess` runs on a feature branch —
  the normal case for an agent — that yields a milestone branch with no ledger
  and no plan on it, so there is nothing to execute against. `/jk:next` now
  enumerates the three branch cases and stops for the user's decision on the
  third, since cutting from the ledger's own commit drags whatever else is
  unmerged into the milestone's review. `/jk:assess` now names the branch its
  ledger landed on and says plainly that the ledger must reach the default
  branch before a milestone branch is cut from it.

- **`/jk:assess` covers programmes that are already part-delivered**
  (`commands/assess.md`): the command assumed a greenfield audit, but the check
  requires a `done` slice to carry a resolving `Plan:`, an evidence file, ticked
  boxes and no open rows — none of which exists retrospectively. A new "Work
  that already landed" section says to backfill one evidence file per landed
  slice from its merge commit and to hatch the `Plan:` line rather than invent a
  plan for finished work, and forbids the tempting shortcut of starting the
  ledger at the current frontier, which would drop closed rows the input
  document still contains. Its reconciliation report also gains a **partly
  satisfied** bucket, for an item whose substance is in the tree but whose
  verification is not — filed as done, the missing lock never gets written;
  filed as outstanding, a later pass rewrites prose that was already correct.


- **Adoption pins moved to `v0.12.0`** (`.pre-commit-hooks.yaml`, the five
  reusable workflow headers, `README.md`, `docs/configuration.md`,
  `site/src/content/docs/{reference/configuration,how-to/adopt-in-a-repo,guide/quickstart}`):
  every documented `rev:` and `uses: …@` reference naming this repository now
  points at the current release. They had been left at `v0.10.0` — two releases
  behind — because the bump can only land after the tag exists, which is the
  gap `RELEASE.md` describes and the reason it is a separate step. `RELEASE.md`
  itself stops naming a version literal when it points at those references: the
  sentence had gone stale the same way, which is the drift the file warns about
  a few lines above. `MIGRATION-poly.md` and `MIGRATION-nfr-review.md` keep
  their original pins, as the record of what those projects actually adopted.

## [0.12.0] - 2026-08-28

### Added

- **`ledger` check + the ledger standard**
  (`src/jk_standards/checks/ledger.py`, `docs/ledger-standard.md`,
  `tests/test_ledger.py`, `docs/checks.md`,
  `site/src/content/docs/reference/checks.mdx`): a delivery ledger is the whole
  state of a programme in one Markdown file — milestones, the slices they
  decompose into, the rows each slice closes, each slice's definition of done,
  and the validation tokens that must pass before it may claim to be done. The
  file is the state and git is the history, so there is nothing to synchronise
  and nothing that a crashed session or a hand-edit can desync. What a file
  cannot do is enforce its own invariants, which is what this check recovers:
  IDs well-formed and unique, a slice nested under the milestone it names,
  statuses from the declared vocabulary, `Depends` resolving inside the same
  ledger, every slice carrying a non-empty definition of done, plan and evidence
  paths staying inside the ledger's own directory, and no placeholder text
  surviving into a commit. A `done` slice must prove it — every box checked, an
  evidence file on disk, every row closed or `accepted` — which is the
  difference between an asserted completion and a demonstrated one. Validation
  tokens are named in the ledger and resolved by the consuming repo in
  `.jk/validations.yml`, so the same token means `ctest` in a native project and
  a browser run in a site; an undeclared token fails rather than skipping
  silently, while a repo with no validations file skips the arm and says so. The
  escape hatch is `<!-- ledger-ok: <reason> -->` on the flagged line, and an
  empty hatch suppresses nothing.

- **`install-commands` — workflow commands vendored from the same lock file**
  (`src/jk_standards/skills_install.py`, `src/jk_standards/cli.py`,
  `commands/status.md`, `docs/commands.md`, `docs/configuration.md`): the
  installer that vendors `skills/` now also vendors `commands/` — single
  Markdown files rather than skill directories — from a `commands` block in the
  same `skills-lock.json`, under the same download, hash-verify and
  `--update-lock` discipline. One lock file, one hash discipline, two kinds of
  vendored asset. The default destination is `.claude/commands/jk` rather than
  `.claude/commands`: a project command in a subdirectory is namespaced by it,
  so a vendored command arrives as `/jk:<name>` and never claims a bare name a
  consuming repo may want for itself. The first command shipped is `status`,
  which reads a ledger and reports milestone and slice state, the next
  actionable slice, and any disagreement between the ledger and the working
  tree — read-only, reporting anything that would change state as something for
  the user to run.

- **The workflow command set — `assess`, `plan`, `next`, `ship`, `close`**
  (`commands/`, `docs/commands.md`): the delivery loop the ledger format
  exists to serve. `assess` reconciles a free-form audit or vision document
  against the codebase and refines a ledger with the user section by section,
  turning every input item into exactly one row — including the ones
  deliberately not actioned, which become `accepted` rows rather than silent
  omissions. `plan` classifies one slice, writes an implementation plan beside
  the ledger with the slice's definition of done copied verbatim, and
  self-reviews it for DoD coverage, row coverage and placeholders. `next`
  executes exactly one task and stops: it derives its position by re-reading
  the files rather than remembering it, works test-first, runs the slice's full
  validation set, appends terse evidence, and commits code, plan checkbox,
  ledger row and evidence as one unit under `Plan`/`Slice`/`Rows` trailers — so
  an interrupted session loses nothing and the next invocation resumes from
  disk. `ship` refuses an unfinished milestone, re-runs every validation on the
  current head rather than trusting that it passed when the slice landed, syncs
  the changelog and roadmap before opening the pull request, and generates the
  body from the ledger and `git log --grep` — listing any commit without a
  `Slice:` trailer as untraced work instead of omitting it. `close` verifies
  the merge landed, retires the milestone and its branch, and rebases or
  creates the next milestone's branch on the updated base, refusing to rewrite
  a branch that carries review comments. Each command uses the Superpowers
  skills where they are installed and names the equivalent by hand where they
  are not, so a project without them gets the same discipline.

## [0.11.0] - 2026-08-20

### Added

- **`release.yml` — the tag cuts the GitHub Release**
  (`.github/workflows/release.yml`, `RELEASE.md`): pushing a `v*.*.*` tag now
  publishes the Release instead of leaving it as an unwritten manual step.
  `release-pins` gates the *tag* and nothing gated the *Release*, so `v0.10.0`
  sat tagged with no Release and `v0.1.0`, `v0.3.0`, `v0.5.0` and `v0.6.0` have
  tags and no Release at all — a gap invisible to every existing check. The
  workflow re-proves the tagged tree first (tag, `pyproject.toml` version and
  `__version__` must agree; `CHANGELOG.md` must carry a section for the version;
  lint, tests, `jk-standards all` and `emit all --check` must pass), then builds
  the sdist and wheel and creates the Release with that changelog section as its
  body and the artifacts attached. The tag is immutable by then, so `verify`
  cannot stop a bad tag — it decides whether a Release is published on top of
  one, which is the half that is still worth gating. Publishes to GitHub only:
  no package index, no registry.

- **`doc-completeness` reverse orphan-existence pass**
  (`src/jk_standards/checks/doc_completeness.py`, `tests/test_doc_completeness.py`,
  `docs/checks.md`, `site/src/content/docs/reference/checks.mdx`, issue #57):
  the check now also asserts that every registered doc — each mapping's `doc:`
  target and each `cannot_drift` entry — still exists on disk, naming any
  orphaned entry together with its registry. A stale `cannot_drift` entry
  silently pre-exempts a future doc created at that path, and a stale mapping
  becomes an unsatisfiable gate escapable only by a `Docs-Not-Affected` trailer,
  so the two get distinct remediation. The pass uses plain filesystem existence
  (tolerating entries outside the enumerated `doc_roots`) and runs
  unconditionally, independent of the git fail-open branch. The success summary
  gains a count of how many registry entries were existence-checked, so a green
  run still proves the reverse pass ran.

## [0.10.0] - 2026-08-18

### Added

- **`status-prose` accuracy arm and `status_prose.date_tolerance_days`**
  (`src/jk_standards/checks/status_prose.py`, `src/jk_standards/config.py`,
  `src/jk_standards/cli.py`, `src/jk_standards/gitutil.py`,
  `docs/checks.md`, `site/src/content/docs/reference/checks.mdx`,
  `docs/configuration.md`, `site/src/content/docs/reference/configuration.mdx`,
  issue #52): the presence arm only proved a `Status:` anchor exists; a doc
  could carry a real date that silently predated its own last edit. The new
  diff-scoped accuracy arm flags any gated doc whose `Status:` anchor is older
  than the doc's most recent commit in the base range, so a stale "current
  (YYYY-MM-DD)" cannot survive a content change. It self-skips when no base ref
  is available (mirroring `doc-drift`), and a `Status:`-line-only edit never
  counts as a substantive change. `status_prose.date_tolerance_days` (default
  `0`) widens the window; a non-negative-int guard rejects anything else as a
  config error.
- **`doc_completeness.exempt_classes` config key**
  (`src/jk_standards/checks/doc_completeness.py`, `src/jk_standards/config.py`,
  `docs/checks.md`, `site/src/content/docs/reference/checks.mdx`,
  `docs/configuration.md`, `site/src/content/docs/reference/configuration.mdx`):
  a doc whose front-matter `class` is exempt (default `["archived"]`) is a
  deliberately frozen record, so requiring it to be mapped or declared
  un-driftable was noise. `doc-completeness` now skips exempt-class docs and
  reports the count. The exemption keys off the doc's own front-matter class,
  not `cfg.generated`, so a generated-config doc classed `gated` stays governed.
- **`python -m jk_standards` module entry point**
  (`src/jk_standards/__main__.py`): the console script depends on being on
  `PATH`; the module form runs from any interpreter that can import the package.
  Both dispatch to the same `cli.main`.

### Fixed

- **`iter_docs` swept untracked and git-ignored files into governance**
  (`src/jk_standards/config.py`, `src/jk_standards/gitutil.py`): the doc walk
  enumerated every file under a `doc_root` on disk, so a scratch draft or a
  build artifact an adopter never committed could fail `doc-taxonomy`,
  `status-prose`, or `doc-completeness`. `iter_docs` now filters to
  git-tracked files, and fails open — outside a git work tree, or if `git`
  is unavailable, it falls back to the full on-disk walk rather than hiding
  every doc.
- **`scripts/verify.sh` assumed the active interpreter had the package
  installed** (`scripts/verify.sh`): a harness that spawned the gate under a
  different `python3` (e.g. macOS system Python, with no editable install)
  failed `python -m jk_standards`. The script now prepends `./.venv/bin` to
  `PATH` when a project virtualenv is present, so every bare Python tool
  resolves to the project's installed copy.
- **C++ enumerator's exotic declarator forms were untested, and the coverage
  comment asserted a stale figure** (`tests/test_doc_coverage_cpp.py`,
  `pyproject.toml`, issue #49): the 18 uncovered statements in
  `checks/doc_coverage_cpp.py` were, almost exactly, the destructor / operator /
  qualified-name / pointer-declarator forms `_name_of` exists to normalise plus
  the `_find_function_declarator` parameter-list-skip guard — a regression in any
  of them passed the golden-count `cpp-dogfood` job unseen as long as the total
  held. Added a table-driven test over each declaration form (asserting the
  enumerated unit name, not the aggregate count) plus direct-node tests for the
  defensive guards, lifting the module from 80% to 99%. The `[tool.coverage.report]`
  comment no longer hardcodes a per-module percentage (it still claimed the
  module was 12% and needed tests that already existed); it now names the
  measurement command instead, so it cannot go stale by construction.
- **Missing top-level `permissions:` on two published reusable workflows**
  (`.github/workflows/doc-discipline.yml`, `.github/workflows/pre-commit.yml`):
  both omitted a workflow-level `permissions:` block, so the `GITHUB_TOKEN`
  scope they ran under was whatever the *calling* repository's default granted
  — `write-all` in any repo that never narrowed it. Every other workflow here
  declares one, and `ci.yml`'s own comment already asserted these two need
  "none beyond `contents: read`"; the assertion just was not enforced where it
  mattered. These two are consumed by other people's repositories, which is
  precisely where an inherited default is invisible to the person affected.
  Both now declare `contents: read`, which is the real ceiling: every step
  only reads the checkout.

## [0.9.0] - 2026-08-17

### Fixed

- **`doc-drift` deps-only detection on mid-block hunks**
  (`src/jk_standards/checks/doc_drift.py`, issue #43):
  `is_deps_only_diff()` asked whether every changed line sat inside a
  `dependencies`/`devDependencies` block, tracking membership by brace depth
  across the diff's context lines. A diff is a fragment, so when the hunk
  window opened after the block's `"dependencies": {` line — which is where a
  real Dependabot bump usually lands — membership never became true and the
  bump was rejected. The `deps_only_manifests` exemption therefore failed on
  precisely the case it exists to allow, on every weekly bump, in any repo
  using it. The rule is now the value's shape rather than the line's position:
  a changed line must be a `"name": "value"` entry whose value is version
  shaped (optional range operator, then a digit-led version). Requiring a
  digit keeps the exemption narrower than a plain entry match would — a
  package rename, a `"license"` change, or a single-token script value like
  `"test": "vitest"` are all still taxonomy signals and still trigger.

### Added

- **`release-pins` check** (`src/jk_standards/checks/release_pins.py`): asserts
  that every `## [X.Y.Z]` changelog heading has a matching `vX.Y.Z` tag, and
  that every pin naming this repository — `uses: <repo>/…@<ref>`, a `rev:`
  under a `repo:` line naming it, or the `pip install "git+…@ref"` form —
  resolves to a real tag. Pins belonging to other projects are never judged: a
  `rev:` counts only when the nearest preceding `repo:` line names this
  repository. Only release-shaped refs are checked, so a SHA or branch pin is
  left alone. Skips cleanly when the repository is unconfigured, when tags are
  unreadable, or when none are present — a shallow CI checkout and a project
  before its first release are indistinguishable, and reporting every pin as
  dangling on an incomplete checkout would be worse than silence. Escape
  hatch: `# release-pin-ok: <reason>`.
- **`release_pins` config section** (`src/jk_standards/config.py`): `repo` and
  `repo_url` identify the project, `changelog` and `extensions` scope the scan,
  `exclude` holds path prefixes whose pins are historical records, and
  `untagged_versions` declares releases that shipped without a tag so the check
  ratchets forward; the count is reported on every run. A non-list
  `untagged_versions`, or a non-string entry, raises a config error surfaced as
  exit 2.
- **Release-in-flight exemption** (`src/jk_standards/checks/release_pins.py`):
  the newest changelog section is exempt from the tag rule. A release commit
  dates its section before the tag is pushed, so requiring one there would fail
  the release pull request on a required check — leaving it unmergeable and the
  tag uncuttable, with the check blocking the process it exists to protect. The
  exemption costs one release of detection latency and no more, and is reported
  as `N awaiting its tag` so the pending state stays visible.
- **`gitutil.list_tags`** (`src/jk_standards/gitutil.py`): the tag list, with
  `None` distinguishing "unreadable" from "none present" so a caller can skip
  rather than misreport.
- **Stricter ruff rule set** (`pyproject.toml`): ruff was running its default
  selection (`E4`/`E7`/`E9` + `F` — syntax errors and pyflakes, little more).
  Now selects `E,W,F,I,B,UP,C4,SIM,RET,PTH`, with `E501` ignored under `tests/`
  where fixture literals embed workflow YAML whose shape is the point. The
  eight resulting findings are fixed, one of them a latent Windows bug:
  `skills_install` derived a tar member prefix with `os.path.dirname`, so
  `Path`-style separators would never have matched an archive entry on Windows
  — it now uses `PurePosixPath`, which is what an archive path actually is.
- **Coverage floor raised to 85%** (`pyproject.toml`): measured 88%, and the
  floor's own comment had drifted — it listed the 71/72/79% modules while
  omitting `checks/doc_coverage_cpp.py` at 12%, the weakest by a wide margin.
  The comment now records that gap and why closing it needs unit tests around
  the C++ enumerator rather than a floor change.
- **Python 3.13 in the CI matrix and trove classifiers**
  (`.github/workflows/ci.yml`, `pyproject.toml`): `requires-python = ">=3.11"`
  admitted 3.13 while CI proved only 3.11 and 3.12, so support was a claim
  rather than a fact. The package also carried no `classifiers`.
- **README check tables completed and drift-mapped** (`README.md`,
  `.github/docs-drift-map.yml`): the front-door tables described ten of the
  seventeen registered checks, having stopped being maintained around v0.4.
  They now cover all of them, split into the documentation checks and the
  engineering-discipline checks whose subject is the code and the CI graph.
  `doc-drift` is named as itself rather than `doc-drift-map`. A drift-map entry
  now pairs `src/jk_standards/checks/**` with `README.md`, so the tables cannot
  silently rot again — the gap existed precisely because README was the one
  per-check inventory no mapping covered.
- **Self-host wiring**: registered in `CHECKS`/`STATIC_CHECKS`, invoked by the
  `dogfood` CI job (which already sets `fetch-depth: 0`, so tags are present)
  and `scripts/verify.sh`, shipped as a pre-commit hook, configured in
  `jk-standards.yaml`, and documented in `docs/checks.md`, the site checks
  reference, both configuration references, and the ARCHITECTURE.md invariant
  table.

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
