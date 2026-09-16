---
class: gated
---

# Install Upgrade Ledger

Status: current (2026-09-15)

**Source:** conversation-refined design (2026-09-15); no input document —
the assess conversation is recorded in M001-decisions.md. The repo runs no
spec system, so per the assess command's proposal mode this ledger was
produced plain, with the install notice printed once.

## Milestone M001 — Version-addressed install

**Vision:** A consuming repo moves to a new jk-standards release with one
command — `jk-standards install-skills v0.17.0` or `latest` — that verifies
the release exists before touching anything, then reinstalls and repins
atomically, decoupling the vendored-asset pin from the pip package version.
**Branch:** milestone/M001-install-upgrade
**Status:** planned

### Slice M001/S01 — The version argument

**Validation:** format, unit, emit-fresh, discipline, gate
**Evidence:** evidence/M001-S01.md
**Status:** open

**Definition of Done**

- [ ] `install-skills vX.Y.Z` verifies the ref exists before any mutation;
      a nonexistent version exits 2 with the lock byte-identical
- [ ] A successful run moves `jkStandardsVersion`, reinstalls the lock's
      assets at the new ref, and rewrites version and hashes in a single
      lock write performed last — a failed download can never leave a
      version pointing at hashes it did not produce
- [ ] `install-commands` accepts the same argument against the shared pin
- [ ] `latest` resolves through the GitHub releases API — the published
      Release, not the newest tag, is the authority (this repo's own
      tag/no-Release history is the argument)
- [ ] A lock pin differing from the CLI's `__version__` prints a skew
      note naming both and suggesting the pip upgrade — never an error
- [ ] Entries carrying their own `ref` are untouched by the version
      argument, locked by a test
- [ ] `--update-lock` behavior is unchanged (its existing tests pass
      unmodified) and the docs state the distinction: the version argument
      means "move to upstream release X"; `--update-lock` means "bless
      what is on disk"
- [ ] The four hand-maintained docs naming `install-skills` (README,
      `docs/skills.md`, `docs/configuration.md`,
      `reference/configuration.mdx`) describe the argument; Status anchors
      refreshed
- [ ] The changelog carries the entry under a fresh `[Unreleased]` section

| ID | Item | Lands in | Verification | Status |
|---|---|---|---|---|
| R1 | Explicit version argument with pre-mutation verification: check the ref upstream first; missing version → exit 2, lock untouched | `src/jk_standards/skills_install.py` | offline pytest via the `_stub_urlopen` seam: 404 path asserts exit 2 and byte-identical lock | `open` |
| R2 | Atomic apply: download/extract/verify at the new ref, recompute hashes, one lock write (version + hashes) performed last | `src/jk_standards/skills_install.py` | offline pytest: success path asserts new pin + new hashes in one write; failure mid-download leaves the lock unchanged | `open` |
| R3 | `install-commands` accepts the same argument; one shared pin governs both asset kinds | `src/jk_standards/skills_install.py` | offline pytest driving the commands entrypoint with a version argument | `open` |
| R4 | `latest` resolves via the GitHub releases API (`releases/latest`), then proceeds as R1/R2 | `src/jk_standards/skills_install.py` | offline pytest stubbing the releases API response | `open` |
| R5 | Version-skew note when the lock pin differs from the CLI `__version__` — informational, never a failure | `src/jk_standards/skills_install.py` | offline pytest asserts the note text and exit 0 | `open` |
| R6 | `--update-lock` unchanged; docs state the move-vs-bless distinction. Rescoped from design: no code change owed, only the doc sentence and the existing tests staying green | `src/jk_standards/skills_install.py` docstring, docs | existing `test_update_lock_*` cases pass unmodified | `open` |
| R7 | Per-entry `ref` escape hatch (already in `resolve_ref`) is untouched by the version argument | `src/jk_standards/skills_install.py` | pytest: an entry with its own `ref` still resolves to it after a version-argument run | `open` |
| R8 | Doc sync: README consumption section, `docs/skills.md`, `docs/configuration.md`, `reference/configuration.mdx`; Status anchors refreshed | those four files | `status-prose --base main` accuracy arm green; prose describes both the version argument and `latest` | `open` |
| R9 | Changelog entry under a fresh `[Unreleased]` section (0.17.0 consumed the previous one) | `CHANGELOG.md` | entry present in the file's style | `open` |
| N1 | No automatic pip upgrade of the jk-standards package — the skew note nudges; the decoupling is the feature, and package management belongs to the consumer | — | recorded as a deliberate non-goal | `accepted` |
| N2 | The argument accepts only `vX.Y.Z` or `latest` — no branches, no arbitrary refs; the per-entry `ref` field remains the escape hatch for that | — | recorded as a deliberate non-goal | `accepted` |
| N3 | No lock-format change — `jkStandardsVersion` and `computedHash` fields as they are | — | recorded as a deliberate non-goal | `accepted` |

## Sequencing

Single slice; no dependencies.
