---
class: plan
---

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

## 2026-09-15 — post-gate follow-up: shipped secrets-scan hook (R23)

- **Q:** Fix the shipped hook via a stub `go.mod` plus
  `additional_dependencies`, or drop the id and document gitleaks'
  upstream hook? — **A:** Stub `go.mod` + dependency.
- **Decision:** `go.mod` stub (commented, no Go code) at the repo root;
  `additional_dependencies: ["github.com/zricethezav/gitleaks/v8@v8.30.1"]`
  on the shipped hook — the module path is the historical zricethezav one,
  verified from the tag's own go.mod, not guessed. Local config gains
  `- id: secrets-scan` to dogfood the consumer path; the dev config's
  upstream hook stays as the developers' daily gate. — **Why:** pre-commit's
  golang language runs `go install ./...` unconditionally (verified in its
  source), so the repo must be a valid module; the one-stop adoption surface
  is worth the two-line stub.
