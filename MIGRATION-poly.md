# Poly migration notes

Changes required in `JimAKennedy/poly` to consume jk-standards instead of
its local copies of the discipline machinery, and to replace its legacy
project-local skill layout with the skills-lock mechanism (as used in
nfr-review). Written during the extraction; execute as two PRs after
jk-standards is pushed and tagged `v0.1.0`.

## PR 1 — adopt the toolkit, delete the local scripts

### 1. Add `jk-standards.yaml` to poly's root

Mapping of the current script behavior onto toolkit config:

```yaml
version: 1

doc_roots:
  - path: docs
    extensions: [".md"]
  - path: site/src/content/docs
    extensions: [".mdx"]

exempt_dirs:
  - docs/reviews/          # dated reviews: frozen, line refs pinned by date

taxonomy:
  classes: [generated, gated, archived]
  extra_files:
    - IMPLEMENTATION_PLAN.md   # root-level historical planning doc

status_prose:
  forbidden_extra:
    - pattern: 'Designed\s+For,\s+Not\s+Implemented'
      hint: forbidden section heading — describe current state or remove
    - pattern: 'TODO\(spike\)\s+markers?\s+remain'
      hint: progress claim — belongs in generated dashboard

file_line_refs:
  extensions: [cpp, h, hpp, mjs, ts, astro, mdx, md, sh, js]
  source_roots:
    - path: engine/src
      extensions: [".cpp", ".h", ".hpp"]
    - path: engine/include
      extensions: [".h", ".hpp"]
    - path: plugin/source
      extensions: [".cpp", ".h", ".hpp"]

count_drift:
  triggers:
    - 'factory\s+presets?'
    - 'presets?\s+(?:in\s+total|total|shipped|are\s+grouped|exist)'
    - 'presets?\s+across\s+\d+\s+categor'
    - 'of\s+the\s+presets?'
    - 'presets?\s+built\s+into'
    - 'categories?\s+(?:total|in\s+total)'
    - 'chapters?\s+(?:total|in\s+total)'
    - '(?:the|all)\s+categories'

drift_map: .github/docs-drift-map.yml   # existing file, format-compatible

doc_drift:
  deps_only_manifests:        # parity with poly PR #140: Dependabot version
    - site/package.json       # bumps must not trigger the testing-strategy
    - webui/package.json      # mapping (dependabot.yml landed in PR #130)

generated:
  - doc: site/src/content/docs/appendix-parameters.mdx
    command: node scripts/generate-param-docs.mjs
  - doc: docs/engine-spec.md
    command: node scripts/generate-param-docs.mjs
  - doc: webui/bridge-schema.md
    command: node scripts/generate-bridge-schema-doc.mjs
  - doc: site/src/content/docs/appendix-euclidean-reference.mdx
    command: node scripts/generate-euclidean-appendix.mjs

behavioral_claims:
  sources:
    - type: gtest
      path: tests
    - type: js
      path: site/tests
    - type: js
      path: site/tests-e2e
```

Notes on semantic deltas from the original scripts (verify in the parity
run):

- The count-drift spelled-number list drops poly's `forty-three`
  special case (compound spelled numbers beyond the tens words aren't
  matched). If a doc relies on it, prefer `{counts.x}` interpolation anyway.
- Marker vocabulary is unchanged (`[file-line-ok]`, `counts-ok`,
  `[verified: …]`, `[⚠ unverified]`, `Docs-Not-Affected:` trailer), so no
  doc edits are needed.
- `check-generated-docs.sh`'s params.json bootstrap (`generate-params-json`
  when missing) must move into the generator scripts themselves or a CI
  step before `jk-standards all` — the toolkit runs the configured command
  as-is.
- The pytest citation format is new capability; poly doesn't use it.

### 2. Delete superseded scripts

- `scripts/check-doc-taxonomy.sh`
- `scripts/check-doc-drift.sh`
- `scripts/check-count-drift.sh`
- `scripts/check-status-prose.mjs`
- `scripts/check-file-line-refs.mjs`
- `scripts/check-behavioral-claims.mjs`
- `scripts/check-generated-docs.sh` (replaced by `generated:` config)

**Keep** (project-specific, not extracted in v0.1.0):
`check-snippet-regions.sh` (phase-2 extraction candidate),
`check-realtime-safety.sh`, `check-pragma-once.sh`,
`check-bridge-schema-coverage.mjs`, `check-site-assets.sh`,
`check-sample-manifest.sh`, `check-wasm-freshness.sh`, all `generate-*.mjs`
generators, `site-verify-*.sh`, `pre-push-check.sh`.

Licensing: poly is GPL-3.0-only; the toolkit re-implements the checks under
Apache-2.0 (same sole author). Deleting the GPL script copies keeps a
single canonical implementation.

### 3. CI wiring (`.github/workflows/ci.yml`)

- `site-lint` job: replace the six deleted script invocations with
  `pip install "git+https://github.com/JimAKennedy/jk-standards@v0.1.0"`
  then `jk-standards all`. The remaining project-specific scripts stay as
  separate steps.
- `doc-drift` job: delete — `jk-standards all` runs doc-drift when
  `GITHUB_BASE_REF` is set (pull_request events), matching the old job's
  `if:` condition. Keep `fetch-depth: 0` on the site-lint checkout (needed
  for merge-base and trailer scanning).
- `site-e2e` job: drop its `check-generated-docs.sh` step (now covered by
  `generated:` in site-lint).
- `ci-complete`: update the `needs:` list for the removed `doc-drift` job.
- Run one parity PR with old and new checks side by side before deleting,
  and diff their findings.

### 4. Pre-commit (`.pre-commit-config.yaml`)

Add above the local hooks:

```yaml
- repo: https://github.com/JimAKennedy/jk-standards
  rev: v0.1.0
  hooks:
    - id: doc-taxonomy
    - id: status-prose
    - id: file-line-refs
```

Add the three ids to `ci: skip:` (they run via the GitHub job instead of
pre-commit.ci, same as the existing local hooks).

### 5. CLAUDE.md / docs updates

- Update any mention of the deleted script names to reference
  `jk-standards` (CLAUDE.md's Pre-Push Quality Gate section references only
  kept scripts, so it likely needs no change — verify).
- `docs/pr-af-review.md` drift-map entry and the map file itself are
  unchanged.

## PR 2 — skills: replace legacy layout with the lock mechanism

Current state: one legacy project-local skill, `.claude/skills/poly-site/`
(tracked). Target state mirrors nfr-review's convention: project-authored
skills tracked; portfolio skills vendored via lock file and gitignored.

1. **Add `skills-lock.json`** at poly's root:

```json
{
  "version": 1,
  "skills": {
    "doc-anti-drift": {
      "source": "JimAKennedy/jk-standards",
      "sourceType": "github",
      "skillPath": "skills/doc-anti-drift/SKILL.md",
      "computedHash": "<sha256 of the tagged SKILL.md>"
    },
    "escape-hatch-discipline": {
      "source": "JimAKennedy/jk-standards",
      "sourceType": "github",
      "skillPath": "skills/escape-hatch-discipline/SKILL.md",
      "computedHash": "<sha256>"
    },
    "sanitizer-ci-setup": {
      "source": "JimAKennedy/jk-standards",
      "sourceType": "github",
      "skillPath": "skills/sanitizer-ci-setup/SKILL.md",
      "computedHash": "<sha256>"
    }
  }
}
```

Compute hashes with `sha256sum skills/*/SKILL.md` at the pinned tag, or run
the installer once and `--update-lock`.

2. **Vendor the installer**: copy jk-standards `scripts/install_skills.py`
   into poly's `scripts/`. Install with
   `python scripts/install_skills.py --dest .claude/skills` so Claude Code
   discovers the skills (nfr-review uses the `.agents/skills` default; poly
   keeps `.claude/skills` because that's its existing discovery path —
   pick one convention portfolio-wide later).

3. **Gitignore vendored skills, keep project-authored ones tracked**:

```gitignore
.claude/skills/doc-anti-drift/
.claude/skills/escape-hatch-discipline/
.claude/skills/sanitizer-ci-setup/
```

`.claude/skills/poly-site/` stays tracked — it is poly-specific authored
content, not vendored.

4. **Gitleaks**: add `skills-lock.json` to `.gitleaks.toml`'s allowlist
   (the sha256 values pattern-match as secrets; nfr-review's config has the
   same allowlist for the same reason).

5. **CLAUDE.md**: add a short "Skills" section documenting the lock file,
   the install command, and the tracked-vs-vendored split.

6. Optional CI guard: a step running
   `python scripts/install_skills.py --check --dest .claude/skills` (fails
   on hash drift) — mirrors how nfr-review keeps vendored skills honest.

## Follow-ups recorded during extraction (not required for migration)

- Extract `check-snippet-regions.sh` (docs↔source region markers) as a
  jk-standards check — needs a component-tag parser, deferred from v0.1.0.
- nfr-review companion rules (detect this discipline in arbitrary repos) —
  tracked separately in the nfr-review backlog discussion.
- poly gaps found during the review, independent of this migration: wire
  `BUILD_FUZZ_TESTS` into a nightly CI job; add a clang-tidy CI invocation;
  consider RealtimeSanitizer alongside the grep-based RT-safety check.
