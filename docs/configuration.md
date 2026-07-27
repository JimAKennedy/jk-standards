---
class: gated
---

# Configuration reference

Status: current (2026-07-25)

All project-specific surface lives in one file, `jk-standards.yaml`, at the
consuming repo's root (override with `--config`). Every key is optional; an
absent file yields defaults (doc root `docs/`, standard class vocabulary,
count-drift and behavioral-claims skipped because they need project input).

```yaml
version: 1

doc_roots:                    # where docs live; default: docs/ (*.md)
  - path: docs
    extensions: [".md"]
  - path: site/src/content/docs
    extensions: [".mdx"]

exempt_dirs:                  # prefix-matched; frozen dated records
  - docs/reviews/

taxonomy:
  classes: [generated, gated, archived]
  extra_files:                # root-level docs outside doc_roots
    - IMPLEMENTATION_PLAN.md

status_prose:
  forbidden_extra:            # project-specific banned phrases
    - pattern: 'Designed\s+For,\s+Not\s+Implemented'
      hint: forbidden section heading — describe current state or remove

file_line_refs:
  extensions: [cpp, h, hpp, py, mjs, ts, md]   # ref extensions to match
  source_roots:               # source trees whose comments are scanned
    - path: engine/src
      extensions: [".cpp", ".h"]

count_drift:
  triggers:                   # inventory-scoped regex phrases
    - 'factory\s+presets?'
    - 'chapters?\s+in\s+total'

drift_map: .github/docs-drift-map.yml

doc_drift:
  deps_only_manifests:        # package.json files whose deps-only version
    - site/package.json       # bumps (Dependabot) don't trigger mappings


generated:                    # regenerate-and-diff pairs
  - doc: docs/engine-spec.md
    command: node scripts/generate-param-docs.mjs

behavioral_claims:
  sources:                    # test-index scrapers
    - type: gtest             # gtest | js | pytest
      path: tests
    - type: pytest
      path: tests

action_pinning:               # GitHub Actions uses: must be SHA-pinned
  workflow_dir: .github/workflows   # default; scanned recursively
  extensions: [".yml", ".yaml"]     # workflow file extensions to scan

snippet_regions:              # doc→region references resolve to real markers
  doc_roots:                  # docs scanned; default: top-level doc_roots
    - path: docs
      extensions: [".md", ".mdx"]
  source_roots:               # trees searched for region:<name> markers
    - path: engine/src
      extensions: [".cpp", ".h", ".sh"]
  markers:                    # per-file-type marker comment prefixes
    - extensions: [".sql"]
      prefixes: ["--"]
```

The `action_pinning` section tunes the `action-pinning` check: `workflow_dir`
is the tree scanned recursively for workflow files (default
`.github/workflows`) and `extensions` are the filename suffixes treated as
workflow files (default `.yml`, `.yaml`). Both have working defaults, so the
section is optional.

The `snippet_regions` section tunes the `snippet-regions` check.
`source_roots` are the trees scanned for `region:<name>` markers that prose
mentions resolve against — with none configured, prose scanning is skipped
and only `<CodeSnippet>` references (which name their own `file=`) are
validated. `markers` maps file extensions to the comment prefixes a marker
may follow, overriding the built-in `//`, `#`, and `<!-- -->` forms.
`doc_roots` narrows which docs are scanned, defaulting to the top-level
`doc_roots`. Every field defaults, so the section is optional. See the
[checks reference](checks.md#snippet-regions) for the rule these fields tune.

## CLI

```
jk-standards <check-name> [--root DIR] [--config FILE] [--base REF]
jk-standards all            # every configured static check (+ doc-drift
                            # when --base or GITHUB_BASE_REF is available)
jk-standards list           # list check names
jk-standards emit <name>    # regenerate one drift-proof fixture under
                            # site/src/generated/; <name> is one of
                            # checks | config-schema | skills | coverage | all
jk-standards emit <name> --check
                            # exit 1 if the on-disk fixture differs from
                            # what would be emitted now (CI drift gate)
```

Exit codes: 0 clean, 1 violations, 2 usage/config error. Checks whose
config section is empty report themselves as skipped rather than failing —
adoption is incremental by design.

## Consuming

Pre-commit (pin to a release tag):

```yaml
- repo: https://github.com/JimAKennedy/jk-standards
  rev: v0.1.0
  hooks:
    - id: doc-taxonomy
    - id: status-prose
    - id: file-line-refs
```

CI (the reusable workflow supplies checkout depth and base-ref wiring):

```yaml
jobs:
  doc-discipline:
    uses: JimAKennedy/jk-standards/.github/workflows/doc-discipline.yml@v0.1.0
```
