---
class: plan
---

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
