---
class: plan
---

# M001 report — Version-addressed install

Status: current (2026-09-15)

Review record for milestone M001 of `docs/plans/install-upgrade/ledger.md`,
generated at the `/jk:auto` review gate. Next step: read this, then
`/jk:ship`.

**Vision:** A consuming repo moves to a new jk-standards release with one
command — `jk-standards install-skills v0.17.0` or `latest` — that verifies
the release exists before touching anything, then reinstalls and repins
atomically, decoupling the vendored-asset pin from the pip package version.

**Branch:** `milestone/M001-install-upgrade` (3 commits, plus the ledger
commit riding on local `main` beneath it — the PR range vs `origin/main`
carries both, the same shape as the two previous milestones).

## Slices

| Slice | Title | Rows | Status |
|---|---|---|---|
| M001/S01 | The version argument | R1–R9 done; N1–N3 accepted | done |

## Definition of done

All nine boxes checked in the ledger; none reworded mid-run.

## Validation

| Token | Result |
|---|---|
| format | exit 0 |
| unit | pytest: 550 passed, 1 skipped |
| emit-fresh | exit 0 |
| discipline | exit 0 |
| gate | verify.sh: all locally-runnable gates passed |

Plus both range-scoped arms post-commit over the full range:
`doc-drift --base main` (no mapped sources touched) and
`status-prose --base main` (accuracy arm ran, 14 files, no violations).

## Traceability

- `7f46cf3` plan: M001 slice plan and decisions — Slice: M001/S01
- `7fcd244` feat: version argument on install-skills/install-commands — Slice: M001/S01, Rows: R1,R2,R3,R4,R5,R7
- `f08554e` docs: version argument documented; changelog; slice done — Slice: M001/S01, Rows: R6,R8,R9

Beneath the branch on local `main`, untraced by design (pre-milestone):
`7b739e5` plan: install-upgrade delivery ledger.

## Things a reviewer should look at twice

- **Both-kinds atomicity was a front-loaded refinement, not in the chat
  design verbatim**: a version run reinstalls skills *and* commands
  whichever subcommand carries it, because the shared pin moving with only
  one kind's files would create the mixed-upstream-state the lock design
  forbids. Recorded in decisions with reasoning.
- **`upgrade_to_version` bypasses `install_skills`' hash verification
  deliberately** — an upgrade repins hashes from the freshly installed
  files; verifying against the old lock's hashes would reject every
  legitimate upgrade. `--check` afterwards verifies the new state.
- **The GitHub releases API call is unauthenticated by default** (the
  existing `GITHUB_TOKEN` header plumbing applies when set); heavy CI use
  could rate-limit. `latest` is a convenience path; the pinned form makes
  no API call beyond the archive fetch.
- **README's example pins `v0.17.0`** as the worked version literal — the
  same literal-drift RELEASE.md warns about; acceptable as an example, but
  it will read stale after future releases.

## Decisions (verbatim from M001-decisions.md)


# M001 decisions

Status: current (2026-09-15)

Append-only record per `/jk:auto`. The design was refined in conversation
(no input document) and approved verbatim by the user, who then instructed
"assess it straight into a ledger and run it" — that instruction is the
design approval and the run authorization for this milestone.

## 2026-09-15 — planning M001/S01

- **Q:** Proceed with the chat-approved design (explicit version argument
  with pre-mutation verification; `latest` via the releases API; skew note;
  `--update-lock` untouched)? — **A:** Yes — "assess it straight into a
  ledger and run it".
- **Decision:** Slice classified bounded — an addition to the existing
  installer flow, its parser, and its tests. — **Why:** no new subsystem.
- **Decision:** A version run moves **both asset kinds** (skills and
  commands) in one atomic operation, whichever subcommand carried the
  argument. — **Why:** forced by R2, not chosen: the pin is shared, so
  moving it while only one kind's files update would create the "mixture
  of upstream states" `resolve_ref`'s single-pin design exists to forbid.
- **Decision:** Verification-before-mutation is the archive download
  itself: fetch every governed asset's archive into memory first; any 404
  or network failure exits 2 with lock and disk untouched; files and the
  single lock write happen only after all fetches succeed. — **Why:** the
  fetch is the existence check — a separate HEAD probe would race it.
- **Decision:** `latest` queries `api.github.com/repos/<source>/releases/latest`
  for the single source shared by all version-governed entries; more than
  one distinct source among them → exit 2 naming them. — **Why:** the pin
  is one toolkit's version; a multi-source governed set is a config error,
  not something to guess through.
- **Decision:** Accepted argument forms: `vX.Y.Z` (stored in the lock
  without the `v`, matching `resolve_ref`'s `refs/tags/v{version}`
  composition) or the literal `latest`. Anything else → exit 2. —
  **Why:** N2; the per-entry `ref` field remains the arbitrary-ref hatch.
