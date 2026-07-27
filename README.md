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
| doc-drift-map | A declarative map pairs source globs with the docs that describe them; a PR touching mapped sources must touch the doc, or carry a `Docs-Not-Affected: <reason>` git trailer |
| generated-freshness | Generated docs must diff clean against a fresh run of their generator |
| behavioral-claims | Prose claims marked `[verified: Suite.Test]` must cite a test that actually exists (checked against a scraped test index); `[⚠ unverified]` markers are counted as an honest-state metric |
| status-prose | Gated docs may not contain progress-tracking prose; `Status:` lines require a `(YYYY-MM-DD)` anchor |
| file-line-refs | Enduring docs and source comments cite symbols/regions, never `foo.cpp:429` — line numbers rot |
| count-drift | Inventory facts ("N presets", "N chapters") live in one generated JSON and are interpolated, never restated |
| action-pinning | Every GitHub Actions `uses:` is pinned to a 40-char commit SHA; a floating ref (`@v6`, `@main`) is flagged with `file:line`, with a `# action-pin-ok: <reason>` escape hatch and local `./` refs accepted |
| snippet-regions | Docs referencing a code region — MDX `<CodeSnippet region=…>` or prose `region:<name>` — must point at a real `region:<name>` marker in the source tree; a dangling reference is flagged with `file:line`, with a `# snippet-region-ok: <reason>` escape hatch and per-file-type marker syntax |

### 2. Pre-commit hooks (`.pre-commit-hooks.yaml`)

The checks above published as [pre-commit](https://pre-commit.com) hooks, consumable
via a standard `repo:` entry pinned to a release tag.

### 3. Reusable CI workflows (`.github/workflows/`)

Three `workflow_call` workflows ship today. `doc-discipline.yml` wraps the doc
anti-drift checks for PR gating in a consuming repo; `pre-commit.yml` runs
`pre-commit run --all-files` against the caller's checkout so a repo gates on its
hooks with a two-line caller (an optional `local-config` input runs a second,
self-referential config a repo cannot load from pre-commit.ci); `sanitizer-nightly.yml`
runs an ASan/UBSan/TSan matrix (with optional integration-surface legs) on a
consumer's schedule and drives a single, label-deduped `sanitizer-failure` issue
— open-or-update on any red leg, close on all-green — the executable form of the
`sanitizer-ci-setup` skill's recipe. Baseline-ratcheted scanning is the remaining
recipe not yet shipped; until then the skills document that recipe so it can be
wired by hand.

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
- **sanitizer-ci-setup** — the nightly ASan/UBSan/TSan matrix + fuzzer wiring recipe

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
  rev: v0.2.0
  hooks:
    - id: doc-taxonomy
    - id: status-prose
    - id: file-line-refs
```

```yaml
# .github/workflows/docs.yml in a consuming repo
jobs:
  doc-discipline:
    uses: JimAKennedy/jk-standards/.github/workflows/doc-discipline.yml@v0.2.0
```

```yaml
# .github/workflows/pre-commit.yml in a consuming repo
jobs:
  pre-commit:
    uses: JimAKennedy/jk-standards/.github/workflows/pre-commit.yml@v0.2.0
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
