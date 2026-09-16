---
class: plan
---

# M003 report — CI, release gate, and drift cadence

Status: current (2026-09-16)

Review record for milestone M003 of `docs/plans/skill-evals/ledger.md` —
the programme's final milestone — generated at the `/jk:auto` review gate.
Next step: read this, then `/jk:ship`.

**Vision:** No release ships unevaluated skills, and a model update that
degrades them surfaces within a week with no diff in this repo.

**Branch:** `milestone/M003-ci-release-drift` (4 commits on `main`).

## Slices

| Slice | Title | Rows | Status |
|---|---|---|---|
| M003/S01 | Reusable workflow and ci.yml wiring | R14–R16 done; N5 accepted | done |
| M003/S02 | Release gate and governed doc | R17, R20–R22 done; N4 accepted | done |
| M003/S03 | Weekly drift schedule | R18 done; N2 accepted | done |

## Definition of done

Every box checked. One amendment, approved at front-load and recorded:
S03's "one dispatched run on main" (impossible before the workflow file
reaches the default branch) became "the PR's own CI eval run completes
and uploads its artifact" — the same pipeline, secret, and artifact,
proven on the board ship watches.

## Validation

| Slice | Token | Result |
|---|---|---|
| all | format | exit 0 |
| all | discipline | jk-standards all: 0 violations |
| S01, S02 | gate | verify.sh: all locally-runnable gates passed |
| S02 | eval | ship-window recorded run of 2026-09-16 (10/10); this milestone changes neither corpus, harness, nor config |

Range arms vs main green (doc-drift 0 triggered-unsatisfied;
status-prose accuracy arm no violations).

## Traceability

- `c2419b4` plan: M003 slice plans and decisions — Slice: M003/S01, S02, S03
- `b3e8d73` feat: reusable skill-evals workflow with drift notify — Slice: M003/S01, Rows: R14
- `4d1571a` feat: per-PR eval gate wired into ci.yml — Slice: M003/S01, Rows: R15,R16
- `1838297` feat: release-tag eval gate and the discipline doc — Slice: M003/S02, Rows: R17,R20,R21,R22
- `28e37ef` feat: weekly drift cadence verified; milestone done — Slice: M003/S03, Rows: R18

No untraced commits.

## Things a reviewer should look at twice

- **Repo secrets were set during the front-load** with the user's
  explicit approval: `ANTHROPIC_API_KEY` and `ANTHROPIC_WORKSPACE_ID`
  from the local .env via `gh secret set` — a GitHub-settings mutation
  outside the tree.
- **The live positives ride this PR's own board**: the branch touches
  the workflow file (in eval-paths' filter set), so the paid gate fires
  on the PR; ship merges only on that green. Two DoD claims are
  contingent on it and say so in evidence (S01's real-work proof, S03's
  CI proof). The missing-secret negative is verified by the guard step's
  presence — staging it live would require deleting the repo secret.
- **The toolkit caught its own composition bug**: workflow-permissions
  flagged the notify job's issues:write exceeding release.yml's ceiling;
  fixed with a job-level grant and the static-composition reason inline.
- **Standing spend now exists**: weekly scheduled run + per-tag run +
  per-eval-relevant-PR run, each bounded by the config caps — minutes
  and cents at current corpus size, but no longer zero.

## Decisions (verbatim from M003-decisions.md)


# M003 decisions

Status: current (2026-09-16)

Append-only record per `/jk:auto` for skill-evals M003.

## 2026-09-16 — planning M003/S01–S03

- **Q:** Set the repo secrets now from the local .env? — **A:** Yes —
  `ANTHROPIC_API_KEY` and `ANTHROPIC_WORKSPACE_ID` set via `gh secret set`
  during the front-load (values from the gitignored .env; org-level key,
  so the workspace id travels with it).
- **Q:** Amend S03's DoD "one dispatched run on main" (impossible before
  the workflow file reaches main)? — **A:** Yes — the PR's own CI eval
  run (same workflow, same secret, artifact uploaded) is the proof;
  dispatch/schedule go live at merge.
- **Q:** Approve the designs? — **A:** Approve.
- **Decision:** Path filter via a plain `git diff --name-only` step, not a
  third-party paths-filter action. — **Why:** no new SHA-pinned dependency;
  the diff is four lines of shell.
- **Decision:** Relevant paths: `skills/`, `commands/`, `evals/`,
  `jk-standards.yaml`, `pyproject.toml`,
  `.github/workflows/skill-evals.yml`. — **Why:** the R15 set plus the two
  files whose edits change what an eval run means (config block, [eval]
  pins) and the workflow itself.
- **Decision:** `ci-complete` accepts `skill-evals` result `success`, or
  `skipped` only when `eval-paths` reported not-relevant — encoded in the
  shell comparison, so a skip is never an advisory pass. — **Why:** the
  repo's ci-hygiene rule.
- **Decision:** Cron `17 6 * * 1` (Mondays 06:17 UTC). — **Why:** weekly
  per R18; off-peak; odd minute avoids the top-of-hour herd.
- **Decision:** Drift notification mirrors sanitizer-nightly: an
  `if: always()` notify job with `issues: write` driving a single
  label-deduped `skill-evals-drift` issue — open/update on red, close on
  green — active only for schedule runs. — **Why:** R18 names that
  posture; the pattern already exists in-repo.
- **Decision:** The reusable workflow declares both secrets optional in
  `workflow_call` and guards at runtime, failing with the documented
  message when the key is absent. — **Why:** R16's loud-failure
  requirement; forked PRs get a named failure, not a silent skip.
