---
class: plan
---

# Plan M002/S02 — Corpus breadth and selection eval

Status: current (2026-09-16)

**Slice:** M002/S02 — Corpus breadth and selection eval, in
`docs/plans/skill-evals/ledger.md`

**Task status**

- [ ] Task 1 — corpus breadth, selection eval, recorded passing run

**Definition of Done**

- [ ] At least two scenarios each for `versioned-state-serialization`,
      `realtime-audio-safety`, and `doc-anti-drift`
- [ ] Selection eval covers every corpus skill and includes a
      no-skill-applies negative case
- [ ] A recorded run passes at the configured thresholds

**Validation**

- `format` → `pre-commit run --all-files`
- `eval` → `make eval`

## Task 1 — corpus breadth, selection eval, recorded run

Consumes: S01's harness, config, and entry. Produces: the initial corpus
and the milestone's recorded passing run.

1. Add cases under `evals/cases/` (S01 shipped
   versioned-state-serialization-basic):
   - `versioned-state-serialization-migration` — task: extend an existing
     versioned format with a new field; rubric: version bumped, old
     versions still branch-readable, no silent reinterpretation.
   - `realtime-audio-safety-callback` — task: implement an audio callback
     mixing voices; rubric: no allocation, no locks, no syscalls/IO in
     the callback path.
   - `realtime-audio-safety-review` — task: review a given callback
     containing a mutex and a `new`; rubric: both violations named, safe
     alternatives proposed.
   - `doc-anti-drift-newdoc` — task: author a short feature doc for a
     repo following the discipline; rubric: lifecycle class front-matter,
     dated Status line, no progress-tracking prose, claims cite tests.
   - `doc-anti-drift-review` — task: critique a doc bearing an undated
     Status and a hardcoded inventory count; rubric: both violations
     identified with the discipline's remedies.
2. Selection eval, judge-free: `evals/test_skill_selection.py` (same
   API-key skip guard) — loads name+description for every skill from
   `site/src/generated/skills.json`, presents one task statement per
   corpus skill plus one negative ("update npm dependencies" — no skill
   applies), asks the agent model to answer with exactly one skill name
   or `none`, scores by exact match, requires all correct; results
   appended to the run's JSON via `write_results`'s selection block.
3. Extend `evals/README.md`'s case list table (mind count-drift: no
   restated totals).
4. Run `make eval` (both files), read output; record per-case scores,
   selection results, and usage in evidence. If any case misses its
   threshold, treat as a real finding: adjust the scenario prompt only if
   it is genuinely ambiguous (record the change), never lower a threshold
   silently — a threshold change is a halt for the user.
5. `format` token; evidence; tick task and DoD boxes; rows R5, R6 done;
   slice `done`; milestone `done`; ledger check; commit with trailers
   `Slice: M002/S02`, `Rows: R5,R6`.

Check that closes the task: `eval` (`make eval` exit 0).
