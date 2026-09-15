---
class: plan
---

# M001 report — Spec-system split

Status: current (2026-09-15)

Review record for milestone M001 of `docs/plans/openspec-split/ledger.md`,
generated at the `/jk:auto` review gate. The next step is a human reading
this and choosing `/jk:ship`.

**Vision:** A consuming repo runs the jk delivery loop against an external
spec system with a clean ownership split — the spec owns the *what*, the
ledger owns the *how and proof* — and the spec's own task checklist is a
mirror the loop keeps true, from its creation at assess to its verification
at close.

**Branch:** `milestone/M001-openspec-split` (5 commits on top of `main`,
which already carries the ledger commit).

## Slices

| Slice | Title | Rows | Status |
|---|---|---|---|
| M001/S01 | The contract | R6, R7 done | done |
| M001/S02 | The commands | R1–R5, R8–R11 done; O1–O4 accepted | done |

## Definition of done

Every box in both slices is checked in the ledger; none were reworded
mid-run.

## Validation

| Slice | Token | Result |
|---|---|---|
| M001/S01 | format | exit 0 |
| M001/S01 | unit | pytest: 542 passed, 1 skipped |
| M001/S01 | emit-fresh | exit 0 |
| M001/S01 | discipline | exit 0 |
| M001/S01 | gate | verify.sh: all locally-runnable gates passed |
| M001/S02 | format | exit 0 |
| M001/S02 | discipline | exit 0 |
| M001/S02 | gate | verify.sh: all locally-runnable gates passed |

Both slices additionally ran the two range-scoped arms CI would otherwise
catch first (learned in skill-evals M001): `doc-drift --base main` (6
mappings triggered, satisfied) and `status-prose --base main` (accuracy arm
ran, no violations).

## Traceability

Every branch commit carries `Slice:` lines; none are untraced:

- `aae7757` plan: M001 slice plans and decisions — Slice: M001/S01, M001/S02
- `e6fece6` feat: ledger check resolves single-token Source paths — Slice: M001/S01, Rows: R7
- `3bf3287` docs: Source contract in the ledger standard — Slice: M001/S01, Rows: R6
- `8390e64` feat: two-mode assess and the availability notice — Slice: M001/S02, Rows: R1,R2,R11
- `4bee0ab` feat: the loop honors the mirror — plan, ship, close, docs — Slice: M001/S02, Rows: R3,R4,R5,R8,R9,R10

## Things a reviewer should look at twice

- **OpenSpec facts are point-in-time.** Install/init/archive commands were
  fetched from the OpenSpec README on 2026-09-15 and cited as such in the
  prose; OpenSpec's surface is visibly mid-rename (`/opsx:archive` in
  current docs, `openspec archive <id>` in the originating consuming
  repo), and both forms are named. A future OpenSpec rename will stale
  these lines with no gate to catch it — external prose has no drift map.
- **Changelog written in S02, not deferred to ship** — a deliberate,
  recorded deviation so the slice's DoD box was closeable at this gate;
  ship's docs-sync will find its entry already present.
- **`emit all` currently aborts in the coverage emitter** on this machine
  (`coverage json` exit 2 — no `.coverage` data file; something earlier
  cleaned it). Deterministic emitters were run individually and
  `emit all --check` is unaffected. Pre-existing condition, not introduced
  by this branch; worth a `rm`-and-regenerate or a tolerant emitter later.
- **The three assess-time decisions** (granularity contract, assess feeding
  the spec system, R11 scoping) live in the ledger itself, not just the
  decisions file — they are contract, not incident.

## Decisions (verbatim from M001-decisions.md)


# M001 decisions

Status: current (2026-09-15)

Append-only record of every question, answer, and choice made on the user's
behalf while planning and executing M001 (openspec-split), per `/jk:auto`.
The three assess-time decisions (granularity contract, assess feeding the
spec system, R11 scoping) are recorded in the ledger itself.

## 2026-09-15 — planning M001/S01 and M001/S02

- **Q:** Approve both designs (Source path-detection = single
  whitespace-free token; OpenSpec commands as fetched and cited; both
  archive forms named; changelog written in S02 rather than deferred to
  ship)? — **A:** Approve both.
- **Decision:** Both slices classified bounded — a check-registry-pattern
  addition plus edits to existing governed docs and command prose. —
  **Why:** no new subsystem or interface.
- **Decision:** `Source:` path detection: in the pre-milestone region, a
  `**Source:**` line whose same-line value is a single whitespace-free
  token is a repo-relative path and must exist as a file or directory;
  any value containing whitespace is prose and skipped; the `ledger-ok`
  hatch suppresses. — **Why:** both existing ledgers carry prose Source
  lines (one naming a deliberately deleted file) that must stay legal,
  while a bare `openspec/changes/<id>/` gets checked.
- **Decision:** OpenSpec facts in command prose come from the OpenSpec
  README as fetched 2026-09-15 — install
  `npm install -g @fission-ai/openspec@latest`, init `openspec init`,
  changes in `openspec/changes/<id>/` (proposal.md, specs/, design.md,
  tasks.md), creation workflow-driven (`/opsx:propose`), archival
  `/opsx:archive` — with `openspec archive <id>` also named because the
  originating consuming repo uses that form. No `validate --strict`
  appears in current docs, so prose says "validate with the spec system's
  tooling where it provides it" rather than naming a flag. — **Why:**
  never fabricate a command; OpenSpec's surface is visibly mid-rename.
- **Decision:** S02's final task writes the `[Unreleased]` changelog entry
  itself instead of deferring to `/jk:ship`'s docs-sync. — **Why:** the
  slice's DoD includes the entry, and a DoD box a later command owes would
  leave the slice unclosable at auto's gate.
- **Decision:** ARCHITECTURE.md drift pair for the `ledger.py` edit is
  satisfied by a `Docs-Not-Affected` trailer. — **Why:** same reasoning
  as skill-evals M001: the doc describes the registry structurally and
  enumerates no per-check behavior; precedent recorded there.
- **Decision:** No deferred questions; no boundary pauses planned. —
  **Why:** the one external unknown (OpenSpec's current commands) was
  resolved by fetching its docs during planning.
