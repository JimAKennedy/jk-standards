---
description: Execute the next task in the current milestone — one task, validated, evidenced, committed, then stop
argument-hint: "[--slice] [ledger-path]"
disable-model-invocation: true
---

Work the ledger forward by exactly one task. Then stop.

Stopping is the design, not a limitation. State lives in the ledger, the plan's
checkboxes, and git — never in this session's memory — so a crash, an
interruption, or a closed laptop loses nothing, and the next `/jk:next`
recomputes where it is from the files. Never carry state forward in your head
between invocations.

## 1. Derive the position — never assume it

Read the ledger fresh, every time.

1. `jk-standards ledger` must pass. If it does not, report the violations and
   **stop** — a broken ledger is not a safe thing to execute against.
2. **Slice** — the first whose status is `in-progress`, else the first `open`
   slice with all `Depends` satisfied.
   - No such slice, and every slice `done` or `accepted` → the milestone is
     complete. Say so and point at `/jk:ship`.
   - The slice has no `Plan` → say so and point at `/jk:plan`. **Stop.**
3. **Task** — the first unchecked box in the plan's **Task status** checklist.
   Not the definition-of-done copy: that is the slice's acceptance criteria, not
   task state, and `/jk:plan` requires it to sit below the task list. A plan
   with no Task status checklist is malformed — say so and **stop**. Repairing
   a plan is `/jk:plan`'s job, not this command's — section 2 of that command
   covers it, and an already-planned slice is a legitimate argument there.
4. **Branch** — the milestone's `Branch`. Three cases, and only the first two
   proceed without asking:
   - It exists → check it out.
   - It does not exist, and the ledger is on the default branch → create it
     from there and say so.
   - It does not exist, and the ledger is **not** on the default branch →
     **stop and ask.** Cutting from the default branch yields a branch with no
     ledger and no plan on it, so there is nothing to execute against; cutting
     from the ledger's own commit carries whatever else is unmerged alongside
     it. Which is right turns on whether that other work belongs in this
     milestone's review, and that is the user's call, not a default.

   If the working tree is dirty with changes no task claims, stop and ask — do
   not sweep someone else's work into your commit.

Announce, before doing anything: the milestone, the slice, the task, and the
exact command that will prove it.

## 2. Execute exactly one task

Use `superpowers:subagent-driven-development` if available — a fresh subagent
for the task, then a two-stage review (does it meet the spec; is the code
good). Without it, execute the task's steps in this session, in order.

Either way:

- **Test first.** Write the failing test, run it, and *see it fail for the
  right reason* before writing implementation. A test that passes before the
  change proves nothing.
- **Follow the plan's steps exactly.** If a step is wrong or impossible, stop
  and say so — do not improvise around it. A plan that needs improvising needs
  editing, and that is a decision for the user: name the defect precisely, so
  `/jk:plan` can repair that step rather than re-plan the slice. Report what
  the step said, what actually happened, and whether sibling tasks share the
  fault — they often do not, and a blanket fix breaks the ones that were right.
- **Do only this task.** Adjacent improvements you notice go in the report, not
  in the diff. An unrequested change is one a reviewer did not ask for and
  cannot easily separate.

**Stop and ask** on: a blocker, an unclear instruction, a validation that fails
for a reason the task did not anticipate, or anything that would widen the
slice. Guessing is what this workflow exists to prevent.

## 3. Validate before claiming anything

Use `superpowers:verification-before-completion` if available. The rule stands
without it: **no completion claim without fresh evidence in this turn.**

- Run the task's own check first — the fast one.
- Then run every validation token the slice declares, resolved through
  `.jk/validations.yml`. Not a subset. Not "the ones likely to be affected".
- Read the actual output: exit code, failure count. "Should pass" is not a
  result.

If anything fails, fix it and re-run, or stop and report. Never proceed to the
commit with a red gate.

## 4. Record the evidence

Append to the slice's evidence file — never rewrite it:

```markdown
## <MID>/<SNN> — <task name>

- `<token>` → exit 0, <headline counts>
- `<token>` → exit 0, <headline counts>
- <YYYY-MM-DD>
```

Terse. Command, result, date. Logs belong in CI artifacts; what belongs here is
the fact that the gate ran and what it returned.

**Do not name a commit SHA.** This file ships inside the commit it would be
describing, so that SHA does not exist yet — and a line you cannot write truly
is a line you will write falsely. A fabricated SHA is worse than an omitted one:
it is indistinguishable from a real one and will be trusted. The `Slice:` and
`Rows:` trailers are the join, and `git log --grep` resolves it in both
directions. (Backfilled evidence, for work that landed before the ledger
existed, is the opposite case and does name its SHA — see the ledger standard.)

## 5. Commit as one unit

The code, the plan's checkbox, the ledger row, and the evidence go in **one
commit**. Splitting them lets the tree and the ledger disagree, which is the
failure mode this whole design exists to avoid.

Trailers carry the traceability:

```
Plan: docs/plans/<slug>/ledger.md
Slice: <MID>/<SNN>
Rows: <ids this task closes, comma-separated>
```

Run `jk-standards ledger` before committing. If this task closed the last of a
slice's rows and satisfied its whole definition of done, set the slice `done` —
the check will then require every DoD box ticked, the evidence file present,
and every row closed or accepted, which is exactly the claim you are making.

## 6. Report, then stop

Say what landed, what the gates returned, and what is next. Then **stop** —
unless `--slice` was passed, in which case continue to the next task in the
same slice and stop at the slice boundary. Never run past a slice boundary:
that is where a human decides whether the thing being built is still the right
thing.

For unattended running the user wraps this in their own loop. That is their
choice to make per session, not a mode baked into this command.
