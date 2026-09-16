---
class: plan
---

# Plan M001/S01 — The version argument

Status: current (2026-09-15)

**Slice:** M001/S01 — The version argument, in
`docs/plans/install-upgrade/ledger.md`

**Task status**

- [ ] Task 1 — upgrade flow in skills_install, tests first
- [ ] Task 2 — docs, changelog, and full gates

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

**Validation**

- `format` → `pre-commit run --all-files`
- `unit` → `pytest -q`
- `emit-fresh` → `jk-standards emit all --check`
- `discipline` → `jk-standards all`
- `gate` → `scripts/verify.sh`

## Task 1 — upgrade flow, tests first

Consumes: nothing. Produces: `upgrade_to_version()` in
`src/jk_standards/skills_install.py`, wired into both subcommand parsers.

1. Failing tests first in `tests/test_skills_install.py`, using its
   existing `_stub_urlopen(monkeypatch, handler)` seam and lock-fixture
   helpers (reuse whatever builder its install tests use). Cases, all
   offline:
   - `test_upgrade_missing_version_exits_2_lock_untouched` — handler
     raises the urllib HTTPError the real 404 produces; assert exit 2 and
     the lock file bytes unchanged, no asset files written.
   - `test_upgrade_success_single_lock_write` — handler serves a valid
     archive; assert `jkStandardsVersion` moved (stored without `v`),
     both asset kinds reinstalled, `computedHash` values match the new
     files, and the note that the write is one file write (assert final
     content; the single-write property is structural — lock is written
     once, after installs).
   - `test_upgrade_via_install_commands_entrypoint` — same success path
     through `commands_main(["v9.9.9", ...])`.
   - `test_upgrade_latest_resolves_releases_api` — handler returns a
     releases/latest JSON body with `tag_name`, then serves the archive;
     assert the pin equals the resolved version.
   - `test_upgrade_skew_note` — after a successful upgrade to a version
     differing from `__version__`, the output contains a note naming both
     and suggesting the pip upgrade, and the exit code is 0.
   - `test_upgrade_leaves_entry_with_own_ref_alone` — an entry carrying
     `ref` keeps it, is not re-fetched from the version tag, and
     `resolve_ref` still returns its own ref afterwards.
   - `test_upgrade_rejects_malformed_argument` — `install-skills 0.17`
     and `install-skills main` both exit 2 with a usage message, lock
     untouched.
   - `test_upgrade_multi_source_governed_entries_exit_2` — two governed
     entries with different `source` values → exit 2 naming both.
2. Run them, watch each fail for the right reason (missing function /
   parser rejecting the positional).
3. Implement in `src/jk_standards/skills_install.py`:
   - `VERSION_ARG_RE = re.compile(r"^v\d+\.\d+\.\d+$")` and a
     `resolve_latest(source) -> str` hitting
     `https://api.github.com/repos/{source}/releases/latest` through the
     existing `_fetch`, reading `tag_name`.
   - `upgrade_to_version(project_root, version_arg, skills_dir,
     commands_dir) -> int`: load lock; collect version-governed entries
     (those without `ref`) across both kinds; require exactly one
     distinct `source` among them (else exit 2); resolve `latest` if
     asked; validate the `vX.Y.Z` shape; **fetch the archive first** —
     any failure exits 2 before anything is written; then extract and
     install every governed skill and command (reusing `extract_skill` /
     `extract_file`, force semantics); recompute hashes; set
     `lock["jkStandardsVersion"]` to the version without `v`; write the
     lock once, last; print the skew note when the new pin differs from
     `__version__`.
   - Parsers: optional positional `version` (`nargs="?"`) on both
     `_build_parser` and `_build_commands_parser`, help text naming the
     two accepted forms; `main`/`commands_main` route to
     `upgrade_to_version` when present (mutually exclusive with
     `--check`/`--update-lock` — combining them exits 2).
   - Extend the module docstring's usage block with the two new
     invocations.
4. Run the new tests green, then `pytest -q` full, `ruff check .`,
   `ruff format --check .`.
5. Evidence, tick this box, `jk-standards ledger`, one commit with
   trailers `Slice: M001/S01`, `Rows: R1,R2,R3,R4,R5,R7`, plus a
   `Docs-Not-Affected:` trailer for the ARCHITECTURE.md pair if doc-drift
   maps `skills_install.py` (it currently does not — verify, and omit the
   trailer if nothing fires).

Check that closes the task: `unit` (`pytest -q` exit 0).

## Task 2 — docs, changelog, gates

Consumes: Task 1's behavior. Produces: the documented, gated feature.

1. Describe the version argument and `latest` in the consumption prose of
   `README.md`, `docs/skills.md`, `docs/configuration.md`, and
   `site/src/content/docs/reference/configuration.mdx`, in each file's
   existing style — including the move-vs-bless distinction against
   `--update-lock` (R6's doc half). Refresh the Status anchors of the
   gated docs touched.
2. Add the changelog entry under a fresh `## [Unreleased]` heading.
3. Re-emit anything staled (`emit doc-coverage` at minimum — new src
   functions shift the inventory).
4. Run every token: `format`, `unit`, `emit-fresh`, `discipline`, `gate`,
   plus `doc-drift --base main` and `status-prose --base main`.
5. Evidence, tick this box and every DoD box, rows R6, R8, R9 done,
   slice and milestone `done`, `jk-standards ledger`, one commit with
   trailers `Slice: M001/S01`, `Rows: R6,R8,R9`.

Check that closes the task: `gate` (`scripts/verify.sh` exit 0).
