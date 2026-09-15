---
class: plan
---

# M001 report — Deterministic guardrails

Status: current (2026-09-15)

Review record for milestone M001 of `docs/plans/skill-evals/ledger.md`,
generated at the `/jk:auto` review gate. The next step is a human reading
this and choosing `/jk:ship`.

**Vision:** A staged secret cannot enter a local commit, and a malformed or
asset-dangling skill cannot pass CI — with no LLM, no API key, and no new
cost anywhere in the gate.

**Branch:** `milestone/M001-deterministic-guardrails` (4 commits on top of
`main`).

## Slices

| Slice | Title | Status | Rows |
|---|---|---|---|
| M001/S01 | Secret-hygiene preflight | done | R0 done |
| M001/S02 | skill-lint check | done | R1, R2, R3 done |

## Definition of done

Every box in both slices is checked in the ledger. S01's second box was
reworded mid-slice (recorded below) to describe the sanctioned fallback
that actually landed; the outcome it states is demonstrated in evidence.

## Validation

| Slice | Token | Result |
|---|---|---|
| M001/S01 | format | exit 0 |
| M001/S01 | gate | scripts/verify.sh: 19 passed, 0 failed, 3 skipped |
| M001/S02 | format | exit 0 |
| M001/S02 | unit | pytest: 536 passed, 1 skipped |
| M001/S02 | emit-fresh | exit 0 |
| M001/S02 | discipline | jk-standards all: 0 violations |
| M001/S02 | gate | scripts/verify.sh: 19 passed, 0 failed, 3 skipped |

Evidence: `evidence/M001-S01.md`, `evidence/M001-S02.md` (the S01 rejection
demo — staged `sk-ant-` key, hook exit 1, rule `anthropic-api-key` — is
recorded there).

## Traceability

Every branch commit carries `Slice:` trailers; none are untraced:

- `883eb21` feat: register skill-lint — hook, docs, fixtures (M001/S02)
- `0052022` feat: skill_lint check module with per-violation-class tests (M001/S02)
- `cd3fbd5` feat: staged-files gitleaks gate in pre-commit (M001/S01)
- `940ae23` plan: M001 slice plans and decisions (skill-evals)

Two related commits sit on local `main`, not this branch, and are not yet
pushed — the branch is rebased on them:

- `0a1d018` chore: plan taxonomy class for delivery-programme docs
  (mid-run governance decision, recorded below)
- `a92c55f` plan: skill-evals delivery ledger from PROPOSAL-skill-evals.md

## Things a reviewer should look at twice

- **Shipped-hook defect (new finding):** the `secrets-scan` hook this repo
  ships in `.pre-commit-hooks.yaml` cannot build in any consumer —
  `language: golang` with no Go module and no `additional_dependencies`
  fails at environment install. This slice landed the sanctioned fallback
  for this repo; fixing the shipped hook needs its own row in a future
  pass.
- **DoD rewording on S01:** the original box named the local config; the
  approved fallback landed the hook in the dev config instead, and the box
  was reworded to match reality before ticking. Same agreed outcome.
- **Repo-wide governance change:** the `plan` taxonomy class and the
  doc-completeness exemption (commit `0a1d018` on main) affect all future
  docs under `docs/plans/` — it was an unanticipated mid-run question,
  answered interactively, not a silent judgment call.
- **ARCHITECTURE.md drift pair:** satisfied by a `Docs-Not-Affected`
  trailer on `883eb21` with the reason inline.

## Decisions (verbatim from M001-decisions.md)


# M001 decisions

Status: current (2026-09-15)

Append-only record of every question, answer, and choice made on the user's
behalf while planning and executing M001, per `/jk:auto`.

## 2026-09-15 — planning M001/S01 and M001/S02

- **Q:** Approve both slice designs and the recorded decisions (sh-only
  executable rule, hardcoded skills root, four violation classes only,
  gitleaks fallback order)? — **A:** Approve both.
- **Decision:** Both slices classified bounded — each changes a flow that
  already exists (the local pre-commit hook list; the check-registry
  pattern). — **Why:** no new subsystem, no interface change.
- **Decision:** S01 contingency order: try the shipped `secrets-scan` hook
  under `repo: .` first; if the `language: golang` environment cannot build
  (this repo has no Go module and the shipped entry declares no
  `additional_dependencies`), fall back to the upstream pinned
  `gitleaks/gitleaks` hook in `.pre-commit-config.yaml`. — **Why:** R0
  records exactly this fallback; a shipped-hook defect found on the way is a
  report note, not a slice widening.
- **Decision:** If gitleaks default rules miss an Anthropic-style key, add a
  `.gitleaks.toml` extending the default config. — **Why:** R0's outcome is
  "a staged Anthropic-style key fails a local commit", so detection of that
  pattern is in scope, not extra.
- **Decision:** skill-lint enforces exactly the four DoD violation classes:
  front-matter parseable with `name` matching the directory; description
  contains "Use when"; backtick-referenced same-directory script tokens
  (`*.sh`/`*.py`, no path separator) resolve to files; sibling `.sh` files
  are executable. No unreferenced-asset rule. — **Why:** matches the DoD;
  an unreferenced-asset rule is false-positive-prone and not in the DoD.
- **Decision:** `.py` assets exempt from the executable-bit rule. — **Why:**
  `skills/sdlc-retro/collect.py` has no exec bit and is invoked as
  `python collect.py` by its own skill body; requiring the bit fails today's
  tree for no gain.
- **Decision:** Skills root hardcoded to `skills/` (as `emit_skills()` does),
  graceful "skipped" summary when the directory is absent. — **Why:**
  consumer repos vendor skills elsewhere and must pass; avoiding a Config
  field keeps `config-schema.json` unchanged.
- **Decision:** Escape hatch is `skill-lint-ok: <reason>` on the offending
  line or the line above, mirroring `action-pinning`. — **Why:** the
  toolkit's uniform suppression discipline.
- **Decision:** S02 also updates
  `site/src/content/docs/reference/checks.mdx`, which the ledger row R2 does
  not name. — **Why:** the drift map pairs `checks/**` with all three of
  `docs/checks.md`, the README tables, and `reference/checks.mdx`; omitting
  the third fails `doc-drift` on the PR.
- **Decision:** No deferred questions; no boundary pauses planned. —
  **Why:** both slices' unknowns resolve by running commands, not by asking.

## 2026-09-15 — unanticipated question: docs/plans under doc governance

- **Q:** The tracked ledger and plan files fail `doc-completeness` (docs
  under a doc_root must be mapped or declared), and every future evidence
  file would fail on the commit creating it. New `plan` taxonomy class,
  `exempt_dirs`, or per-file registry entries? — **A:** New `plan` class.
- **Decision:** `plan` added to `taxonomy.classes` and to
  `doc_completeness.exempt_classes`; plans/evidence/decisions carry
  `class: plan`; the ledger stays `class: gated` per the ledger standard
  with one exact cannot_drift entry. Landed on `main` beside the ledger
  commit so that commit is not CI-red alone; milestone branch rebased on
  top. — **Why:** uses designed seams, keeps everything taxonomy-governed,
  and avoids a registry treadmill on every evidence file.

## 2026-09-15 — executing M001/S01

- **Decision:** Fallback path taken as planned: the shipped `secrets-scan`
  hook's golang environment cannot build under `repo: .` ("directory prefix
  . does not contain main module"), so the upstream `gitleaks/gitleaks`
  hook, pinned `v8.30.1`, landed in `.pre-commit-config.yaml`. — **Why:**
  step 2 of the plan prescribed exactly this on exactly this failure.
- **Decision:** S01's second DoD box and R0's cells reworded to describe
  the fallback outcome rather than the local-config placement. — **Why:**
  the approved design sanctioned the fallback but the DoD wording had not
  tracked it; ticking the old wording would have been false. Judgment call:
  same agreed outcome, corrected description.
- **Note for the report:** the shipped `secrets-scan` hook in
  `.pre-commit-hooks.yaml` is unusable by any consumer for the same reason
  (`language: golang`, no Go module, no `additional_dependencies`). Fixing
  it is outside this slice; it deserves its own row in a future pass.

## Addendum (2026-09-15, post-gate)

The shipped-hook defect flagged above was fixed at the user's request as
row R23 before shipping: stub `go.mod` + pinned `additional_dependencies`
make the shipped `secrets-scan` hook build in consumers (proven by a
simulated consumer repo), and this repo's local config now dogfoods it.
