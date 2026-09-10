---
description: Drive one milestone end to end — decisions front-loaded, tasks executed in sequence, stopping at a review gate with a full report
argument-hint: "[milestone-id] [ledger-path]"
disable-model-invocation: true
---

Run a whole milestone unattended: plan its slices with every question asked up
front, execute task after task through slice boundaries, and stop at a review
gate with a report of everything that changed and every decision that shaped
it. `/jk:ship` remains a deliberate human act taken after reading that report.

This is the loop `/jk:next` deliberately leaves to the user, made a command.
It **composes** `/jk:plan` and `/jk:next` — their rules all apply unchanged,
and this file adds none that contradict them. State lives in the ledger, the
plans, and git, never in this session: an interrupted run loses nothing, and
re-issuing `/jk:auto` recomputes its position from the files — including after
`/jk:close`, when it finds the next open milestone and starts there.

## 1. Orient — derive the position from the files

1. `jk-standards ledger` must pass. If not, report the violations and stop.
2. **Milestone** — the argument, else the first `in-progress` milestone, else
   the first `planned`/`open` one whose dependencies are satisfied. If none
   remains, the programme is complete: say so, name the ledger, stop.
3. **Already past execution?** Route instead of re-running:
   - Every slice `done`/`accepted` and the milestone's report (section 5)
     exists → the milestone is at the review gate. Say so, point at
     `/jk:ship`, stop.
   - A PR is already open or merged for the branch → point at `/jk:ship` or
     `/jk:close` respectively, and stop.
4. Announce the milestone, its slices and their states, and what this run
   intends to do, before doing any of it.

## 2. Front-load the decisions

Before executing anything, take every human decision the milestone is going to
need — this is what makes the rest of the run safe to leave alone.

For each slice without a `Plan`, do `/jk:plan`'s classification and clarifying
questions **now**, in one batch. An architectural slice still gets its design
written and approved here — front-loading moves `/jk:plan`'s gates earlier, it
never removes them.

Record every question, its answer, and every choice made on the user's behalf
in **`docs/plans/<slug>/<MID>-decisions.md`** — one file per milestone,
append-only, created on first use:

```markdown
## <YYYY-MM-DD> — planning <MID>/<SNN>

- **Q:** <the question as asked> — **A:** <the user's answer>
- **Decision:** <what was chosen> — **Why:** <the reason, one line>
```

A question that only becomes answerable once earlier slices have landed is
recorded here as **deferred**, naming the boundary it waits at. Reaching that
boundary is then a planned pause, not a failure: stop there, ask, record the
answer, continue.

Write the plans for the slices that can be planned now (per `/jk:plan`,
including its self-review), consuming the recorded answers rather than
re-asking. Commit plans, ledger updates, and the decisions file with the
milestone's trailers.

## 3. Execute the loop

Work the milestone forward with `/jk:next` semantics, one task at a time, in
order — with exactly one override: **do not stop at slice boundaries.** The
human decision that boundary exists for was taken in section 2 and is
re-reviewed at the gate in section 5. At each boundary: if the next slice is
unplanned, plan it now from the recorded decisions; if a deferred question
waits there, stop and ask it first.

Everything else in `/jk:next` binds exactly as written: test-first, follow the
plan's steps, one task per commit with trailers, full validation before any
claim, evidence appended, `jk-standards ledger` before each commit.

A judgment call made in flight — an ambiguity the plan left open that is too
small to stop for, resolved in an obviously-right way — is appended to the
decisions file when made. If it is not obviously right, it is a halt, not a
judgment call.

## 4. Halt conditions

Stop, report precisely, and end the run — never guess past — on any of:

- anything `/jk:next` or `/jk:plan` would stop for: a broken ledger, a
  malformed or wrong plan step, a missing branch with the ledger off the
  default branch, a dirty tree with changes no task claims
- a validation failure the current task cannot honestly fix within its own
  scope
- a question section 2 did not anticipate and did not defer
- anything that would widen a slice

The report of a halt names the milestone, slice, task, and the exact thing a
human must decide or fix. After they do, re-issuing `/jk:auto` resumes from
the files.

## 5. The review gate — report, then stop

When every slice is `done` or `accepted`:

1. Write **`docs/plans/<slug>/<MID>-report.md`** — the record the user reviews
   before choosing to ship. It is generated from the ledger, git, and the
   decisions file, not from memory:
   - the milestone's Vision and per-slice table (as `/jk:ship`'s body format)
   - the definition-of-done boxes, all checked
   - the validation table from the slices' evidence
   - **traceability**: one line per commit from `git log --grep="Slice: "`
     over the branch, with untraced commits listed separately, never omitted
   - **decisions**: the contents of `<MID>-decisions.md`, verbatim
2. Commit the report with the milestone's trailers.
3. Present the report's headlines in chat, name anything a reviewer should
   look at twice (untraced commits, deferred decisions, judgment calls), and
   **stop**: the next step is the user reading the report and issuing
   `/jk:ship`. Never run it for them — the gap between this gate and that
   command is where the human review happens.
