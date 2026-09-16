---
class: plan
---

# Plan M003/S02 — Release gate and governed doc

Status: current (2026-09-16)

**Slice:** M003/S02 — Release gate and governed doc, in
`docs/plans/skill-evals/ledger.md`

**Task status**

- [x] Task 1 — release gate, governed doc, drift map, RELEASE.md

**Definition of Done**

- [ ] The tag-path `verify` job runs the full corpus (agreed: full, not a
      smoke subset, at current corpus size)
- [ ] `docs/skill-evals.md` exists with taxonomy front-matter and passes
      the doc checks
- [ ] The drift map pairs `evals/**` and the harness with that doc
- [ ] `RELEASE.md`'s pre-tag checklist names `make eval` as the local
      preflight

**Validation**

- `format` → `pre-commit run --all-files`
- `discipline` → `jk-standards all`
- `eval` → `make eval`
- `gate` → `scripts/verify.sh`

## Task 1 — release gate, governed doc, drift map, RELEASE.md

1. `release.yml`: add a `skill-evals` job —
   `uses: ./.github/workflows/skill-evals.yml`, `secrets: inherit` —
   alongside `verify` (the tag is immutable either way; a red eval blocks
   the Release, which is the gate's point). Note the flaky-recovery rule
   in a comment: re-run the job, never re-tag.
2. Write `docs/skill-evals.md` (`class: gated`, dated Status): the eval
   discipline — corpus format pointer to `evals/README.md`, two-arm and
   require_lift semantics, config region, thresholds/ratchet time-box,
   CI/release/schedule surfaces, cost model, reading a failure. No
   restated inventory counts (count-drift).
3. `.github/docs-drift-map.yml`: mapping `evals/**` →
   `docs/skill-evals.md` with a reason.
4. `RELEASE.md`: pre-tag checklist gains `make eval` with a note that
   the tag push re-runs the suite in `release.yml`.
5. Tokens: `format`, `discipline`, `gate`; `eval` satisfied by the
   ship-window recorded run noted in evidence (rerun only if corpus or
   harness changed since — this slice changes neither). Range arms vs
   main. Evidence; tick task and DoD boxes; rows R17, R20–R22, N4;
   slice `done`; commit with trailers `Slice: M003/S02`,
   `Rows: R17,R20,R21,R22`.

Check that closes the task: `discipline` (`jk-standards all` exit 0).
