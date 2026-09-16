---
class: plan
---

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
