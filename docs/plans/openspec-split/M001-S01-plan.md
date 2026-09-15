---
class: plan
---

# Plan M001/S01 — The contract

Status: current (2026-09-15)

**Slice:** M001/S01 — The contract, in
`docs/plans/openspec-split/ledger.md`

**Task status**

- [x] Task 1 — Source path resolution in the ledger check, tests first
- [x] Task 2 — the standard's Source section and the check's doc pairs

**Definition of Done**

- [ ] `docs/ledger-standard.md` specifies `Source:` as an optional
      ledger-level bold key and states the ownership split, the mirror
      rule, and the granularity contract (one change → one ledger;
      milestone is the landing unit; a partially ticked mirror is expected
      mid-programme; archival is handed off at the final milestone's close)
- [ ] The `ledger` check verifies a repo-relative-path `Source:` resolves
      and leaves prose `Source:` untouched, with tests covering both —
      including a prose-with-filename case mirroring the skill-evals
      ledger's Source line, whose named proposal file no longer exists and
      must not flag
- [ ] The `checks/**` drift pairs (`docs/checks.md`, README tables,
      `reference/checks.mdx`) are satisfied for the check change

**Validation**

- `format` → `pre-commit run --all-files`
- `unit` → `pytest -q`
- `emit-fresh` → `jk-standards emit all --check`
- `discipline` → `jk-standards all`
- `gate` → `scripts/verify.sh`

## Task 1 — Source path resolution, tests first

Consumes: nothing. Produces: the `Source:` rule in
`src/jk_standards/checks/ledger.py` that Task 2 documents.

1. Write failing tests in `tests/test_ledger.py`, following that file's
   existing fixture pattern for building a ledger in `tmp_path` (find the
   helper its other cases use and reuse it). Cases:
   - `test_source_path_resolving_passes` — ledger whose pre-milestone
     region carries `**Source:** docs/input.md` with that file created →
     0 violations.
   - `test_source_path_directory_passes` — `**Source:** specs/change-1/`
     with that directory created → 0.
   - `test_source_path_dangling_flagged` — `**Source:** specs/gone.md`,
     nothing created → 1 violation naming the value.
   - `test_source_prose_skipped` — `**Source:** PROPOSAL-x.md (repo
     root, 2026-09-15). Deleted after assess.` with no such file → 0;
     the value contains whitespace, so it is prose.
   - `test_source_dangling_hatch_suppresses` — the dangling case with
     `<!-- ledger-ok: source archived externally -->` on the line → 0.
2. Run `pytest -q tests/test_ledger.py -k source` and watch every case
   fail because the check reports nothing (assertions on violation counts
   fail), the right reason.
3. Implement in `src/jk_standards/checks/ledger.py`, inside
   `_check_ledger`: scan lines before the first `_MILESTONE_RE` match;
   for each `_KEY_RE` match whose key is `Source`, take the same-line
   value; if it is non-empty and contains no whitespace, require
   `(root / value).is_file() or (root / value).is_dir()`, reporting a
   violation in the file's existing error style when it resolves to
   neither; skip when `_hatched(line)`. Values with whitespace are prose
   and never checked. Extend the module docstring's rule list with one
   line for the new rule.
4. Run the new tests, watch them pass; run the check against the real
   tree (`.venv/bin/jk-standards ledger --root .`) — both existing
   ledgers carry prose Source lines and must still conform.
5. Run `pytest -q` (full suite), `ruff check .`, `ruff format --check .`.
6. Append evidence to `evidence/M001-S01.md`, tick this task's box, run
   `.venv/bin/jk-standards ledger`, commit as one unit with trailers
   `Slice: M001/S01`, `Rows: R7`, and a `Docs-Not-Affected:` trailer for
   ARCHITECTURE.md (structural doc, no per-check enumeration — reasoning
   recorded in the decisions file). The remaining `checks/**` doc pairs
   are Task 2's deliverable and land inside this same PR range, so
   `doc-drift` (range-scoped) is satisfied at gate time.

Check that closes the task: `unit` (`pytest -q` exit 0).

## Task 2 — the standard's Source section and the doc pairs

Consumes: the rule from Task 1. Produces: the contract the S02 command
prose will cite.

1. Add a `## Source` section to `docs/ledger-standard.md`, placed between
   the `## Structure` block and `## Validation tokens`. Content:
   - `Source:` is an optional ledger-level bold key naming the input
     document or spec change the ledger was assessed from; a
     single-token repo-relative value is a path the `ledger` check
     requires to resolve, while a prose value is not checked.
   - The ownership split when `Source:` names a structured spec system
     document: the spec owns the *what* (proposal, requirement and
     scenario deltas, archived capability specs); the ledger owns the
     *how and proof* (milestones, slices, rows, DoD, validation,
     evidence, traceability).
   - The boundary rule: the ledger cites requirements and scenarios by
     name and never restates spec content.
   - The mirror rule: a checklist in the source document is ticked only
     to reflect what the ledger proves done, in ship's docs-sync commit.
   - The granularity contract: one spec change maps to one ledger,
     defaulting to one milestone, with multiple milestones allowed for a
     large change; the milestone is the landing unit; a partially ticked
     mirror after an intermediate milestone ships is expected; archival
     is handed off at the final milestone's close.
   - Update the doc's `Status:` anchor to the current date (the accuracy
     arm bites otherwise — learned in skill-evals M001).
2. Add the invariant row "A single-token `Source:` path resolves —
   `ledger` check" to the standard's Invariants table.
3. Doc pairs for the `checks/**` change: extend the `## ledger` section
   of `docs/checks.md` and `site/src/content/docs/reference/checks.mdx`
   with the Source rule, citing the new tests with `[verified:
   test_ledger::test_source_path_dangling_flagged]` and
   `[verified: test_ledger::test_source_prose_skipped]`; extend the
   README `ledger` row's rule text with a clause for Source resolution.
   Refresh the `Status:` anchors of both checks docs.
4. Run `.venv/bin/jk-standards emit all --check`; if `checks.json` or
   `doc-coverage.json` drifted, re-emit and stage.
5. Run every validation token: `format`, `unit`, `emit-fresh`,
   `discipline`, `gate` — and additionally
   `jk-standards doc-drift --root . --base main` and
   `jk-standards status-prose --root . --base main`, the two range-scoped
   arms that only CI would otherwise run (learned in skill-evals M001).
6. Append evidence, tick this task's box, tick the slice DoD boxes, set
   rows R6 and R7 and the slice `done`, run `.venv/bin/jk-standards
   ledger`, commit as one unit with trailers `Slice: M001/S01`,
   `Rows: R6`.

Check that closes the task: `gate` (`scripts/verify.sh` exit 0).
