---
name: branch-discipline
description: Keep milestone work on one branch at a time and land it cleanly — one branch per milestone, never stack the next milestone on an unmerged one, and re-run the full pre-commit suite after every rebase. Use when starting, rebasing, or merging a milestone branch, or when tempted to branch the next milestone off an open PR.
---

# Branch discipline

Milestone work lands cleanly when each milestone owns exactly one branch and
that branch is rebased and re-checked before it merges. The failure mode this
prevents is a chain of half-merged milestones that no rebase can untangle.

## One branch per milestone

Cut **one** branch per milestone off the current `main`, named for the
milestone it delivers (`milestone/M005`, `milestone/M006`). Everything that
milestone ships — every slice, every task — lands on that one branch, and the
branch exists only until its PR merges. Don't open a second branch for the
same milestone, and don't reuse a milestone branch for the next milestone: a
fresh milestone starts from a fresh cut of `main` after the previous one has
landed.

The branch name *is* the unit of work. When `milestone/M005` merges, that
milestone is done; branch protection saw one squashed commit, and `main` moved
forward by exactly one milestone.

## Never stack milestones

Do not branch `milestone/M006` off `milestone/M005` while M005 is still
unmerged. Wait for M005's PR to land on `main`, then cut M006 from the updated
`main`.

The rationale is the **squash merge**. This repo squash-merges every PR, so
M005's twenty commits collapse into a single new commit on `main` that no M005
branch commit is an ancestor of. If M006 was branched off M005's pre-squash
history, M006 now carries M005's *original* commits as its own — and when you
rebase M006 onto the squashed `main`, git replays those already-landed commits
against a tree that already contains their effect. Every one of them is a
conflict, resolved by hand, for changes that are already merged. Stacking turns
one clean squash into a full-branch conflict replay. Waiting for the merge
costs minutes; unstacking a stacked branch costs the afternoon.

## Re-check after every rebase

A rebase replays your commits onto a moved base, and the rebased result is code
that **has never been checked in that combination** — your changes against
their new context. Passing pre-commit before the rebase proves nothing about
the post-rebase tree.

So after every rebase (and after resolving any conflict), run the full suite
across the whole tree, not just staged files:

```bash
pre-commit run --all-files
```

`--all-files` is the load-bearing flag. The default `pre-commit run` only
checks staged changes; a rebase can silently break a file you didn't touch this
session (a moved import, a renamed symbol, a format rule that now applies to a
line the rebase pulled in). Only the all-files pass reflects what CI will
actually see on the rebased branch. Fix what it reports before you force-push.

## Completeness checklist

- [ ] Exactly one branch named for the milestone (`milestone/M###`), cut from current `main`
- [ ] Next milestone is branched only after the previous one's PR has squash-merged
- [ ] No milestone branch is stacked on another unmerged milestone branch
- [ ] `pre-commit run --all-files` run and green after every rebase and every conflict resolution
- [ ] Force-push only after the all-files pass, so CI sees what you saw
