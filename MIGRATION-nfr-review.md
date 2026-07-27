# nfr-review migration notes

Changes required in `JimAKennedy/nfr-review` to retire its vendored
`scripts/lint_docs.py` by adopting jk-standards for the portable subset of
its doc checks. `lint_docs.py` runs three checks; two are regex/diff-level
and map 1:1 onto shipped toolkit checks, and one is registry-specific and
stays in nfr-review. Execute as one PR after jk-standards is pushed and
tagged `v0.2.0`.

The mapping below is proven by reproducible fixtures in
`tests/test_checks.py` (the `nfr-review parity` block) — the toolkit
produces the same pass/fail behavior `lint_docs.py` produces on the same
tree, without either repo depending on the other's checkout.

## lint_docs.py check inventory

| lint_docs.py check | Portable? | jk-standards check |
|---|---|---|
| #1 rules.json length == rule_registry length | No | — (retained residual, see below) |
| #2 `<CodeSnippet region=…>` markers resolve to a real `region:<name>` in the rule-registry source | Yes | snippet-regions |
| #3 compliance.mdx `**N rules**` numeral matches the compliance mapping | Yes | count-drift (`rules\b` trigger) |

## PR — adopt the toolkit, retire the portable checks

### 1. Add `jk-standards.yaml` to nfr-review's root

Mapping of the two portable `lint_docs.py` checks onto toolkit config:

```yaml
version: 1

# Check #3: compliance.mdx "**N rules**" drifts from the rule registry the
# moment a rule is added or removed. count-drift flags a bare numeral in
# front of a `rules` noun; the fix is `{counts.rules}` interpolation from the
# generated source of truth, or a `<!-- counts-ok: … -->` escape hatch for a
# worked example.
doc_roots:
  - path: docs
    extensions: [".mdx"]

count_drift:
  triggers:
    - 'rules\b'

# Check #2: <CodeSnippet region=…> in the compliance docs must point at a
# real `region:<name>` marker in the rule-registry source tree; a dangling
# reference is flagged with file:line. The escape hatch is
# `# snippet-region-ok: <reason>`.
snippet_regions:
  doc_roots:
    - path: docs
      extensions: [".mdx"]
  source_roots:
    - path: rules
      extensions: [".ts"]
```

Notes on semantic deltas from `lint_docs.py` (verify in the parity run):

- count-drift's `rules\b` trigger fires on any bare numeral immediately
  preceding the word `rules` in a scanned doc — broader than lint_docs.py's
  single hard-coded compliance.mdx line. Use `{counts.rules}` interpolation
  or a scoped `counts-ok` marker where a literal numeral is intentional.
- snippet-regions resolves `<CodeSnippet file="…" region="…" />` against the
  configured `source_roots` union and also matches prose `region:<name>`
  mentions. `lint_docs.py` only understood the MDX `<CodeSnippet>` form, so
  the toolkit is a strict superset — no compliance-doc edits are needed.
- Region markers default to `//`, `#`, and `<!-- -->` comment prefixes. The
  rule registry is TypeScript, so the defaults already cover it; add a
  `snippet_regions.markers` block only if a new source file type needs an
  unusual prefix.
- The toolkit does **not** re-implement check #1 (see below) — that stays in
  nfr-review.

### 2. Retire the portable checks in `scripts/lint_docs.py`

Delete lint_docs.py checks #2 and #3 (and any helper code only they use).
The vendored `scripts/lint_docs.py` deletion — once check #1 has its own
home — is tracked as a follow-up PR:

- Follow-up PR (deletes `scripts/lint_docs.py`): _<link to be recorded once opened in JimAKennedy/nfr-review>_

Until that PR lands, run one parity commit with `lint_docs.py` and
`jk-standards all` side by side and diff their findings before removing the
superseded check code.

### 3. Retained residual — check #1 stays in nfr-review

lint_docs.py check #1 (`rules.json` length == `rule_registry` length) is a
registry-integrity assertion, not a doc-drift regex: it compares two
in-repo data structures specific to nfr-review's rule model. It is **not
portable** to a generic toolkit check and is intentionally kept in
nfr-review (as a slimmed `lint_docs.py` or a small dedicated script). The
count-drift check above covers the *prose* numeral; check #1 covers the
*data* invariant — they are complementary, not redundant.

### 4. CI wiring (`.github/workflows/`)

- Add `pip install "git+https://github.com/JimAKennedy/jk-standards@v0.2.0"`
  then `jk-standards all` to the doc-lint job (or consume the reusable
  `doc-discipline.yml` / `pre-commit.yml` workflows — nfr-review already
  vendors skills from this repo, so the producer/consumer split is
  established).
- Keep the residual check #1 as its own step.

### 5. Pre-commit (`.pre-commit-config.yaml`)

Add above the local hooks:

```yaml
- repo: https://github.com/JimAKennedy/jk-standards
  rev: v0.2.0
  hooks:
    - id: count-drift
    - id: snippet-regions
```

## 1:1 invariant

Every claim in this guide maps to a shipped toolkit check, per the README
1:1 invariant: the two portable checks correspond exactly to count-drift and
snippet-regions, both covered by the `nfr-review parity` fixtures in
`tests/test_checks.py`. Check #1 is explicitly documented as a
non-portable residual with no corresponding toolkit check.
