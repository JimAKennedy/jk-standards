---
class: gated
---

# Ledger standard

Status: current (2026-08-26)

A **ledger** is a single Markdown file that holds the whole state of a delivery
programme: its milestones, the slices each milestone decomposes into, the rows
each slice closes, what "done" means for each slice, and what must pass before
anything may claim to be done.

This document defines the format. The `ledger` check enforces it.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as in
RFC 2119.

## Why a file

The state of in-flight work is normally kept in a tool — a tracker, a database,
a plugin's private store. That state then has to be kept in step with the tree
it describes, and the two drift the moment anything happens outside the tool.

A ledger inverts that. The file **is** the state; git is its history; the
working tree is the arbiter. There is nothing to synchronise, nothing to
migrate, and nothing that a crashed session, an interrupted agent, or a
hand-edit can corrupt beyond what `git diff` will show you. An agent reading a
ledger recomputes what to do next from the file every time rather than
remembering it, which is what makes the workflow resumable.

The cost of that choice is that a file cannot enforce its own invariants. That
is what the `ledger` check is for: the guarantees a schema would have given you
are recovered as a check that runs in pre-commit and CI.

## Layout

One ledger per programme, at:

```
docs/plans/<slug>/ledger.md
```

Everything the programme produces lives beside it:

```
docs/plans/<slug>/
├── ledger.md
├── M001-S05-plan.md          # per-slice implementation plan
└── evidence/
    └── M001-S05.md           # what was run, what it returned
```

The directory is configurable through `ledger.roots`; the internal layout is
not — a slice's `Plan:` and `Evidence:` paths MUST resolve inside the ledger's
own directory, so a programme is one movable, self-contained tree.

## Structure

A ledger is a `class: gated` doc. Below the title it carries milestone
sections, each containing slice sections, each containing a row table.

````markdown
---
class: gated
---

# Theory Audit Remediation Ledger

Status: current (2026-08-26)

**Source:** poly_theory_audit.md (external research archive, August 2026)

## Milestone M001 — Theory Corrections

**Vision:** Every claim in the guide that is factually wrong or overclaimed
relative to its source is corrected, and each correction is locked by a test.
**Branch:** milestone/M001-theory-corrections
**Status:** in-progress

### Slice M001/S05 — Chapter 2 hedges

**Depends:** M001/S01
**Plan:** M001-S05-plan.md
**Validation:** doc-conformance, gate
**Evidence:** evidence/M001-S05.md
**Status:** open

**Definition of Done**

- [ ] Chapter 2's opening no longer asserts multi-century continuity in the
      guide's own voice
- [ ] The gankogui claim uses the source's descriptive phrasing
- [ ] Both are locked by named test cases so an edit cannot silently regress

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| F07 | Unsourced "for centuries" claim in the chapter opening | `02-sub-saharan-africa.mdx` | Case `S05-F07` forbids unhedged multi-century phrasing | `open` |
| F08 | "single most important timeline pattern" overstates the cited source | `02-sub-saharan-africa.mdx` | Case `S05-F08` asserts the descriptive phrasing | `open` |
````

### Milestones

A milestone heading MUST match `## Milestone <ID> — <title>`, where `<ID>` is
`M` followed by three digits. IDs MUST be unique within a ledger.

A milestone MUST declare, as bold key lines directly beneath its heading:

| Key | Meaning |
|---|---|
| `Vision` | One or two sentences describing the state of the world once the milestone lands. Not a task list. |
| `Branch` | The single branch every slice in the milestone lands on. |
| `Status` | `planned`, `in-progress`, or `done`. |

A milestone MAY also declare `Demo` — how a reader confirms the whole milestone
landed, as distinct from any one slice's definition of done. Any other bold key
lines a programme finds useful are carried through and ignored by the check.

One branch per milestone is the rule the `branch-discipline` skill exists to
protect: the next milestone never stacks on an unmerged one.

### Slices

A slice heading MUST match `### Slice <MID>/S<NN> — <title>`, where `<MID>` is
the enclosing milestone's ID and `<NN>` is two digits. A slice MUST be nested
under the milestone whose ID it names — a slice that claims a different
milestone than the section it sits in is a violation, not a cross-reference.

A slice is the unit that carries a definition of done, a validation set, and a
branch's worth of review. It MUST declare:

| Key | Required | Meaning |
|---|---|---|
| `Status` | always | `open`, `in-progress`, `done`, or `accepted`. |
| `Validation` | always | Comma-separated validation tokens (see below). |
| `Evidence` | always | Path to this slice's evidence file, relative to the ledger. |
| `Plan` | once past `open` | Path to the implementation plan, relative to the ledger. |
| `Depends` | optional | Comma-separated slice IDs that MUST land first. |

Plus a `**Definition of Done**` heading followed by a non-empty checklist. A
slice with no definition of done cannot be finished, only abandoned, so the
check refuses one.

`accepted` is a deliberate no-change: the slice was considered and closed
without work. It is recorded rather than deleted so a later pass does not
rediscover it as an omission.

### Rows

Each slice owns one table. A row is the smallest traceable unit — a finding, a
requirement, a defect. The required columns are `ID`, `Item`, `Verification`,
and `Status`; any others (severity, disposition, source section) MAY be added
and are ignored by the check.

Rows live inside the slice that closes them. There is no `Slice` column and no
separate index: nesting is what makes "every row belongs to a real slice" true
by construction rather than by cross-reference.

A slice ends at the next slice heading or at the next milestone-level (`##`)
heading, whichever comes first. Sections below the last slice — `## Sequencing`,
`## Related issues`, `## Out of scope` — are siblings of the milestones and may
carry tables of their own without those tables being read as anybody's rows.
Headings deeper than `##` stay inside the slice, so a slice may sub-divide its
own body.

A row's `Verification` cell MUST name what proves it — a test case, a check
name, a named artifact. Not "tested", not "verified manually". The cell is the
claim a reviewer audits.

## Validation tokens

A slice's `Validation` line names tokens, never commands:

```markdown
**Validation:** unit, doc-conformance, e2e
```

Each token is resolved by the consuming repository, in `.jk/validations.yml`:

```yaml
unit:            cmake --build build --config Release && ctest --test-dir build
doc-conformance: bash scripts/check-doc-conformance.sh
e2e:             bash scripts/site-verify-local.sh
gate:            bash scripts/pre-push-check.sh
```

This is what makes a ledger portable. `unit` means a different command in a C++
plugin than in an Astro site; the ledger says what class of assurance a slice
owes, and the repository says how that assurance is obtained. The check asserts
that every token a ledger uses is declared, so a typo is a failure rather than a
silently skipped gate.

## Evidence

A slice's evidence file records what was actually run. It is appended to as
work lands, never rewritten:

```markdown
## M001/S05 — task 2

- `doc-conformance` → exit 0, 16 files, 0 failures
- commit `a1b2c3d`
- 2026-08-26
```

Evidence is terse by design: the command, its result, the commit it belongs to.
Logs belong in CI artifacts. What is recorded here is the fact that the gate ran
and what it returned, so a reader can tell an asserted completion from a
demonstrated one.

## Traceability

Every commit produced against a ledger carries trailers naming what it
implements:

```
Plan: docs/plans/theory-audit/ledger.md
Slice: M001/S05
Rows: F07,F08
```

Git trailers are the join key between the plan and the tree, in both
directions: a slice's commits are `git log --grep`-able, and a commit names the
row it closes. Trailers survive rebase, squash and cherry-pick, which is why
they are used in preference to branch names or commit-message conventions.

## Invariants

| Invariant | Mechanism |
|---|---|
| Milestone and slice IDs are well-formed and unique | `ledger` check |
| A slice sits under the milestone it names | `ledger` check |
| Status tokens come from the declared vocabulary | `ledger` check |
| `Depends` names slices that exist in the ledger | `ledger` check |
| Every slice declares a non-empty definition of done | `ledger` check |
| Every validation token is declared by the consuming repo | `ledger` check |
| A `done` slice has every DoD box checked and an evidence file on disk | `ledger` check |
| A `done` slice's rows are all `done` or `accepted` | `ledger` check |
| Plan and evidence paths stay inside the ledger's directory | `ledger` check |
| No placeholder text survives into a committed ledger | `ledger` check |

## Escape hatch

A single row or slice that must violate a rule carries an in-band reason on the
line the check flags:

```markdown
**Validation:** manual-uat  <!-- ledger-ok: no automatable gate; UAT script in the plan -->
```

The hatch is greppable, carries a written reason, and suppresses exactly the
line it sits on — the same discipline every other check in this toolkit uses.
