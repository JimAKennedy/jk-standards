---
class: gated
---

# Configuration reference

Status: current (2026-07-28)

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

boundaries:                   # forbidden cross-directory references
  rules:
    - name: checks-must-not-import-cli
      from: src/jk_standards/checks   # directory scanned recursively
      forbid: 'jk_standards\.cli'     # regex a line MUST NOT match
      extensions: [".py"]             # files to scan; empty = all
      hint: a check must not reach back into the CLI

doc_coverage:                 # code no doc or docstring describes at all
  source_roots:               # trees the enumerator walks (Python or C++)
    - path: src/jk_standards
      extensions: [".py"]     # .py roots use the ast enumerator (default)
    - path: engine/src        # a C++ root needs the jk-standards[cpp] extra
      extensions: [".cpp", ".h"]   # C++ suffixes → tree-sitter-cpp enumerator
  doc_scopes:                 # dirs scanned for the whole-word "mention" signal
    - docs
    - site/src/content/docs
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

The `boundaries` section supplies the `boundaries` check with `rules`. Each
rule names a `from` directory (scanned recursively), a `forbid` regex a line
under it must not match, an optional `extensions` filter (empty scans every
file), an optional `name` shown on each finding, and an optional `hint`
explaining the boundary. `from` and `forbid` are required; a rule with neither
is meaningless. With no rules the check is skipped. See the
[checks reference](checks.md#boundaries) for the rule these fields tune.

The `doc_coverage` section tunes the `doc-coverage` check, which catches code
that no doc and no docstring describes at all. `source_roots` are the trees the
enumerator walks (each entry defaults to `.py` files); with none configured the
check has nothing to enumerate and trivially passes. A root whose entries carry
Python suffixes is walked with the `ast` enumerator, while a root with C++
suffixes (`.cpp`, `.cc`, `.cxx`, `.c++`, `.hpp`, `.hh`, `.hxx`, `.h++`, `.h`,
`.c`) is parsed with tree-sitter-cpp and enumerated by the public-declaration
heuristic — so the `engine/src` entry above adds C++ coverage alongside the
Python root. `doc_scopes` are the doc directories scanned for the whole-word
symbol "mention" OR-signal. Both fields default to empty, so the section is
optional.

An optional `module_min_percent` (an int in `[0, 100]`, unset by default) sets a
soft advisory floor: a module whose live documented-unit ratio falls below that
percentage emits a `::warning` (surfaced inline on the PR) and is tallied in the
check's summary line, but it is strictly advisory — it never fails the build. It
composes with, and is additive to, both the binary bare-module gate and the
per-module baseline ratchet (the ratchet's committed floor map lives at
`baselines/doc-coverage.json` and is recorded only through the
`doc-coverage --update-baseline` CLI flag; see below).

The C++ grammar is not a base dependency: install it with the optional extra,
`pip install jk-standards[cpp]`, which pulls in `tree-sitter` and
`tree-sitter-cpp`. When a C++ source root is configured but that extra is not
installed, the check degrades gracefully rather than failing — the C++ files
contribute zero units and a single summary line reports how many were skipped
and points at `jk-standards[cpp]`, so a grammar-less repo keeps working on the
zero-dependency default. See the [checks reference](checks.md#doc-coverage) for
the rule these fields tune.

## CLI

```
jk-standards <check-name> [--root DIR] [--config FILE] [--base REF]
jk-standards all            # every configured static check (+ doc-drift
                            # when --base or GITHUB_BASE_REF is available)
jk-standards list           # list check names
jk-standards emit <name>    # regenerate one drift-proof fixture under
                            # site/src/generated/; <name> is one of
                            # checks | config-schema | skills | coverage |
                            # doc-coverage | all
jk-standards emit <name> --check
                            # exit 1 if the on-disk fixture differs from
                            # what would be emitted now (CI drift gate)
jk-standards doc-coverage --update-baseline
                            # record/ratchet the per-module floor map at
                            # baselines/doc-coverage.json (never via emit, so
                            # a floor can never silently self-heal)
jk-standards doc-coverage --update-baseline --allow-regression
                            # with --update-baseline: permit a write that
                            # LOWERS an existing floor (refused otherwise)
```

`--update-baseline` and `--allow-regression` are check flags, not emit verbs:
they belong to `jk-standards doc-coverage`, and `--allow-regression` is valid
only alongside `--update-baseline`.

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
