---
description: Write the implementation plan for the next open slice in a delivery ledger
argument-hint: "[slice-id] [ledger-path]"
---

Turn one slice of a ledger into an implementation plan an engineer with no
context could follow.

## 1. Pick the slice

With a slice ID argument, use it. Otherwise pick the first slice whose status
is `open` and whose `Depends` are all `done` or `accepted`. Say which you
picked and why, and name any other slice that was equally ready.

Refuse, and say so, if:

- the slice already has a `Plan` and unchecked steps — it is planned; run
  `/jk:next`
- its dependencies are unmet — name the blocking slice
- `jk-standards ledger` fails — fix the ledger first; a plan built on a broken
  ledger inherits the break

## 2. Classify the work

Use `superpowers:brainstorming` if available; it classifies the slice as
**spike**, **bounded**, or **architectural** and gates on the user's approval
either way. Without it, do the same by hand:

- **Bounded** — a well-scoped change to a flow that already exists in this
  repo. Present a short design in chat, get an explicit yes, and write a plan
  only if the slice has more than a couple of steps.
- **Architectural** — new subsystems, changed interfaces, anything that
  restructures how parts fit. Write the design to
  `docs/plans/<slug>/<slice>-design.md` first, get it reviewed, then plan.

When in doubt, take the heavier path. Announce the classification out loud so
the user can override it — they know things about the change that the tree does
not show.

## 3. Write the plan

Use `superpowers:writing-plans` if available. The plan goes to
`docs/plans/<slug>/<MID>-<SNN>-plan.md` — beside the ledger, because the
ledger check requires plan paths to resolve inside the ledger's own directory.

The plan must carry, at the top:

- **Slice** — the ledger ID, and the ledger's path
- **Task status** — a checklist with one `- [ ]` per task, in execution order.
  This is the plan's executable state: `/jk:next` reads the first unchecked box
  to choose its task, and that task's own commit ticks it. It must sit *above*
  the Definition of Done, and these two must be the only checklists in the
  file — a third would make "the first unchecked box" ambiguous.
- **Definition of Done** — copied verbatim from the slice. Not paraphrased: the
  plan argues that its tasks satisfy *this* DoD, so the two must be the same
  text. It is acceptance criteria, not task state; `/jk:next` never reads it to
  decide what to do.
- **Validation** — the slice's tokens, each expanded to the command
  `.jk/validations.yml` maps it to, so an executor never has to guess

Then tasks. Each task:

- names exact files to create and modify
- states what it consumes from earlier tasks and produces for later ones
- carries bite-sized steps: write the failing test, run it and watch it fail,
  implement, run it and watch it pass, commit
- ends with a check that maps to one of the slice's validation tokens

**Every task ends in a verifiable state.** A task whose last step is "implement
the thing" with no way to tell whether it worked is not a task, it is a wish.

**No placeholders.** No "TBD", no "add appropriate error handling", no "similar
to task 2", no reference to a function no task defines. The executor may read
tasks out of order and cannot ask you what you meant.

## 4. Self-review before handing over

Check the plan against the slice yourself — this is a checklist, not a
delegation:

1. **DoD coverage.** For each item in the slice's definition of done, point at
   the task that satisfies it. A DoD item with no task is a gap; add the task.
2. **Row coverage.** For each row in the slice, point at the task that closes
   it and the task step that produces its `Verification`.
3. **Placeholder scan.** Search your own plan for the patterns above.
4. **Name consistency.** A function called one thing in task 3 and another in
   task 7 is a bug you are shipping to your own executor.

## 5. Register it

Update the slice in the ledger:

- set `Plan` to the plan's path, relative to the ledger
- set `Status` to `in-progress`

Run `jk-standards ledger` — it enforces that a slice past `open` names a plan
and that the plan exists — then commit the plan and the ledger change together
with trailers:

```
Plan: docs/plans/<slug>/ledger.md
Slice: <MID>/<SNN>
```

Report the task count and the first task, then stop. `/jk:next` executes.
