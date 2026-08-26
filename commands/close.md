---
description: Close a merged milestone — verify, sync, clean up the branch, and rebase the next milestone onto the new base
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

## 3. Close the milestone in the ledger

On the default branch:

- Set the milestone's `Status` to `done`.
- Confirm every slice is `done` or `accepted`; if one is not, the merge shipped
  something the ledger does not describe. Stop and report — do not "tidy" the
  ledger to match. The tree is the arbiter, and a mismatch here is a finding.
- Confirm the changelog carries the milestone's entry. If `/jk:ship` synced it,
  it is already there; if not, add it now.

Run `jk-standards ledger`, then commit with the milestone's trailers.

## 4. Clean up the branch

- Delete the local milestone branch.
- Delete the remote branch, unless the repo's convention keeps merged branches.
- Prune stale remote-tracking refs.

## 5. Prepare the next milestone

Find the next milestone whose `Depends` — at slice level — are satisfied.

- Create its branch from the **updated** default branch, and set its `Status`
  to `in-progress` if the user wants to start now; leave it `planned` if not.
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
Run /jk:plan to plan M002/S01.
```

If no milestone remains, say the programme is complete and name the ledger, so
its final state is easy to find later.
