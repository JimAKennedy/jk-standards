---
class: gated
---

# Architecture

Status: current (2026-07-30)

This document is jk-standards' own architecture document, written to the
[architecture standard](docs/architecture-standard.md) this toolkit publishes.
It exists to prove the standard is followable: the repository that defines the
rule *"no invariant without a mechanism; no mechanism without a stated
invariant"* holds itself to it. Every invariant in the table below names a
concrete check or CI job a reader can run.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as in
RFC 2119.

## Components

The toolkit is a pure-Python package under `src/jk_standards/` plus an Astro
site under `site/`. The parts a reader reasons about in isolation:

- **CLI** (`src/jk_standards/cli.py`) — parses argv, loads config, and
  dispatches to a check, an emitter, or the skills installer.
- **Check registry** (`src/jk_standards/checks/`) — each module exposes
  `run(root, cfg) -> int` returning a violation count; `CHECKS` and
  `STATIC_CHECKS` in `checks/__init__.py` are the registry the CLI and emitters
  read.
- **Config model** (`src/jk_standards/config.py`) — loads `jk-standards.yaml`
  into a `Config` dataclass; every field has a default so an absent config
  still yields a usable one.
- **Emitters** (`src/jk_standards/emit.py`) — project Python truth (the check
  registry, the config schema, the skills catalog) into the site's tracked JSON
  fixtures under `site/src/generated/`.
- **Skills installer** (`src/jk_standards/skills_install.py`) — vendors the
  `skills/` tree into a consuming repository.
- **Test index** (`src/jk_standards/testindex.py`) — enumerates the test suite
  so the `behavioral-claims` check can bind doc claims to real tests.
- **Support modules** — `output.py` (GitHub-Actions annotation formatting),
  `frontmatter.py` (doc class parsing), `gitutil.py` (base-ref resolution and the tag list),
  `workflows.py` (workflow YAML parsed with the line numbers findings are
  reported at).
- **Site** (`site/`) — Astro Starlight docs that consume the generated JSON
  fixtures; nothing under `site/src/generated/` is hand-maintained.

## Boundaries

Dependencies flow one direction: consumers depend on the check registry, and
the check registry depends on nothing above it.

- The **CLI** and the **emitters** MAY import the **check registry** — both read
  `CHECKS`/`STATIC_CHECKS` to dispatch and to project the registry into
  fixtures.
- A **check** MUST NOT import the **CLI**. The CLI depends on checks; a check
  reaching back into the CLI would invert the dependency and create a cycle.
- A **check** MUST NOT import the **emitters**. Emitters depend on the check
  registry to build `checks.json`; a check importing `emit` would close the same
  cycle from the other side.
- The **check registry** MAY import the **config model** and the support
  modules; the config model MUST NOT import checks.

The two `MUST NOT` boundaries above are grep-enforced by the `boundaries` check
(see the invariant table); the rest are described here as the intended shape and
enforced by review against this section.

## Data flow

A check run: the **CLI** reads argv, loads `jk-standards.yaml` through the
**config model**, and selects one or more entries from the **check registry**.
Each selected check walks the working tree, and on a violation calls **output**
to print a `::error file=…,line=…::` GitHub-Actions annotation. The CLI's exit
code is the sum of the checks' returned violation counts: `0` clean, `1`
violations, `2` usage/config error. No check mutates the tree.

A fixture emit: the **emitters** read Python truth — the **check registry** for
`checks.json`, the **config model**'s dataclass fields for
`config-schema.json`, and the `skills/` tree for `skills.json` — and write the
tracked JSON files under `site/src/generated/`. The **site** build consumes
those fixtures at render time. The `emit --check` path re-derives each fixture
and diffs it against the tracked file instead of writing, so a source change
without a regenerated fixture fails CI rather than shipping a stale site.

## Invariants and enforcement

Every property below MUST hold for the architecture to be sound, and each names
the mechanism that enforces it. A row whose enforcement is "review" is not
listed as an invariant — those live in the prose above.

| Invariant | Enforced by |
|-----------|-------------|
| A check module MUST NOT import the CLI | `boundaries` check, rule `checks-no-cli` |
| A check module MUST NOT import the emitters | `boundaries` check, rule `checks-no-emit` |
| Every doc under the doc roots, plus this file, declares a valid lifecycle class | `doc-taxonomy` check |
| Every gated doc's `Status:` line carries a `(YYYY-MM-DD)` date anchor | `status-prose` check |
| Site JSON fixtures stay in sync with their Python generators | `generated-freshness` check / `emit-check` CI job |
| A source change that should update a mapped doc lands with that doc | `doc-drift` check / `doc-discipline` CI job |
| `file:line` references in docs point at a real file and in-range line | `file-line-refs` check |
| Every behavioral claim in a doc traces to a real test | `behavioral-claims` check |
| Inventory counts are not hardcoded as numerals in prose | `count-drift` check |
| Every `<CodeSnippet>` region reference resolves to a real marker | `snippet-regions` check |
| GitHub Actions are pinned to a full commit SHA | `action-pinning` check |
| No Python module is wholly undocumented — every module has a unit reached by a docstring, drift-map glob, or doc mention | `doc-coverage` check |
| Research citations resolve to defined bibliography anchors; research-derived pages declare provenance | `research-provenance` check |
| No configured package gains a module-level import cycle | `import-cycle` check |
| A reusable-workflow caller grants every scope its callee declares | `workflow-permissions` check |
| A concurrency group is ref-scoped or a declared global lock | `workflow-concurrency` check |
| Every released version is tagged, and every pin to this repo resolves | `release-pins` check |
| The test suite passes with coverage at or above the 80% floor | `test` + `coverage` CI jobs |
| The whole conformance gate stays green on this repo | `dogfood` CI job (`jk-standards all`) / `scripts/verify.sh` |

The first seventeen mechanisms are checks in this repository's own `CHECKS`
registry, run together by `jk-standards all` in the `dogfood` CI job and
reproduced locally by `scripts/verify.sh`. The last two are CI jobs defined in
`.github/workflows/ci.yml`. The two `boundaries` rules are configured in
`jk-standards.yaml` under `boundaries.rules`, and a drift-map entry
(`.github/docs-drift-map.yml`) requires a change to the check registry, CLI, or
emitters to land with an update to this file — so the exemplar cannot silently
drift from the code it describes.

## Why gated

This document is `class: gated`: it is the exemplar the architecture standard
points readers to, so it is held to the same dated-`Status` and
progress-free-prose discipline the standard asks of every document it governs.
An exemplar that drifts teaches the wrong lesson. Gating it is the toolkit
gating itself with itself — the governing rule applied to the document that
describes the toolkit.
