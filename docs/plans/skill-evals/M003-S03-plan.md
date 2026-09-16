---
class: plan
---

# Plan M003/S03 — Weekly drift schedule

Status: current (2026-09-16)

**Slice:** M003/S03 — Weekly drift schedule, in
`docs/plans/skill-evals/ledger.md`

**Task status**

- [x] Task 1 — verify the cadence surfaces and record the CI proof

**Definition of Done**

- [ ] The reusable workflow carries `schedule` (weekly) and
      `workflow_dispatch` triggers on main
- [ ] The PR's own CI eval run completes and uploads its results artifact
      (dispatch and schedule go live at merge) — amended from "one
      dispatched run on main", which is impossible before the file
      reaches the default branch; amendment recorded in
      M003-decisions.md

**Validation**

- `format` → `pre-commit run --all-files`
- `discipline` → `jk-standards all`

## Task 1 — verify cadence surfaces, record the CI proof

1. Confirm `skill-evals.yml` (from S01) carries the `schedule` and
   `workflow_dispatch` triggers and the schedule-only notify job — these
   landed in S01's file; this slice owns proving them.
2. The CI-proof half of the DoD is completed at ship time by the PR's
   own `skill-evals` run (this branch touches eval-relevant paths, so
   `eval-paths` will trigger it). Record in evidence now that the box is
   ticked contingent on that run, which `/jk:ship` watches before
   merging — a red eval run blocks the ship, so the tick cannot outlive
   a false claim.
3. Tokens: `format`, `discipline`. Evidence; tick task and DoD boxes;
   rows R18 and N2; slice `done`, milestone `done`; commit with trailers
   `Slice: M003/S03`, `Rows: R18`.

Check that closes the task: `discipline` (`jk-standards all` exit 0).
