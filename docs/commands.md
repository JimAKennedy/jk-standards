---
class: gated
---

# Workflow commands index

Status: current (2026-08-28)

Slash commands shipped by this repo, under `commands/<name>.md`, vendored into
a consuming project with `jk-standards install-commands`. They are the
procedural half of the discipline: the skills teach an agent how to write
within the conventions, the checks enforce them, and these commands drive the
delivery loop that produces the work in the first place.

Commands install to `.claude/commands/jk` by default. A project command in a
subdirectory is namespaced by it, so a vendored command is invoked as
`/jk:<name>` and never claims a bare name a consuming repo may want for itself.

| Command | Does |
|---|---|
| assess | Reads a free-form input document — an audit, a product vision, a feature brief — reconciles every item in it against the codebase, refines the decomposition with the user section by section, and writes a conforming ledger. Every input item becomes exactly one row, including the ones deliberately not actioned |
| plan | Takes the next open slice, classifies the work, writes an implementation plan beside the ledger carrying a task-status checklist and the slice's definition of done copied verbatim, self-reviews it for coverage and placeholders, and registers the plan path on the slice. Also repairs an existing plan when execution proves a step wrong, without resetting the boxes of tasks that already landed |
| next | Executes exactly one task — the first unchecked box in the plan's task-status checklist: derives its position from the files, works the task test-first, runs the slice's full validation set, appends the evidence, and commits code, checkbox, ledger row and evidence as one unit with traceability trailers (the evidence names no commit SHA: it ships inside the commit it would name, so the trailers are the join) — then stops at the slice boundary. Stops and asks rather than guessing when the milestone's branch does not exist and the ledger is not on the default branch |
| ship | Refuses to ship an unfinished milestone, re-runs every slice's validation on the current head, syncs the changelog and roadmap, pushes, and opens a pull request whose body is generated from the ledger and from git trailers rather than written from memory |
| close | Verifies the merge landed, closes the milestone in the ledger — directly on the default branch, or through a pull request when that branch is protected — deletes the branch, rebases or creates the next milestone's branch on the updated base, and prints the next action |
| status | Reads a delivery ledger and reports milestone/slice state, the next actionable slice, and any disagreement between the ledger and the working tree. Read-only: it never writes a file, and reports anything that would change state as something for the user to run |

The commands operate on the ledger format defined in the
[ledger standard](ledger-standard.md) and gated by the `ledger` check. A
command may assume a conforming ledger, because the check is what guarantees
one.

## The loop

```
research (free-form, outside this workflow)
  └─ /jk:assess <doc>     → ledger.md
       └─ /jk:plan        → <slice>-plan.md, slice in-progress
            └─ /jk:next   → one task, validated, evidenced, committed  ⟲
                 └─ /jk:ship   → PR, traced back to the ledger
                      └─ /jk:close  → merged, branch retired, next milestone ready
```

`/jk:status` reads at any point in that loop and changes nothing.

Three properties hold throughout, and are what the commands exist to protect:

**State lives in files.** The ledger, the plan's checkboxes, the evidence
files, and git. No command carries state in its head between invocations —
each derives its position by re-reading. An interrupted session loses nothing
and resumes by running the same command again.

**Nothing claims completion without evidence.** A slice reaches `done` only
with its definition of done checked, its validation tokens run, and an evidence
file recording what those runs returned. `/jk:ship` re-runs the whole set on
the current head rather than trusting that it passed when the slice landed.

**Every change traces to the plan.** Commits carry `Plan`, `Slice` and `Rows`
trailers, so the join between the tree and the ledger is a `git log --grep`
away in both directions. `/jk:ship` builds its pull-request body from those
trailers, and lists any commit that carries none as untraced work rather than
omitting it.

Commands lean on the [Superpowers](https://github.com/obra/superpowers) skills
where they are installed — `brainstorming` for refinement, `writing-plans` for
decomposition, `subagent-driven-development` for execution,
`verification-before-completion` for the gate — and each names the equivalent
by hand so a project without them still gets the same discipline.

## Consuming

Add a `commands` block to the same `skills-lock.json` that pins vendored
skills:

```json
{
  "version": 1,
  "commands": {
    "status": {
      "source": "JimAKennedy/jk-standards",
      "sourceType": "github",
      "commandPath": "commands/status.md",
      "computedHash": "<sha256 of the command file>"
    }
  }
}
```

Then install, and verify the pinned hashes on demand:

```bash
jk-standards install-commands
jk-standards install-commands --check
```

One lock file, one hash discipline, two kinds of vendored asset.
