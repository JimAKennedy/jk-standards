# jk-standards

[Docs · jkstandards.jk.digital](https://jkstandards.jk.digital)

Reusable engineering-discipline toolkit: documentation anti-drift checks, pre-commit
hooks, reusable CI workflows, and agent skills — extracted from
[poly](https://github.com/JimAKennedy/poly) and designed to be adopted by arbitrary
projects with a few lines of configuration.

## Why

Well-run projects accumulate discipline mechanisms — doc-drift gates, sanitizer
matrices, escape hatches that demand written reasons — but they stay trapped in the
repo that invented them. This repo extracts those mechanisms into a versioned,
consumable standard so every project (mine or yours) can exhibit the same discipline
without re-deriving it.

The design principle throughout: **every check is simple (regex/diff-level), every
escape hatch is in-band, greppable, and carries a written reason.** Sophistication
lives in the system design, not the analysis techniques — which is what makes the
whole thing portable.

## What lives here

### 1. Documentation anti-drift toolkit (`checks/`)

A typed lifecycle for documentation, machine-enforced:

| Check | Rule |
|---|---|
| doc-taxonomy | Every doc declares `class: generated \| gated \| archived` front-matter; each class carries different invariants |
| doc-drift | A declarative map pairs source globs with the docs that describe them; a PR touching mapped sources must touch the doc, or carry a `Docs-Not-Affected: <reason>` git trailer |
| doc-completeness | Every doc is either mapped by a drift rule or explicitly declared un-driftable with a recorded reason, so an unmapped doc is a documented exemption rather than an accidental omission |
| doc-coverage | Every module has at least one public unit reached by a docstring, drift-map glob, or doc mention, so no code is wholly undescribed; a per-module baseline ratchets the percentage and an optional advisory floor warns without failing |
| generated-freshness | Generated docs must diff clean against a fresh run of their generator |
| behavioral-claims | Prose claims marked `[verified: Suite.Test]` must cite a test that actually exists (checked against a scraped test index); `[⚠ unverified]` markers are counted as an honest-state metric |
| status-prose | Gated docs may not contain progress-tracking prose; `Status:` lines require a `(YYYY-MM-DD)` anchor |
| file-line-refs | Enduring docs and source comments cite symbols/regions, never `foo.cpp:429` — line numbers rot |
| count-drift | Inventory facts ("N presets", "N chapters") live in one generated JSON and are interpolated, never restated |
| action-pinning | Every GitHub Actions `uses:` is pinned to a 40-char commit SHA; a floating ref (`@v6`, `@main`) is flagged with `file:line`, with a `# action-pin-ok: <reason>` escape hatch and local `./` refs accepted |
| snippet-regions | Docs referencing a code region — MDX `<CodeSnippet region=…>` or prose `region:<name>` — must point at a real `region:<name>` marker in the source tree; a dangling reference is flagged with `file:line`, with a `# snippet-region-ok: <reason>` escape hatch and per-file-type marker syntax |
| research-provenance | Docs summarising published research make provenance mechanically visible: citation links resolve to stable `id="…"` anchors in the bibliography (never duplicated, never renumbered), and pages opted in via `provenance: research` front-matter carry a provenance sentence plus an `**Attribution:**` note, with a `# provenance-ok: <reason>` escape hatch |

The same registry ships engineering-discipline checks whose subject is the code
and the CI graph rather than the prose:

| Check | Rule |
|---|---|
| boundaries | Directed layering rules are grep-enforced: files under a `from` directory must not match a `forbid` regex naming a component they may not reference, with a `# boundary-ok: <reason>` escape hatch whose live use is counted |
| import-cycle | The module-level import graph of each configured package is acyclic; every strongly-connected component of more than one module is reported at `file:line` with its member chain, with a `# import-cycle-ok: <reason>` escape hatch. `TYPE_CHECKING`-guarded imports are not runtime edges |
| workflow-permissions | A job calling a local reusable workflow must grant every scope that callee declares, at workflow *and* job level — otherwise the run fails to compose before any job starts, as a `startup_failure` carrying no annotation |
| workflow-concurrency | Every `concurrency:` group is either ref-scoped or named as a deliberate repo-wide lock; an unscoped group silently serialises the whole repository, so unrelated pull requests cancel each other's jobs |
| release-pins | Every `## [X.Y.Z]` changelog heading has a matching tag, and every adoption pin naming this repo resolves — so documented install instructions cannot rot into dangling refs |

### 2. Pre-commit hooks (`.pre-commit-hooks.yaml`)

The checks above published as [pre-commit](https://pre-commit.com) hooks, consumable
via a standard `repo:` entry pinned to a release tag.

### 3. Reusable CI workflows (`.github/workflows/`)

Five `workflow_call` workflows ship today. `doc-discipline.yml` wraps the doc
anti-drift checks for PR gating in a consuming repo; `pre-commit.yml` runs
`pre-commit run --all-files` against the caller's checkout so a repo gates on its
hooks with a two-line caller (an optional `local-config` input runs a second,
self-referential config a repo cannot load from pre-commit.ci); `sanitizer-nightly.yml`
runs an ASan/UBSan/TSan matrix (with optional integration-surface legs) on a
consumer's schedule and drives a single, label-deduped `sanitizer-failure` issue
— open-or-update on any red leg, close on all-green — the executable form of the
`sanitizer-ci-setup` skill's recipe; `deploy-site.yml` builds and deploys an
Astro/Starlight site to GitHub Pages, exposing a caller-supplied `prebuild`
command plus optional toolchain/verify inputs and a `deploy` boolean (build-only
when `false`), so one parameterized workflow covers both a Python prebuild (this
repo's `jk-standards emit all`) and a Node-only prebuild (`python-version: ""`);
`secrets-scan.yml` runs a full-history gitleaks scan (`fetch-depth: 0`) as a
dedicated job a caller gates on with a two-line `uses:`, the same job this repo's
own `ci.yml` consumes and that `.pre-commit-hooks.yaml` also exposes as a local
`secrets-scan` hook. Baseline-ratcheted scanning is the remaining recipe not yet shipped; until then
the skills document that recipe so it can be wired by hand. This repo consumes
`deploy-site.yml` from its own `publish-site.yml` caller, the same
producer/consumer split it uses for the other reusable workflows.

### 4. Agent skills (`skills/`)

Authoring-time discipline for AI coding agents — the conventions the checks enforce,
taught at write time:

- **branch-discipline** — one branch per milestone, never stack milestones (the
  squash-merge conflict-replay rationale), re-run `pre-commit run --all-files` after every rebase
- **ci-hygiene** — layered cost-ordered gates, SHA-pinned actions on a dependabot
  cadence, a single aggregation gate for branch protection, artifact-retention conventions
- **doc-anti-drift** — classify every doc, date every status claim, cite symbols not
  line numbers, mark behavioral claims, maintain the drift map
- **escape-hatch-discipline** — every suppression in-band, greppable, and reasoned
- **realtime-audio-safety** — keep the audio callback thread real-time-safe (no heap
  allocation, locks, blocking syscalls, exceptions, or unbounded growth), gated by the
  greppable `check-realtime-safety.sh` scanner with an `RT-SAFE-OK` waiver, RealtimeSanitizer as the dynamic backstop
- **sanitizer-ci-setup** — the nightly ASan/UBSan/TSan matrix + fuzzer wiring recipe
- **versioned-state-serialization** — serialize persistent state so old data still loads
  after a format change: write a version tag first, branch on it when reading, never
  reinterpret unversioned bytes (the "preset compatibility time bomb" anti-pattern)

A consuming repo vendors these skills through a `skills-lock.json` and the
`install-skills` CLI subcommand rather than copying files by hand:

```bash
pip install jk-standards
jk-standards install-skills --dest .agents/skills   # install missing skills
jk-standards install-skills --check                 # verify hashes match the lock
jk-standards install-skills --update-lock           # repin hashes + toolkit version
```

`install-skills` downloads each skill listed in `skills-lock.json` from its
source repo, verifies the SKILL.md sha256 against the lock, and writes them
under `--dest` (default `.agents/skills`; use `.claude/skills` for Claude
Code). `--check` reports MISSING vs HASH MISMATCH per skill (exit 1 on drift);
`--update-lock` refreshes the recorded hashes and pins the producing
`jkStandardsVersion` into the lockfile so consumers know which toolkit version
generated it.

### Companion: detection rules in nfr-review

[nfr-review](https://github.com/JimAKennedy/nfr-review) gains hygiene rules that
*detect* whether a target repo has this discipline wired up. This repo *enforces*
it; nfr-review *reports* on it. Clean producer/consumer split — the two version
independently.

## Adoption model

```yaml
# .pre-commit-config.yaml in a consuming repo
- repo: https://github.com/JimAKennedy/jk-standards
  rev: v0.9.0
  hooks:
    - id: doc-taxonomy
    - id: status-prose
    - id: file-line-refs
```

```yaml
# .github/workflows/docs.yml in a consuming repo
jobs:
  doc-discipline:
    uses: JimAKennedy/jk-standards/.github/workflows/doc-discipline.yml@v0.9.0
```

```yaml
# .github/workflows/pre-commit.yml in a consuming repo
jobs:
  pre-commit:
    uses: JimAKennedy/jk-standards/.github/workflows/pre-commit.yml@v0.9.0
```

One config file (`jk-standards.yaml`) supplies the project-specific surface: doc
roots, class vocabulary, drift-map path, count trigger nouns, test-index sources.

## Development

`jk-standards all` runs only the doc-conformance checks (the CI `dogfood` job).
To reproduce the full CI conformance gate locally, run the verify script from
anywhere in the tree:

```bash
scripts/verify.sh              # full local gate: ruff, pytest, 80% coverage floor,
                               # dogfood checks, doc-drift, emit --check, build+twine, site
scripts/verify.sh --no-site    # skip the Node/site-build step
scripts/verify.sh --base REF   # diff doc-drift against REF (default: main)
```

It runs every CI job that can run on a laptop, in CI order, and prints one
pass/fail summary (exit 1 if any step fails). Two CI jobs are CI-only and are
reported as skipped: `secrets-scan` (gitleaks needs full history + a token) and
`reusable-workflow-smoke` (it smoke-tests the reusable workflow's shape in
Actions). Assumes dev deps are installed (`pip install -e ".[dev]"`).

`make check` is the shorthand for `scripts/verify.sh` (and `make check-fast`
for `--no-site`).

## Status

v0.6.0: hardens the `doc-coverage` check with a per-module baseline ratchet — each
module's live documented-unit ratio is recomputed on every run and hard-fails if it
drops below its committed floor in `baselines/doc-coverage.json`, composing with (not
replacing) the existing fully-undocumented-module gate. New `--update-baseline` /
`--allow-regression` flags maintain that floor map, whose write path is deliberately
excluded from `emit all` so the ratchet cannot self-heal; lowering a floor is refused
all-or-nothing unless `--allow-regression` is also passed. An opt-in
`doc_coverage.module_min_percent` advisory emits warning-only annotations for modules
below a target percent without ever changing the exit code on its own.

v0.5.0: opens the toolkit's native-code authoring layer — three C++/DSP skills plus
a gated conventions doc set indexed on the site. `realtime-audio-safety` keeps the
audio callback thread real-time-safe and is gated by the shipped
`check-realtime-safety.sh` scanner, a greppable grep-gate honoring an in-band
`RT-SAFE-OK: <reason>` waiver with a live suppression count, proven by a
subprocess-driven pytest against violating and waived C++ audio-callback fixtures,
with RealtimeSanitizer named as the dynamic backstop. `versioned-state-serialization`
teaches serializing persistent state so old data still loads after a format change
(version tag first, branch on it when reading — the "preset compatibility time bomb"
anti-pattern). `determinism-testing` teaches making DSP output reproducible so golden
tests catch regressions — deriving oscillator/LFO phase from absolute transport time
and gating byte-identical renders in CI. Underpinning the skills, a `conventions/`
doc set — `cpp-language-standard`, `msvc-portability`, and `warning-flags`, each
`class: gated` — codifies the C++ standard baseline, the MSVC portability rules, and
the shared warning set shipped as `cmake/jk_warnings.cmake`.

v0.4.0: introduces the `architecture-standard` — the toolkit's first normative
gated standard, defining the `ARCHITECTURE.md` invariant↔mechanism contract
(every stated invariant links to a check or CI job that enforces it, and vice
versa) — enforced by the new `boundaries` check and taught by the
`architecture-definition` skill. It also lands the reusable `deploy-site.yml`
and `secrets-scan.yml` workflows (the latter with a companion `secrets-scan`
pre-commit hook) and a dogfooded root `ARCHITECTURE.md` exemplar.

v0.3.0: adds the `sanitizer-nightly.yml` reusable workflow — an ASan/UBSan/TSan
matrix driving a single deduped `sanitizer-failure` issue — and the `ci-hygiene` and
`branch-discipline` authoring skills, bringing the toolkit to three reusable workflows
and five skills.

v0.2.0: the doc anti-drift and CI-hygiene checks are implemented (extracted from
poly, where the originals run in production CI), with pre-commit hooks, two reusable
workflows, the first three skills plus the `install-skills` CLI, and a pytest suite.
v0.2 adds the action-pinning and snippet-regions checks, the `install-skills`
subcommand for vendoring skills via `skills-lock.json`, the reusable `pre-commit.yml`
workflow, and the companion detection rules in nfr-review. This repo dogfoods its own machinery: its
docs carry class front-matter, its drift map couples the check sources to
`docs/checks.md`, and its behavioral claims cite its own tests — see the `dogfood`
CI job. `MIGRATION-poly.md` records the changes poly needs to consume this repo
and adopt the skills-lock mechanism; `MIGRATION-nfr-review.md` records how
nfr-review retires its vendored `scripts/lint_docs.py` by mapping its
portable doc checks onto count-drift and snippet-regions.

## License

[Apache-2.0](LICENSE)
