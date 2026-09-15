---
class: plan
---

# Plan M001/S02 — The commands

Status: current (2026-09-15)

**Slice:** M001/S02 — The commands, in
`docs/plans/openspec-split/ledger.md`

**Task status**

- [x] Task 1 — assess and auto: input modes, materialization, notice
- [x] Task 2 — plan, ship, close, commands.md, changelog, R9 verification

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

**Validation**

- `format` → `pre-commit run --all-files`
- `discipline` → `jk-standards all`
- `gate` → `scripts/verify.sh`

All prose in both tasks phrases the mechanism generically ("a structured
spec document named by the ledger's `Source:`, which may carry its own
task checklist") with OpenSpec as the named worked example, per the
proposal's design stance. OpenSpec specifics come only from the decisions
file's fetched-and-cited facts — never from memory.

## Task 1 — assess and auto

Consumes: the standard's `## Source` section from S01 (cite it, do not
restate it). Produces: the two-mode assess and the auto notice.

1. Edit `commands/assess.md`:
   - In section 1 ("Read both sides"), add the spec-directory mode: when
     the argument is a structured spec change directory (worked example:
     `openspec/changes/<id>/`), the input document is the proposal, the
     design doc, and the spec deltas; the change's own task checklist
     (`tasks.md` for OpenSpec) is excluded from row extraction because it
     is the mirror-to-be. "Every input item becomes exactly one row" maps
     to one row per requirement/scenario in the deltas and per discrete
     proposal item, each carrying a source-section column naming what it
     traces to.
   - Add the proposal mode: when the argument is a free-form document and
     the repo has the spec system available (for OpenSpec: an `openspec/`
     directory from `openspec init`), first materialize the change from
     the proposal following the spec system's own creation workflow (for
     OpenSpec: the conventions `/opsx:propose` scaffolds — proposal.md,
     specs/ deltas, design.md), validate it with the spec system's tooling
     where it provides validation, then assess that change. Write its
     task checklist (`tasks.md`) only after the slice decomposition is
     agreed, as the unticked mirror of the agreed slices — it is born a
     mirror, never an independent tracker.
   - Add the absent case: when the input is a free-form proposal and the
     spec system is not available, print the install guidance — for
     OpenSpec: `npm install -g @fission-ai/openspec@latest` then
     `openspec init` (per the OpenSpec README, 2026-09-15) — note that
     the user may re-run assess with a change directory later, and
     proceed as a plain assess. Non-blocking.
   - In section 6 ("Write it"), add: the ledger's `**Source:**` names the
     spec change directory as a repo-relative path (the ledger check
     verifies it resolves), and state the boundary rule with a pointer to
     the ledger standard's Source section: rows cite requirements and
     scenarios by name; the ledger never restates spec content.
2. Edit `commands/auto.md`, section 1 (Orient): one addition — when the
   ledger's `Source:` names a spec change directory and the spec system's
   CLI is absent, say so with the same install pointer and continue; the
   loop itself never needs the CLI.
3. Self-check the prose: generic contract phrasing with OpenSpec as
   example; no invented commands (only the decisions-file facts); no
   contradiction with the untouched sections.
4. Run `format` and `discipline` (`doc-drift` will flag the
   `docs/commands.md` pair until Task 2 lands it — expected inside one PR
   range; run `jk-standards all` and confirm the only findings are the
   commands.md pairing, or none if run without a base).
5. Append evidence to `evidence/M001-S02.md`, tick this task's box, run
   `.venv/bin/jk-standards ledger`, commit as one unit with trailers
   `Slice: M001/S02`, `Rows: R1,R2,R11`.

Check that closes the task: `format` (`pre-commit run --all-files`
exit 0).

## Task 2 — plan, ship, close, commands.md, changelog, R9

Consumes: Task 1's assess/auto prose and S01's standard section.
Produces: the rest of the loop honoring the mirror, and the synced index.

1. Edit `commands/plan.md`, section 4 ("Write the plan"): when the
   ledger's `Source:` names a structured spec document, the plan links
   the requirements its slice implements by name and must not paraphrase
   them; the Definition of Done verbatim-copy rule is untouched.
2. Edit `commands/ship.md`, section 3 (docs-sync): one owed doc added —
   when the ledger's `Source:` document carries its own task checklist,
   tick each box the ledger proves done, in this same docs-sync commit;
   boxes the ledger cannot prove stay unticked and are reported. Section
   5 (body): the PR body links the source spec change.
3. Edit `commands/close.md`, section 3 (verify): confirm the mirror
   checklist reflects exactly what the ledger proves — a ticked box the
   ledger cannot prove is a finding at any close; an unticked box for
   proven work is a finding only when this close ends the source
   change's final milestone. Section 6 (handoff): at the final
   milestone's close, name the spec system's archival step as the user's
   next action — for OpenSpec, `/opsx:archive` (current docs) or
   `openspec archive <id>` (earlier CLI form) — close never runs it.
4. Sync `docs/commands.md`: update the rows for assess, plan, ship,
   close, and auto to reflect the new behavior, in the file's existing
   style.
5. R9 verification: re-read the `superpowers:*` references in
   `commands/assess.md`, `commands/plan.md`, `commands/next.md`; confirm
   none of the new prose changes their meaning or placement; record the
   confirmation (or the small fix) in evidence.
6. Changelog: add the milestone's entry under `## [Unreleased]` (the
   section exists since skill-evals M001), in the file's style.
7. Run every validation token — `format`, `discipline`, `gate` — plus
   the two range-scoped arms against main:
   `jk-standards doc-drift --root . --base main` and
   `jk-standards status-prose --root . --base main`. Refresh any gated
   doc's `Status:` anchor the accuracy arm names.
8. Append evidence, tick this task's box, tick the slice DoD boxes, set
   rows R1–R5, R8–R11 and the slice `done` (O-rows are already
   `accepted`), set milestone M001 `done`, run
   `.venv/bin/jk-standards ledger`, commit as one unit with trailers
   `Slice: M001/S02`, `Rows: R3,R4,R5,R8,R9,R10`.

Check that closes the task: `gate` (`scripts/verify.sh` exit 0).
