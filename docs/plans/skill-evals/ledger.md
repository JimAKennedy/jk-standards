---
class: gated
---

# Skill Evaluation Programme Ledger

Status: current (2026-09-14)

**Source:** PROPOSAL-skill-evals.md (repo root, 2026-09-14). Every R/N item
in that proposal is exactly one row below; the proposal file is research and
may be deleted once this ledger is the plan of record.

## Milestone M001 — Deterministic guardrails

**Vision:** A staged secret cannot enter a local commit, and a malformed or
asset-dangling skill cannot pass CI — with no LLM, no API key, and no new
cost anywhere in the gate.
**Branch:** milestone/M001-deterministic-guardrails
**Status:** done

### Slice M001/S01 — Secret-hygiene preflight

**Plan:** M001-S01-plan.md
**Validation:** format, gate
**Evidence:** evidence/M001-S01.md
**Status:** done

**Definition of Done**

- [x] A staged Anthropic-style key fails a local commit, demonstrated and
      recorded in evidence
- [x] A config the GHA `pre-commit` job runs includes a staged-files
      gitleaks hook and the full suite passes (landed via R0's sanctioned
      fallback: the upstream pinned hook in `.pre-commit-config.yaml`; the
      shipped `secrets-scan` hook cannot build from this non-Go repo)

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R0 | Staged-files gitleaks gate in this repo's own pre-commit setup. Shipped `secrets-scan` hook proved unbuildable under `repo: .` (no Go module, no `additional_dependencies` — defect noted for the report); the recorded fallback landed: upstream pinned hook in the dev config | `.pre-commit-config.yaml` | evidence records the staged `sk-ant-` key rejected (hook exit 1, rule `anthropic-api-key`) and the full suite passing | `done` |

### Slice M001/S02 — skill-lint check

**Plan:** M001-S02-plan.md
**Validation:** format, unit, emit-fresh, discipline, gate
**Evidence:** evidence/M001-S02.md
**Status:** done

**Definition of Done**

- [x] `skill-lint` is registered in `CHECKS` and `STATIC_CHECKS`
- [x] Each violation class — name/dir mismatch, missing trigger phrasing,
      dangling asset, non-executable script — has a pytest case that fails
      without the check and passes with it
- [x] The hook id ships in `.pre-commit-hooks.yaml`
- [x] `docs/checks.md` and the README check tables describe the check
- [x] Regenerated `site/src/generated/checks.json` is committed

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R1 | `skill-lint` check: front-matter `name` matches directory, description carries trigger phrasing, referenced assets exist and scripts are executable. Rescoped: `emit_skills()` already fails on unparseable front-matter, so parseability is not this row's work | `src/jk_standards/checks/` | pytest cases for each violation class in `tests/test_checks.py` | `done` |
| R2 | Registration, hook id, `docs/checks.md`, README tables | `src/jk_standards/checks/__init__.py`, `.pre-commit-hooks.yaml`, `docs/checks.md`, `README.md` | `doc-drift` mapping forces the doc pair; registry covered by pytest | `done` |
| R3 | Emitter fixtures regenerated with the new check | `site/src/generated/checks.json` | `jk-standards emit all --check` exits 0 | `done` |

## Milestone M002 — Eval corpus and harness, locally runnable

**Vision:** Any developer with an API key can score every corpus skill —
compliance with a with/without-skill delta, plus selection — from one make
target, with no Claude Code CLI anywhere in the loop.
**Branch:** milestone/M002-eval-corpus-harness
**Status:** planned

### Slice M002/S01 — Harness end-to-end on one skill

**Depends:** M001/S02
**Validation:** format, unit, eval, gate
**Evidence:** evidence/M002-S01.md
**Status:** open

**Definition of Done**

- [ ] `evals/README.md` documents the corpus format
- [ ] One skill's scenarios run both arms (with/without skill text) and are
      judged by the Anthropic-backed deepeval model with no OpenAI key
      referenced anywhere
- [ ] `region:skill-evals-config` in `jk-standards.yaml` holds agent model
      id, judge model id, run count, and thresholds; every results file
      records them
- [ ] Budget caps (per-case tokens, suite case cap) abort a run that
      exceeds them
- [ ] `make eval` runs the suite given `ANTHROPIC_API_KEY`;
      `scripts/verify.sh`'s documented exclusion list names it
- [ ] Offline harness logic (corpus loading, config, arm construction,
      results serialization) has pytest coverage with the API mocked

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R4 | `evals/` corpus layout: scenario definition plus rubric per case, format documented | `evals/README.md`, `evals/` | offline pytest loads the corpus; format doc exists | `open` |
| R7 | Harness lives outside the shipped package; registry and boundary invariants untouched | `evals/harness/` | `boundaries` and `import-cycle` checks stay green; base package metadata unchanged | `open` |
| R8 | `[eval]` extra with exact deepeval pin (note the documented `evaluate()` API break at deepeval 1.0) plus `anthropic` SDK; base and `[dev]` stay LLM-free | `pyproject.toml` | `pip install -e ".[eval]"` recorded in evidence on the supported interpreter matrix | `open` |
| R9 | Two-arm runs asserting absolute threshold and positive with-skill delta | `evals/harness/` | deepeval metric config; offline pytest covers arm construction | `open` |
| R10 | Judge is a deepeval custom model on the Anthropic API, provider swappable | `evals/harness/` | offline pytest with mocked API; evidence records a grep showing no OpenAI key reference | `open` |
| R11 | Non-determinism controls: fixed run count, median scoring, per-case thresholds, flaky marking; config in `region:skill-evals-config`; results files record model ids | `jk-standards.yaml`, `evals/harness/` | offline pytest asserts results schema carries model ids, run count, thresholds | `open` |
| R12 | Budget guards: per-case token caps, suite case cap, printed cost/usage summary | `evals/harness/` | offline pytest: capped run aborts; summary present in a recorded live run | `open` |
| R13 | `make eval` target; verify.sh exclusion list updated | `Makefile`, `scripts/verify.sh` | target documented; exclusion list names the eval job | `open` |
| R19 | `eval` validation token declared with a cost warning; token added with this ledger, command resolves when the make target lands | `.jk/validations.yml`, `Makefile` | `jk-standards ledger` passes citing the token; `make eval` exists and matches the mapping | `open` |
| N1 | No Claude Code CLI runner and no `claude plugin eval` integration this iteration — plugin eval probed 2026-09-14 on CLI 2.1.236, still early-access per-org; corpus format kept portable to it | — | recorded here as a deliberate non-goal | `accepted` |

### Slice M002/S02 — Corpus breadth and selection eval

**Depends:** M002/S01
**Validation:** format, eval
**Evidence:** evidence/M002-S02.md
**Status:** open

**Definition of Done**

- [ ] At least two scenarios each for `versioned-state-serialization`,
      `realtime-audio-safety`, and `doc-anti-drift`
- [ ] Selection eval covers every corpus skill and includes a
      no-skill-applies negative case
- [ ] A recorded run passes at the configured thresholds

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R5 | Initial corpus: the three named skills, at least two scenarios each; remaining skills are follow-on corpus work | `evals/` | recorded passing eval run in evidence | `open` |
| R6 | Skill-selection eval from the generated inventory, exact-match scored, with a negative case | `evals/` | recorded selection run: exact-match results in evidence | `open` |
| N3 | No evaluation of the `commands/` prompts yet — they orchestrate tools and multi-turn flows a direct-API harness cannot exercise honestly; deferred, not forgotten | — | recorded here as a deliberate non-goal | `accepted` |

## Milestone M003 — CI, release gate, and drift cadence

**Vision:** No release ships unevaluated skills, and a model update that
degrades them surfaces within a week with no diff in this repo.
**Branch:** milestone/M003-ci-release-drift
**Status:** planned

### Slice M003/S01 — Reusable workflow and ci.yml wiring

**Depends:** M002/S02
**Validation:** format, discipline, gate
**Evidence:** evidence/M003-S01.md
**Status:** open

**Definition of Done**

- [ ] `.github/workflows/skill-evals.yml` exists as a `workflow_call`
      reusable, SHA-pinned, permission-ceiling compliant
- [ ] The ci.yml `skill-evals` job passes through as success on a PR
      touching no eval-relevant paths, and does real work on one that does
- [ ] `ci-complete` names the job in both the `needs` list and the shell
      comparison
- [ ] A run without the secret on eval-relevant changes fails with the
      documented message

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R14 | Reusable `skill-evals.yml`: installs `.[eval]`, runs the suite, uploads results artifact with bounded retention | `.github/workflows/skill-evals.yml` | `action-pinning`, `workflow-permissions`, `workflow-concurrency` checks green | `open` |
| R15 | ci.yml job with change-detection pass-through, registered in `ci-complete` twice | `.github/workflows/ci.yml` | unrelated-paths PR run shows pass-through; `ci-complete` diff shows both registrations | `open` |
| R16 | `ANTHROPIC_API_KEY` repository secret; missing-secret path fails loudly with guidance | GitHub repo settings, `.github/workflows/skill-evals.yml` | failure-mode run link recorded in evidence; secret creation is a maintainer action outside the tree | `open` |
| N5 | No per-PR full-suite run on unrelated changes — the R15 path filter is the mechanism, so this non-goal is enforced by construction | — | pass-through behaviour verified under R15 | `accepted` |

### Slice M003/S02 — Release gate and governed doc

**Depends:** M003/S01
**Validation:** format, discipline, eval, gate
**Evidence:** evidence/M003-S02.md
**Status:** open

**Definition of Done**

- [ ] The tag-path `verify` job runs the full corpus (agreed: full, not a
      smoke subset, at current corpus size)
- [ ] `docs/skill-evals.md` exists with taxonomy front-matter and passes
      the doc checks
- [ ] The drift map pairs `evals/**` and the harness with that doc
- [ ] `RELEASE.md`'s pre-tag checklist names `make eval` as the local
      preflight

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R17 | Release gate: tag push runs the full eval suite; flaky-failure recovery is re-running the workflow job, never re-tagging | `.github/workflows/release.yml` | first post-landing tag's run recorded in evidence | `open` |
| R20 | Governed doc: corpus format, adding a scenario, thresholds, reading a failure, cost model | `docs/skill-evals.md` | `doc-taxonomy`, `status-prose`, `count-drift` checks green over the new doc | `open` |
| R21 | Drift-map mapping for corpus and harness changes | `.github/docs-drift-map.yml` | `doc-drift` check enforces the pair on a touching PR | `open` |
| R22 | RELEASE.md pre-tag checklist gains the eval preflight | `RELEASE.md` | checklist line present; referenced target exists | `open` |
| N4 | No committed score snapshot or ratchet baseline — CI runs evals directly; scores are artifacts, thresholds are config. The committed-receipt model was considered and set aside with the CLI-based design | — | recorded here as a deliberate non-goal | `accepted` |

### Slice M003/S03 — Weekly drift schedule

**Depends:** M003/S01
**Validation:** format, discipline
**Evidence:** evidence/M003-S03.md
**Status:** open

**Definition of Done**

- [ ] The reusable workflow carries `schedule` (weekly) and
      `workflow_dispatch` triggers on main
- [ ] One dispatched run on main completes and uploads its results artifact

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R18 | Weekly model-drift run: unchanged corpus re-scored on current models, failures surfacing as a failed scheduled run, notification posture matching `sanitizer-nightly` | `.github/workflows/skill-evals.yml` | dispatched-run link and artifact recorded in evidence | `open` |
| N2 | No Confident AI cloud account — results stay CI artifacts and local files; hosted baseline features out of scope | — | recorded here as a deliberate non-goal | `accepted` |

## Sequencing

- **M001/S02 → M002/S01:** the harness reads the corpus the lint check
  guarantees is well-formed; building atop unlinted skills would re-derive
  the same validation ad hoc.
- **M002/S01 → M002/S02:** corpus breadth is authored against the proven
  pipeline; scenarios written before the harness settles would be rewritten.
- **M002/S02 → M003/S01:** CI wiring with nothing complete to run would gate
  on an empty suite.
- **M003/S01 → M003/S02 and M003/S03:** the release gate and the schedule
  both invoke the reusable workflow S01 creates.
- M001/S01 has no dependencies and lands first: every later branch assumes
  an API key is in daily local use.

## Configuration defaults (agreed at assess time)

- Agent-under-test and judge model ids both default to `claude-sonnet-5`;
  both live in `region:skill-evals-config` and are recorded in every
  results file, so either can change without ambiguity about what produced
  a score.
- Initial thresholds are generous with deepeval flaky marks, time-boxed:
  ratchet after two releases' score distributions have been observed.
- The release tag path runs the full corpus; revisit only if corpus growth
  makes that slow or costly.
