---
name: ci-hygiene
description: Structure CI for correctness and cost — layered cost-ordered gates, SHA-pinned actions on a weekly dependabot cadence, a single aggregation gate for branch protection, and artifact-retention conventions. Use when setting up, auditing, or reviewing a project's CI workflow structure and dependency-update hygiene (the generic layer, not the sanitizer/native layer — see sanitizer-ci-setup).
---

# CI structure and hygiene

Generic, language-agnostic CI-structure discipline: how to *order* gates, keep
the supply chain pinned, and expose a single honest merge signal. For the
native-code sanitizer/instrumentation layer that sits on top of this, see the
`sanitizer-ci-setup` skill.

## The layered gate model

Order checks by cost and place each at the cheapest layer that catches the
failure early enough:

1. **pre-commit** — seconds: format, lexical lints, secret scan.
2. **pre-push** — a minute or two: build + unit tests + a *reduced*
   strictness level of the expensive validators. Accumulate failures and
   report all broken gates in one run rather than exiting on the first.
3. **PR CI** — the merge gate: multi-platform build, full-strictness
   validators, coverage threshold, doc checks, ratcheted scanners.
4. **nightly** — the expensive sweep: full scans that produce the next day's
   ratchet baseline (and, for native projects, the sanitizer matrix).

The pre-push/CI pair should run the *same* checks at different strictness,
and the pre-push failure message should print the CI-parity invocation so the
developer can reproduce exactly what CI will do.

This repo's `.github/workflows/ci.yml` is the worked example: cheap `test`
(ruff + pytest across a Python matrix) and `emit-check` jobs sit alongside
the heavier `dogfood`, `package`, and `site-build` jobs, each isolated so a
slow leg never blocks the fast signal.

## SHA pinning and the dependabot cadence

Pin **every** third-party action to a full commit SHA, with the human-readable
tag in a trailing comment so the intent stays legible:

```yaml
- uses: actions/checkout@08c6903cd8c0fde910a37f88322edcfb5dd907a8 # v5.0.0
```

A moving tag (`@v5`) is a supply-chain hole: the tag can be re-pointed at
malicious code after you've reviewed it. The SHA is immutable; the comment is
what you read. Enforce this with a check that fails on any unpinned `uses:`
(this repo runs `jk-standards action-pinning` in the `dogfood` job so the
whole `.github/workflows/` tree is audited on every PR).

Pinning freezes the supply chain, so pair it with a **written renewal cadence**
or the pins rot. `.github/dependabot.yml` here watches all three ecosystems the
repo ships (`github-actions`, `pip`, `npm` under `/site`) on a weekly Monday
schedule. The grouping rule is the load-bearing decision:

- **minor + patch → one grouped PR per ecosystem per week** so routine bumps
  read as a single review (`groups: { actions-minor-patch: { update-types: [minor, patch] } }`).
- **majors → individual PRs**, because they carry breaking-change risk and
  deserve isolated review (e.g. ruff, whose default rule set expands even in
  minor releases).
- `open-pull-requests-limit: 5` caps the inbox flood per ecosystem.

Validator/tool versions get the same treatment: pin the version and record a
written bump procedure next to the pin, so a bump is a deliberate, reviewed
change rather than a silent drift.

## The aggregation gate

Branch protection should require **one** check, not a hand-maintained list of
every job. Add a single job that `needs` every other job and fails if any of
them did not succeed — then require only that job. This is the `ci-complete`
pattern in `ci.yml`:

```yaml
ci-complete:
  needs: [test, coverage, pre-commit, emit-check, dogfood, package,
          reusable-workflow-smoke, sanitizer-nightly-smoke, secrets-scan, site-build]
  if: always()
  runs-on: ubuntu-latest
  steps:
    - name: Check all jobs passed
      run: |
        if [[ "${{ needs.test.result }}" != "success" ]] || \
           [[ "${{ needs.coverage.result }}" != "success" ]] || \
           ... ; then
          echo "One or more CI jobs failed"
          exit 1
        fi
```

Requiring the aggregation gate instead of the individual jobs means adding a
new job only touches `ci.yml` (extend `needs` + the result check), never the
branch-protection settings — the required-check list stays a one-liner.

### The matrix-finalization gotcha

The aggregation gate has one non-obvious failure mode, and it is the reason
`if: always()` is mandatory:

- **`if: always()` is not optional.** Without it, the aggregation job inherits
  the default `if: success()` and is **skipped** the moment any upstream job
  fails. A *skipped* required check reads as not-failed to branch protection,
  so a broken PR silently becomes mergeable — the exact opposite of the intent.
  `always()` forces the job to run and reach its explicit result check.
- **Check `result`, never trust the absence of a failure.** A matrix job
  (like `test` across `python-version: ["3.11", "3.12"]`) *finalizes* its legs
  into a single `needs.test.result`: `success` only if every leg succeeded,
  and `skipped` if the matrix expanded to zero legs. Comparing `!= "success"`
  catches `failure`, `cancelled`, **and** the empty-matrix `skipped` case, so a
  vacuously-green matrix can't slip a PR through. Enumerate each job's
  `.result` explicitly — an omitted job is an un-checked hole in the gate.
- Never mask a leg with `continue-on-error: true`: it rewrites the job result
  to `success`, defeating the `.result` check above.

## Artifact retention

Uploaded artifacts default to the repo/org retention limit (often 90 days),
which quietly accumulates storage. Set `retention-days` explicitly on every
`upload-artifact` to the shortest window that is still useful — this repo uses
`retention-days: 14` for CI diagnostics (`coverage-xml`, `dist`, `site-dist`).
Pair it with `if-no-files-found:` so a missing artifact is a loud `error` when
the artifact is a required output, or a `warn` when it is best-effort:

```yaml
- uses: actions/upload-artifact@330a01c490aca151604b8cf639adc76d48f6c5d4 # v5
  with:
    name: site-dist
    path: site/dist/
    retention-days: 14
    if-no-files-found: error
```

## Completeness checklist

- [ ] Checks ordered cheapest-first across pre-commit / pre-push / PR / nightly
- [ ] pre-push runs the same checks as CI at reduced strictness and prints the CI-parity command
- [ ] Every third-party action SHA-pinned with a tag comment; a check fails on any unpinned `uses:`
- [ ] Validator/tool versions pinned with a written bump procedure
- [ ] `dependabot.yml` covers every shipped ecosystem, minor+patch grouped, majors individual, PR limit set
- [ ] One `needs`-everything aggregation gate is the *only* required branch-protection check
- [ ] Aggregation gate uses `if: always()` and checks each job's `.result != 'success'` explicitly
- [ ] No `continue-on-error` masking a job the aggregation gate depends on
- [ ] Every `upload-artifact` sets `retention-days` and `if-no-files-found`
