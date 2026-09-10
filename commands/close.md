---
description: Verify a merged milestone landed closed, clean up its branch, and cut the next milestone from the genuinely current base — committing nothing
argument-hint: "[milestone-id] [ledger-path]"
disable-model-invocation: true
---

Retire a merged milestone and leave the repo ready for the next one.

This command exists because the gap between "the PR merged" and "the next
milestone can start cleanly" is where a file-based workflow rots: a ledger that
still says `in-progress`, a stale branch, and a next milestone quietly based on
the wrong commit.

## 1. Verify the merge before changing anything

- Identify the milestone: the argument, else the one whose slices are all
  `done` or `accepted` and whose branch has an open or recently merged PR.
- Confirm the PR is **merged** — not closed, not approved-but-open. If it is
  not merged, stop and say what its actual state is.
- Fetch, and confirm the milestone's commits are in the default branch.

If the PR was closed without merging, stop. Deciding what happens to abandoned
work is the user's call, and the branch is the only copy.

## 2. Update the default branch

Check out the default branch and fast-forward it. If it cannot fast-forward,
stop and report — something else landed in a way that needs a human.

## 3. Confirm the ledger already closed

This command **commits nothing**. The milestone's `Status: done` landed with
the merge — `/jk:ship` sets it in the same docs-sync commit that carries the
changelog, precisely so a protected default branch never needs a second pull
request just to say a milestone ended. Here, verify that it did:

- The milestone reads `done` on the updated default branch. If it does not,
  that is a **finding**, not something to fix in place: the merge shipped
  without ship's docs sync — a hand-opened PR, an older ship, a `--slice`
  sequence — and how to land the correction is the user's call. Report it
  and stop.
- Every slice is `done` or `accepted`; if one is not, the merge shipped
  something the ledger does not describe. Stop and report — do not "tidy"
  the ledger to match. The tree is the arbiter, and a mismatch here is a
  finding.
- The changelog carries the milestone's entry. `/jk:ship` owed it; if it is
  missing, report that as a finding too.

Run `jk-standards ledger` on the default branch, so the state being handed to
the next milestone is a checked one.

## 4. Clean up the branch

- Delete the local milestone branch.
- Delete the remote branch, unless the repo's convention keeps merged branches.
- Prune stale remote-tracking refs.

## 5. Prepare the next milestone

Find the next milestone whose `Depends` — at slice level — are satisfied.

- Create its branch from the **updated** default branch — which, because the
  close committed nothing, is genuinely current: no pending close PR, no
  stale status line, no rebase debt handed to the next milestone.
  Set its `Status` to `in-progress` if the user wants to start now; leave it
  `planned` if not.
- If its branch already exists from earlier work, rebase it onto the updated
  default branch. Never stack a new milestone on an unmerged one: a squash
  merge rewrites the base, and every commit the stacked branch shares replays
  as a conflict. If the repo ships a branch-discipline skill, follow it — it
  owns this rule.
- **Never rewrite a branch that has review comments on it.** Check before
  rebasing. If it does, stop and ask; a force-push there discards a reviewer's
  anchors.
- After any rebase, re-run the repo's full local gate. A rebase that compiles
  is not a rebase that passes.

## 6. Report the handoff

End with the state the user needs to start again, and nothing else:

```
M001 closed — merged in #123, branch deleted.
Next: M002 Citation Integrity (4 slices, none planned).
Branch milestone/M002-citation-integrity created from main @ <sha>.
Run /jk:plan to plan M002/S01, or /jk:auto to run M002 end to end.
```

If no milestone remains, say the programme is complete and name the ledger, so
its final state is easy to find later.
