---
description: Show the state of a delivery ledger — what is done, what is next, and where the ledger and the tree disagree
argument-hint: "[ledger-path]"
allowed-tools: Read, Glob, Grep, Bash
---

Render the current state of a delivery programme. **This command reads. It never
writes** — not the ledger, not a plan, not a file in the tree. Anything that
would change state is reported as something for the user to run, never done.

## 1. Locate the ledger

If an argument was given, use it. Otherwise glob `docs/plans/*/ledger.md`
(or the roots named under `ledger:` in `jk-standards.yaml`).

- No ledger → say so, name where one would live, and stop.
- More than one → list them with their milestone counts and ask which. Do not
  guess.

## 2. Check that it is well-formed

Run `jk-standards ledger` and report the result before anything else. A ledger
that fails its own check is not a trustworthy state report, so say plainly that
the state below may be wrong, and list the violations first.

## 3. Read the state

From the ledger itself:

- **Milestones** — ID, title, status, branch.
- **Slices** — ID, title, status, dependencies, plan, validation tokens.
- **Rows** — counted per slice by status.

## 4. Reconcile with the tree

The ledger is the state; **the tree is the arbiter**. Where they disagree, the
tree wins and you say so — never reconcile silently, and never edit the ledger
to match.

Check, and report any mismatch as drift:

- **Branch.** Does the current milestone's `Branch` exist? Is it checked out?
  Has it been merged already? (`git branch --list`, `git log --oneline -1`)
- **Commits.** For each slice past `open`, are there commits carrying its
  trailer? `git log --grep="Slice: <ID>" --oneline`
- **Plans.** Does each named `Plan` exist, and how many of its `- [ ]` steps
  are checked?
- **Evidence.** Does each `done` slice's evidence file exist, and does its most
  recent entry name a commit that is on the branch?
- **Uncommitted work.** `git status --short` — work in the tree that no slice
  has claimed is drift worth naming.

## 5. Report

Lead with the answer to "what happens next", then the detail:

```
Programme: <title>  (docs/plans/<slug>/ledger.md)
Ledger check: pass | N violations

M001 Theory Corrections   in-progress   milestone/M001-theory-corrections
  S01 Harness             done          4/4 rows
  S05 Chapter 2 hedges    open          0/2 rows      ← next
  S06 Attribution care    open          blocked by S05

Next: M001/S05 — no plan yet. Run /jk:plan to write one.
Drift: evidence/M001-S01.md names commit a1b2c3d, which is not on this branch.
```

Rules for the report:

- **Next** is the first slice whose status is `open` or `in-progress` and whose
  `Depends` are all `done` or `accepted`. If several qualify, name the
  lowest-numbered and say the others are also ready.
- If the next slice has no `Plan`, the next action is to plan it; if it has one
  with unchecked steps, the next action is to execute it; if every slice is
  `done`, the next action is to ship or close the milestone.
- **Drift is never omitted for brevity.** A clean report ends with `Drift:
  none`, so the absence of a drift line is never ambiguous.
- Keep it to what fits on a screen. Detail per row only when asked, or when a
  row is what the drift concerns.
