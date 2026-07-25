---
name: sanitizer-ci-setup
description: Wire ASan/UBSan/TSan, fuzzing, and layered quality gates into CI for C/C++ projects — nightly sanitizer matrices, issue-dedupe notification, sanitizer-aware tests, strictness gradients. Use when setting up or auditing CI for a native-code project.
---

# Sanitizer and quality-gate CI setup

## The layered gate model

Order checks by cost and place them at the cheapest layer that catches the
failure early enough:

1. **pre-commit** — seconds: format, lexical lints, secret scan.
2. **pre-push** — a minute or two: build + unit tests + a *reduced*
   strictness level of the expensive validators. Accumulate failures and
   report all broken gates in one run rather than exiting on the first.
3. **PR CI** — the merge gate: multi-platform build, full-strictness
   validators, coverage threshold, doc checks, ratcheted scanners.
4. **nightly** — the expensive sweep: sanitizer matrix, full scans that
   produce the next day's ratchet baseline.

The pre-push/CI pair should run the *same* checks at different strictness,
and the pre-push failure message should print the CI-parity invocation so
the developer can reproduce exactly what CI will do.

## Sanitizer matrix

Run ASan, UBSan, and TSan as **separate jobs** — they are mutually
exclusive instrumentations; enforce that in the build system
(`if/elseif`, not independent flags). Recommended baseline:

- Debug builds, `-fno-omit-frame-pointer` with ASan/UBSan.
- `UBSAN_OPTIONS=print_stacktrace=1`; per-sanitizer suppression files
  checked in from day one, even empty — the file's existence is where the
  first third-party suppression goes, with a comment, instead of a panicked
  CI hack.
- **Instrument the integration surface, not just the core.** If the
  library core and the host/plugin layer build separately, add jobs that
  drop the core-only flag so the boundary code (threading handshakes,
  callbacks) is instrumented — that boundary is where the races live.
- Test-filter the sanitizer jobs (`ctest -R <regex>`) to the suites that
  exercise concurrency and memory hot paths; full-suite sanitizer runs are
  for a weekly cadence if runtime allows.

### Sanitizer-aware tests

Write stress tests so they scale under instrumentation: detect the
sanitizer at compile time (`__has_feature(thread_sanitizer)`) and reduce
iteration counts ~20× — TSan costs 5–15× runtime. Keep both variants: the
full-iteration run's invariant assertions catch logic races; the
instrumented run catches races the invariants can't observe. Document that
division of labor in the test.

### Nightly-vs-blocking trade-off

Sanitizers on every PR is the gold standard but costs wall-clock. A nightly
matrix is an acceptable floor **only with a notification path that cannot
be ignored**: a job that, on any failure, comments on an existing open
issue labelled `sanitizer-failure` or creates one — deduplicated by label
so repeats don't spam. Beware `continue-on-error: true` on GitHub Actions:
it reports the job's result as `success`, silently killing
`needs.<job>.result == 'failure'` notification logic. Let jobs fail
honestly and gate the notify step with `if: always()`.

## Fuzzing

A fuzz target that isn't in CI doesn't exist. Wire libFuzzer targets to at
least a nightly short run (e.g. `-max_total_time=300`) with the corpus
cached between runs. Fuzz *through* the parser into the logic behind it:
if deserialization succeeds, drive the real engine on the parsed state —
parser-only fuzzing misses the bugs that matter.

## Completeness checklist

- [ ] ASan + UBSan + TSan jobs, mutually exclusive flags, suppression files checked in
- [ ] Integration-surface (non-core-only) sanitizer jobs
- [ ] Sanitizer-aware iteration scaling in stress tests
- [ ] Failure → deduped issue/notification, no `continue-on-error` masking
- [ ] Fuzz targets wired to a schedule, corpus cached
- [ ] Static analysis (clang-tidy) actually invoked in CI — a config file with no CI step is decoration
- [ ] Coverage threshold enforced locally in the job (external coverage services advisory only)
- [ ] All third-party actions SHA-pinned; validator versions pinned with a written bump procedure
