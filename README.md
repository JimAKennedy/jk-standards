# jk-standards

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

### 2. Pre-commit hooks (`.pre-commit-hooks.yaml`)

The checks above published as [pre-commit](https://pre-commit.com) hooks, consumable
via a standard `repo:` entry pinned to a release tag.

### 3. Reusable CI workflows (`.github/workflows/`)

`workflow_call` workflows wrapping the same checks for PR gating, plus recipe
workflows for the wider discipline stack (nightly sanitizer matrix with
issue-dedupe notification, baseline-ratcheted scanning).

### 4. Agent skills (`skills/`)

Authoring-time discipline for AI coding agents — the conventions the checks enforce,
taught at write time:

- **doc-anti-drift** — classify every doc, date every status claim, cite symbols not
  line numbers, mark behavioral claims, maintain the drift map
- **escape-hatch-discipline** — every suppression in-band, greppable, and reasoned
- **sanitizer-ci-setup** — the nightly ASan/UBSan/TSan matrix + fuzzer wiring recipe

### Companion: detection rules in nfr-review

[nfr-review](https://github.com/JimAKennedy/nfr-review) gains hygiene rules that
*detect* whether a target repo has this discipline wired up. This repo *enforces*
it; nfr-review *reports* on it. Clean producer/consumer split — the two version
independently.

## Adoption model

```yaml
# .pre-commit-config.yaml in a consuming repo
- repo: https://github.com/JimAKennedy/jk-standards
  rev: v0.1.0
  hooks:
    - id: doc-taxonomy
    - id: status-prose
    - id: file-line-refs
```

```yaml
# .github/workflows/docs.yml in a consuming repo
jobs:
  doc-discipline:
    uses: JimAKennedy/jk-standards/.github/workflows/doc-discipline.yml@v0.1.0
```

One config file (`jk-standards.yaml`) supplies the project-specific surface: doc
roots, class vocabulary, drift-map path, count trigger nouns, test-index sources.

## Status

Scaffold. The checks are being extracted from poly, where they run in production
CI today. This repo dogfoods its own machinery: its docs carry class front-matter,
its drift map pairs each check with its skill, and its behavioral claims cite its
own tests.

## License

[Apache-2.0](LICENSE)
