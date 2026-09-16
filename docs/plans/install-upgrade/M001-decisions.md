---
class: plan
---

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
