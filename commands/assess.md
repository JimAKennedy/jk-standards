---
description: Analyse the codebase against a vision or audit document and produce a delivery ledger
argument-hint: "<input.md> [ledger-slug]"
---

Turn a free-form input document — an audit, a product vision, a feature
brief — into a **delivery ledger** conforming to the ledger standard.

The input is research. The output is a plan of record. Everything between those
two is a conversation with the user, not a generation step.

## 1. Read both sides

**The input document** (the argument; ask for a path if none was given). Read
it completely before saying anything about it. Identify what it actually
asserts: findings, gaps, requested capabilities, and — importantly — anything
it *assumes* about the codebase.

**The codebase.** Establish what is already true. For each claim or request in
the input, determine whether it is already done, partly done, wrong about the
current state, or genuinely outstanding. This is the step that earns the
ledger's credibility: an input document is a snapshot from outside, and some of
it will be stale.

Report that reconciliation before proposing any structure:

```
Read <input>: 14 items.
Already satisfied: 3 (say which, and where in the tree).
Partly satisfied: 2 (say which half is missing).
Contradicted by the current code: 1 (say what the code actually does).
Outstanding: 8.
```

**Partly satisfied is its own bucket.** An item whose substance is already in
the tree but whose verification is not is neither done nor outstanding, and
filing it as either misleads: as done, the missing lock never gets written; as
outstanding, a later reader rewrites prose that was already correct. The row
survives, rescoped to the work that actually remains.

## 2. Refine, don't generate

Use `superpowers:brainstorming` on its architectural path if it is available;
otherwise run the same shape by hand. Either way the rules are:

- Ask clarifying questions **one at a time**, and only ones whose answer
  changes the decomposition.
- Where the input is ambiguous about intent, ask. Where it is ambiguous about
  mechanism, propose and let the user correct.
- Present the milestone decomposition **in sections**, and get agreement on
  each before moving on. Do not present a finished ledger for approval — by
  then it is too late to argue with cheaply.

Decompose in this order, because each level constrains the next:

1. **Milestones** — each one a coherent change in the state of the world,
   landable on a single branch, with a `Vision` sentence that is an outcome and
   not a task list. If you cannot write that sentence, the milestone is a bag
   of unrelated work; split it.
2. **Slices** — the unit that carries a definition of done and a branch's worth
   of review. A slice produces something independently testable. Fold setup and
   docs into the slice whose deliverable needs them; split only where a
   reviewer could reject one and approve its neighbour.
3. **Rows** — the smallest traceable unit: one finding, requirement, or defect
   from the input, with the location it lands in and what will prove it.

**Every item in the input becomes exactly one row.** An item deliberately not
being actioned is still a row, with status `accepted` and a reason — recorded
so a later pass does not rediscover it as an omission. Nothing is silently
dropped; the ledger's worth depends on it.

## 3. Definition of done and validation

For each slice, agree with the user:

- **Definition of Done** — a checklist of observable outcomes, not activities.
  "The chapter opening no longer asserts X in our own voice" is an outcome;
  "update the chapter" is an activity. Each item must be checkable by someone
  who did not do the work.
- **Validation** — which token set this slice owes: unit, integration,
  end-to-end, doc conformance, manual UAT, whatever the repo declares. Read
  `.jk/validations.yml` and use only tokens it declares. If a token is needed
  that the repo does not declare, add it to that file as part of this command
  and say so.

A slice whose only validation is "review it" is a slice with no gate. Say so
and propose one.

## 4. Work that already landed

An audit of a live programme will find some of it already delivered. Those
items are still rows, and the slices that closed them are still slices — with
`Status: done`. The ledger check then requires each of those slices to carry a
`Plan:` that resolves to a file on disk, an evidence file, every definition-of-
done box ticked, and no row left open. None of that exists retrospectively, so
agree with the user how to record it before writing the ledger:

- **Evidence** — reconstruct one file per slice from the merge commit and the
  tests it added: which gates ran, what they returned, the commit SHA, the
  date. State in the file that it is backfilled, so a reader does not mistake
  it for a contemporaneous record.
- **Plan** — a slice that shipped before the ledger existed has no plan, and
  writing one retrospectively is a fiction. Use the escape hatch on the line
  instead, naming what stood in for it:

  ```markdown
  **Plan:** —  <!-- ledger-ok: landed as PR #256 before this ledger existed; the PR is the plan of record -->
  ```

Do not quietly start the ledger at the current frontier. Dropping the closed
rows breaks the rule that every input item becomes exactly one row, and a later
pass rediscovers them as omissions.

## 5. Sequencing

Record `Depends` between slices, and state the reason for each dependency in
prose beneath the milestone. Only real dependencies — "these two touch the same
paragraph" is real; "it feels tidier" is not, and over-constraining the graph
is what makes a programme serialise for no reason.

## 6. Write it

Write `docs/plans/<slug>/ledger.md` (slug from the argument, else proposed and
confirmed), then:

- Run `jk-standards ledger` and fix anything it reports. Do not hand over a
  ledger that fails its own check.
- Show the user the slice inventory and the first actionable slice.
- Commit the ledger on its own, before any implementation branch exists.
- Name the branch the ledger landed on, and say whether that is the default
  branch. **The ledger and its plans must reach the default branch before any
  milestone branch is cut from it** — `/jk:next` and `/jk:close` both cut
  milestone branches from the default branch, and one cut from a base without
  the ledger has nothing to execute against. If the ledger is on a feature
  branch, say so plainly and name the two ways forward — land it first, or cut
  the milestone branch from the ledger's own commit — without picking for the
  user.

Then stop. **Do not plan a slice and do not write code.** `/jk:plan` is the
next step, and it is the user's to take.
