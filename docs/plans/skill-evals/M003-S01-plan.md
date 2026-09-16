---
class: plan
---

# Plan M003/S01 — Reusable workflow and ci.yml wiring

Status: current (2026-09-16)

**Slice:** M003/S01 — Reusable workflow and ci.yml wiring, in
`docs/plans/skill-evals/ledger.md`

**Task status**

- [ ] Task 1 — skill-evals.yml reusable workflow
- [ ] Task 2 — ci.yml wiring: eval-paths, skill-evals, ci-complete

**Definition of Done**

- [ ] `.github/workflows/skill-evals.yml` exists as a `workflow_call`
      reusable, SHA-pinned, permission-ceiling compliant
- [ ] The ci.yml `skill-evals` job passes through as success on a PR
      touching no eval-relevant paths, and does real work on one that does
- [ ] `ci-complete` names the job in both the `needs` list and the shell
      comparison
- [ ] A run without the secret on eval-relevant changes fails with the
      documented message

**Validation**

- `format` → `pre-commit run --all-files`
- `discipline` → `jk-standards all`
- `gate` → `scripts/verify.sh`

## Task 1 — the reusable workflow

Consumes: M002's `make eval` path. Produces: the workflow S02/S03 and
ci.yml call.

1. Write `.github/workflows/skill-evals.yml`: header comment with the
   pinned-tag consumption example (repo convention); `on:` carrying
   `workflow_call` (secrets `ANTHROPIC_API_KEY` and
   `ANTHROPIC_WORKSPACE_ID`, both `required: false`), `schedule`
   (`cron: "17 6 * * 1"`), and `workflow_dispatch`. Top-level
   `permissions: contents: read`. Jobs, inside
   `region:skill-evals-jobs` markers:
   - `eval`: checkout and setup-python at the SHA pins used by ci.yml;
     `pip install -e ".[eval]"`; a guard step that fails with the
     documented message ("skill-evals needs the ANTHROPIC_API_KEY
     repository secret — forked PRs cannot see it; a maintainer re-runs
     from a branch") when the secret is empty; run
     `python -m pytest evals/ -q` with both env vars; upload
     `evals/results/*.json` as artifact `skill-evals-results`,
     `retention-days: 14`, `if-no-files-found: error`.
   - `notify`: `if: always() && github.event_name == 'schedule'`,
     `permissions: issues: write`, mirroring sanitizer-nightly's
     open-or-update/close-on-green flow for a `skill-evals-drift`
     labeled issue keyed on the eval job's result.
2. `action-pinning`, `workflow-permissions`, `workflow-concurrency`
   checks over the new file (`jk-standards all`); fix anything flagged.
3. Evidence, tick box, ledger check, commit with trailers
   `Slice: M003/S01`, `Rows: R14`.

Check that closes the task: `discipline` (`jk-standards all` exit 0).

## Task 2 — ci.yml wiring

Consumes: Task 1's workflow. Produces: the per-PR gate.

1. In `.github/workflows/ci.yml` add:
   - `eval-paths`: checkout `fetch-depth: 0`; one script step computing
     the changed set — PR: `git diff --name-only origin/$GITHUB_BASE_REF...HEAD`;
     push: `git diff --name-only ${{ github.event.before }} HEAD` — and
     setting output `relevant=true` when any path starts with `skills/`,
     `commands/`, `evals/`, or equals `jk-standards.yaml`,
     `pyproject.toml`, or `.github/workflows/skill-evals.yml`.
   - `skill-evals`: `needs: eval-paths`,
     `if: needs.eval-paths.outputs.relevant == 'true'`,
     `uses: ./.github/workflows/skill-evals.yml`, `secrets: inherit`.
2. `ci-complete`: add `eval-paths` and `skill-evals` to `needs`; extend
   the shell so `eval-paths` must be `success` and `skill-evals` must be
   `success` OR (`skipped` AND `eval-paths.outputs.relevant != 'true'`).
   Update the header comment naming the callee's ceiling if needed
   (`skill-evals.yml` → none beyond `contents: read`; notify re-grants
   its own `issues: write`, which the ci.yml ceiling already allows).
3. `format`, `discipline`, `gate`; evidence (noting the real CI proof
   arrives with the PR run, this branch touching `evals/`-relevant
   paths); tick box and the first three DoD boxes (the fourth — the
   missing-secret failure — is verified by the guard step's presence and
   recorded as prose-verified, with the live negative impossible to
   stage without deleting the secret); set rows R14–R16 and N5 per
   ledger, slice `done`; commit with trailers `Slice: M003/S01`,
   `Rows: R15,R16`.

Check that closes the task: `gate` (`scripts/verify.sh` exit 0).
