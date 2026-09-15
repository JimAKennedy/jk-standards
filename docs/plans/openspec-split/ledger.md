---
class: gated
---

# OpenSpec Split Ledger

Status: current (2026-09-15)

**Source:** PROPOSAL-openspec-split.md (repo root, 2026-09-15), refined at
assess time with three adopted decisions recorded under
"Decisions adopted at assess" below. Every R/O item is exactly one row; the
proposal file is research and may be deleted now that this ledger is the
plan of record.

## Milestone M001 — Spec-system split

**Vision:** A consuming repo runs the jk delivery loop against an external
spec system with a clean ownership split — the spec owns the *what*, the
ledger owns the *how and proof* — and the spec's own task checklist is a
mirror the loop keeps true, from its creation at assess to its verification
at close.
**Branch:** milestone/M001-openspec-split
**Status:** planned

### Slice M001/S01 — The contract

**Plan:** M001-S01-plan.md
**Validation:** format, unit, emit-fresh, discipline, gate
**Evidence:** evidence/M001-S01.md
**Status:** in-progress

**Definition of Done**

- [ ] `docs/ledger-standard.md` specifies `Source:` as an optional
      ledger-level bold key and states the ownership split, the mirror
      rule, and the granularity contract (one change → one ledger;
      milestone is the landing unit; a partially ticked mirror is expected
      mid-programme; archival is handed off at the final milestone's close)
- [ ] The `ledger` check verifies a repo-relative-path `Source:` resolves
      and leaves prose `Source:` untouched, with tests covering both —
      including a prose-with-filename case mirroring the skill-evals
      ledger's Source line, whose named proposal file no longer exists and
      must not flag
- [ ] The `checks/**` drift pairs (`docs/checks.md`, README tables,
      `reference/checks.mdx`) are satisfied for the check change

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R6 | Formalize `Source:`: optional bold key naming the input document or spec change; when it names a structured spec, the standard states the ownership split, the mirror rule, and the granularity contract adopted at assess | `docs/ledger-standard.md` | the standard's new section; `status-prose`/`doc-taxonomy` green over the edit | `open` |
| R7 | `ledger` check: a `Source:` value that is a bare repo-relative path must resolve; prose values (the current examples) are not paths and are not checked; no inspection of mirror-checklist formats. Cost named up front: `checks/**` edits drag the checks.md/README/mdx drift pairs | `src/jk_standards/checks/ledger.py`, `tests/test_ledger.py` | pytest cases for resolving path, dangling path, and prose-with-filename leniency in `tests/test_ledger.py` | `open` |

### Slice M001/S02 — The commands

**Depends:** M001/S01
**Plan:** M001-S02-plan.md
**Validation:** format, discipline, gate
**Evidence:** evidence/M001-S02.md
**Status:** in-progress

**Definition of Done**

- [ ] `commands/assess.md` carries both input modes: a spec change
      directory is consumed with `tasks.md` excluded from row extraction;
      a free-form proposal, when the repo has OpenSpec available, is first
      materialized into a validated OpenSpec change whose `tasks.md` is
      written as the unticked mirror of the agreed slices — and when
      OpenSpec is absent, verified install guidance is printed and the
      assess proceeds plain
- [ ] `commands/assess.md` states the boundary rule and records `Source:`
      naming the spec change directory
- [ ] `commands/plan.md` requires plans to cite spec requirements by name,
      never paraphrase them
- [ ] `commands/ship.md`'s docs-sync ticks the mirror checklist exactly as
      far as the ledger proves, reports unprovable boxes, and links the
      spec change in the PR body
- [ ] `commands/close.md` verifies the mirror (an unprovable tick is a
      finding at any close; a short mirror is a finding only at the final
      milestone's close) and names the spec system's archival step as the
      user's next action at the final close only
- [ ] `commands/auto.md`'s orient step prints the availability notice when
      the ledger's `Source:` names a spec change directory and the CLI is
      absent — non-blocking
- [ ] `docs/commands.md` reflects all changed commands
- [ ] The changelog carries the milestone's entry

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R1 | Assess input modes: spec-directory mode (rows from deltas and proposal items, one row per requirement/scenario with a source-section column; `tasks.md` excluded as mirror-to-be) and proposal mode (materialize + validate the OpenSpec change when available, then assess it; `tasks.md` born as the unticked mirror of the agreed slices) | `commands/assess.md` | command prose carries both modes; `doc-drift` forces the `docs/commands.md` pair | `open` |
| R2 | Assess records provenance (`Source:` names the change directory) and states the boundary rule so ledgers cite requirements rather than restate them | `commands/assess.md` | boundary-rule prose present; exercised by the next spec-directory assess | `open` |
| R3 | Plans cite the spec requirements their slice implements and never paraphrase them; DoD verbatim-copy rule untouched | `commands/plan.md` | prose addition in the "Write the plan" section | `open` |
| R4 | Ship docs-sync ticks the mirror exactly as far as the ledger proves, in the same commit as the changelog entry; unprovable boxes stay unticked and are reported; PR body links the change | `commands/ship.md` | docs-sync and PR-body sections carry the mirror rule | `open` |
| R5 | Close verifies the mirror per the granularity contract and hands off `openspec archive <id>` as the user's next action at the final milestone's close; close still commits nothing | `commands/close.md` | verify and handoff sections carry the contract | `open` |
| R8 | `docs/commands.md` rows for assess, plan, ship, close, and auto synced with R1–R5 and R11 | `docs/commands.md` | `doc-drift` mapping `commands/**` → `docs/commands.md` green on the PR | `open` |
| R9 | Superpowers interplay verified unchanged: the existing `superpowers:*` references in assess, plan, and next are orthogonal to the split. Deliverable is confirmation during implementation, or the small fix if wrong | `commands/assess.md`, `commands/plan.md`, `commands/next.md` | verification recorded in evidence | `open` |
| R10 | Changelog entry lands with ship's docs-sync; release tag and adoption-pin bump follow `RELEASE.md` post-merge so consumers can bump `jkStandardsVersion` and re-run `jk-standards install-commands` | `CHANGELOG.md`, release process | changelog entry in the ship commit; tag is the user's post-merge step per `RELEASE.md` | `open` |
| R11 | OpenSpec-availability notice, relevance-gated and non-blocking: assess's proposal mode prints verified install guidance when OpenSpec is absent; auto's orient step prints it when the ledger's `Source:` names a spec change directory and the CLI is absent. Install command verified from OpenSpec's documentation at implementation time, never guessed | `commands/assess.md`, `commands/auto.md` | notice prose in both commands; guidance text cites its source | `open` |
| O1 | No `Spec:` commit trailer — `Slice:`/`Rows:` plus the ledger's `Source:` already give a two-hop join; a third trailer is derivable ceremony | — | recorded as a deliberate non-goal | `accepted` |
| O2 | No mirror-checklist enforcement in the `ledger` check — close reports it as a finding; Python enforcement would couple the check to foreign file formats. Revisit only if the finding proves chronic | — | recorded as a deliberate non-goal | `accepted` |
| O3 | No changes to `next.md` or `status.md` — they compose the rules above (R9 verifies the composition holds). Amended at assess: `auto.md` is no longer exempt; it gains exactly the R11 notice and nothing else | — | recorded as a deliberate non-goal, amendment noted | `accepted` |
| O4 | The jk commands do not drive OpenSpec's archival — close only names `openspec archive <id>` as the user's next step. Amended at assess: change *creation* moved in scope (R1's proposal mode materializes the change so the spec step cannot be forgotten); archival stays out | — | recorded as a deliberate non-goal, amendment noted | `accepted` |

## Sequencing

- **M001/S01 → M001/S02:** the command prose cites the standard's new
  `Source:` section as the contract it executes; writing the prose first
  would invent the contract in five places.

## Decisions adopted at assess

- **Granularity contract:** one OpenSpec change maps to one ledger,
  defaulting to one milestone; a large change may decompose into multiple
  milestones within its ledger. The milestone is the landing unit for the
  mirror sync; a partially ticked mirror after an intermediate ship is
  expected, not a finding; archival is handed off at the final milestone's
  close.
- **Assess feeds the spec system:** given a free-form proposal in a repo
  with OpenSpec available, assess materializes and validates the change
  before assessing it, so the spec step cannot be forgotten (O4 amended:
  creation in scope, archival out).
- **R11 scoping:** relevance-gated and non-blocking, in assess's proposal
  mode and auto's orient step only (O3 amended: auto gains exactly this).
