---
class: plan
---

# Plan M001/S01 — Secret-hygiene preflight

Status: current (2026-09-15)

**Slice:** M001/S01 — Secret-hygiene preflight, in
`docs/plans/skill-evals/ledger.md`

**Task status**

- [ ] Task 1 — add the secrets-scan hook to the local pre-commit config and
      prove a staged Anthropic-style key is rejected

**Definition of Done**

- [ ] A staged Anthropic-style key fails a local commit, demonstrated and
      recorded in evidence
- [ ] The GHA `pre-commit` job passes running
      `.pre-commit-config.local.yaml` with the `secrets-scan` hook included

**Validation**

- `format` → `pre-commit run --all-files`
- `gate` → `scripts/verify.sh`

## Task 1 — add the hook and prove the rejection

Consumes: nothing. Produces: the guarded local config every later slice's
local key-handling relies on.

1. Edit `.pre-commit-config.local.yaml`: append `- id: secrets-scan` to the
   hook list under the existing `repo: .` block.
2. Attempt environment build and a clean run:
   `pre-commit run --config .pre-commit-config.local.yaml secrets-scan --all-files`
   (use `.venv/bin/pre-commit`). Two outcomes:
   - It runs (pass or findings): proceed to step 3.
   - The golang environment fails to build (no Go module in this repo, no
     `additional_dependencies` on the shipped hook): revert the line, and
     instead append to `.pre-commit-config.yaml` a new pinned repo block —
     `repo: https://github.com/gitleaks/gitleaks` at the latest release tag
     observed from that repo at execution time, hook id `gitleaks` — then
     re-run with that config. Record which path was taken in evidence and
     in the decisions file.
3. Demonstrate the rejection: write a scratch file `leak-demo.txt` in the
   repo containing a fabricated Anthropic-style key (the `sk-ant-` prefix
   followed by base64-ish filler), `git add` it, run the hook the same way
   with the file staged, and confirm nonzero exit naming the finding. If
   gitleaks does not flag it, add `.gitleaks.toml` with
   `[extend] useDefault = true` plus a rule matching `sk-ant-[A-Za-z0-9_-]+`,
   and re-run until the staged key is rejected.
4. Clean up: `git reset` the scratch file and delete it. Confirm
   `git status` shows only the intended config change (plus ledger, plan,
   evidence edits).
5. Run the full local-config suite as the GHA job does:
   `pre-commit run --config .pre-commit-config.local.yaml --all-files` —
   must exit 0 on the clean tree.
6. Run the slice's validation tokens: `format`
   (`.venv/bin/pre-commit run --all-files`) and `gate` (`scripts/verify.sh`).
   Read the exits.
7. Append evidence to `evidence/M001-S01.md`: hook path taken, the rejection
   demonstrated (exit code and rule name), both token results, the date.
8. Tick this task's box, tick the slice DoD boxes, set row R0 and the slice
   `done`, run `.venv/bin/jk-standards ledger`, and commit everything as one
   unit with trailers `Plan:`, `Slice: M001/S01`, `Rows: R0`.

Check that closes the task: `gate` (`scripts/verify.sh` exit 0).
