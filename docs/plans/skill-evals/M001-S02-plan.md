---
class: plan
---

# Plan M001/S02 — skill-lint check

Status: current (2026-09-15)

**Slice:** M001/S02 — skill-lint check, in
`docs/plans/skill-evals/ledger.md`

**Task status**

- [ ] Task 1 — skill_lint module with failing-first pytest coverage
- [ ] Task 2 — registry, hook id, docs, and regenerated fixtures

**Definition of Done**

- [ ] `skill-lint` is registered in `CHECKS` and `STATIC_CHECKS`
- [ ] Each violation class — name/dir mismatch, missing trigger phrasing,
      dangling asset, non-executable script — has a pytest case that fails
      without the check and passes with it
- [ ] The hook id ships in `.pre-commit-hooks.yaml`
- [ ] `docs/checks.md` and the README check tables describe the check
- [ ] Regenerated `site/src/generated/checks.json` is committed

**Validation**

- `format` → `pre-commit run --all-files`
- `unit` → `pytest -q`
- `emit-fresh` → `jk-standards emit all --check`
- `discipline` → `jk-standards all`
- `gate` → `scripts/verify.sh`

## Task 1 — skill_lint module with failing-first pytest coverage

Consumes: nothing. Produces: `src/jk_standards/checks/skill_lint.py` with a
`run(root, cfg) -> int` callable Task 2 registers.

1. Write the failing tests first, in `tests/test_checks.py`, following its
   existing `write(tmp_path, path, content)` + `check.run(tmp_path, Config())`
   pattern. Import `skill_lint` alongside the other check imports. Cases:
   - `test_skill_lint_clean_skill_passes` — `skills/good/SKILL.md` with
     front-matter `name: good`, a description containing "Use when", body
     referencing no assets → expect 0.
   - `test_skill_lint_name_dir_mismatch_flagged` — `name: other` under
     `skills/good/` → expect 1.
   - `test_skill_lint_missing_frontmatter_flagged` — SKILL.md with no
     front-matter block → expect 1.
   - `test_skill_lint_missing_trigger_flagged` — description without
     "Use when" → expect 1.
   - `test_skill_lint_dangling_asset_flagged` — body references
     `` `helper.sh` `` with no such sibling file → expect 1.
   - `test_skill_lint_existing_asset_passes` — body references
     `` `helper.sh` ``, sibling exists with exec bit
     (`path.chmod(0o755)`) → expect 0.
   - `test_skill_lint_nonexecutable_sh_flagged` — sibling `helper.sh`
     exists mode 0o644, referenced or not → expect 1.
   - `test_skill_lint_py_asset_needs_no_exec_bit` — referenced sibling
     `helper.py` mode 0o644 → expect 0.
   - `test_skill_lint_pathed_reference_ignored` — body references
     `` `tests/foo.py` `` (path separator) with no such file → expect 0.
   - `test_skill_lint_marker_exempts` — dangling `` `helper.sh` `` with
     `<!-- skill-lint-ok: doc example -->` on the same line → expect 0.
   - `test_skill_lint_no_skills_dir_skips` — empty tmp_path → expect 0.
2. Run `pytest -q tests/test_checks.py -k skill_lint` — every case must
   fail with ImportError/AttributeError (module absent), the right reason.
3. Implement `src/jk_standards/checks/skill_lint.py` in the house style
   (module docstring stating rule, scope, escape hatch; `output.error(rel,
   lineno, msg)` per finding; `output.summary(...)` when clean):
   - Scope: `root / "skills"` — absent dir prints a "skipped" summary,
     returns 0.
   - For each `skills/*/SKILL.md`: parse leading `---` front-matter with
     `yaml.safe_load`; unparseable or missing → one error. `name` differing
     from the directory name → error. `description` lacking the substring
     "Use when" → error.
   - Reference rule: every backtick-quoted token in the body matching
     `^[A-Za-z0-9_.-]+\.(sh|py)$` (no path separator) must exist in the
     skill's directory → else "dangling asset" error at that line.
   - Executable rule: every sibling `*.sh` in the skill directory must have
     the owner-executable bit → else error. `.py` files exempt.
   - Suppression: `skill-lint-ok` marker on the offending line or the line
     above suppresses that finding (front-matter findings anchor to the
     `name:`/`description:` line; absent front-matter anchors to line 1).
4. Run the skill-lint tests, watch them pass. Run the module against the
   real tree — `python -c` calling `skill_lint.run` on the repo root — and
   confirm 0 findings across all skills.
5. Run `pytest -q` (full suite) and `ruff check . && ruff format --check .`;
   both must be green.
6. Append evidence to `evidence/M001-S02.md` (`unit` result, real-tree run
   result, date), tick this task's box, run `.venv/bin/jk-standards ledger`,
   commit as one unit with trailers `Slice: M001/S02`, `Rows: R1`.

Check that closes the task: `unit` (`pytest -q` exit 0).

## Task 2 — registry, hook id, docs, and regenerated fixtures

Consumes: `skill_lint.run` from Task 1. Produces: the check reachable via
CLI, hooks, and docs; fixtures fresh.

1. Register: add `skill_lint` to the import block and `CHECKS` dict in
   `src/jk_standards/checks/__init__.py` as `"skill-lint"`. It joins
   `STATIC_CHECKS` automatically (that list is derived). Order: keep the
   dict's existing grouping, appending after `release-pins`.
2. Hook: add to `.pre-commit-hooks.yaml`, wrapped in
   `# region:hook-skill-lint` / `# endregion:hook-skill-lint` markers like
   its neighbours: id `skill-lint`, name "skills carry valid front-matter,
   triggers, and assets", entry `jk-standards skill-lint`,
   language python, `pass_filenames: false`, `types_or: [markdown]`.
3. Docs, matching each file's existing per-check format: a `## skill-lint`
   section in `docs/checks.md` (rule, mechanism, escape hatch); a row in
   each README check table that lists per-check inventory; a matching entry
   in `site/src/content/docs/reference/checks.mdx` (the drift map pairs all
   three with `checks/**`).
4. Regenerate: `.venv/bin/jk-standards emit all`, commit the changed
   `site/src/generated/checks.json` (and any doc-coverage refresh the new
   module causes).
5. Verify reachability: `.venv/bin/jk-standards skill-lint --root .` exits
   0 with the summary line; `.venv/bin/jk-standards all --root .` includes
   skill-lint output and exits 0.
6. Run every validation token: `format`, `unit`, `emit-fresh`,
   `discipline`, `gate`. All exit 0.
7. Append evidence (each token, result, date), tick this task's box, tick
   the slice DoD boxes, set rows R2 and R3 and the slice `done`, run
   `.venv/bin/jk-standards ledger`, commit as one unit with trailers
   `Slice: M001/S02`, `Rows: R2,R3`.

Check that closes the task: `gate` (`scripts/verify.sh` exit 0).
