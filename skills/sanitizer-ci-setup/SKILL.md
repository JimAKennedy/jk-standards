---
name: sanitizer-ci-setup
description: Wire ASan/UBSan/TSan and fuzzing into CI for C/C++ projects — nightly sanitizer matrices, issue-dedupe notification paths, sanitizer-aware stress tests, integration-surface instrumentation. Use when setting up or auditing the native-code sanitizer layer of a project's CI.
---

# Sanitizer and fuzzing CI setup

This skill covers the native-code instrumentation layer: sanitizer matrices,
sanitizer-aware tests, fuzzing, and the notification path that keeps a nightly
sweep honest. The generic CI-structure discipline underneath it — layered
cost-ordered gates, SHA pinning + dependabot cadence, the single aggregation
gate, artifact retention — lives in the `ci-hygiene` skill; set that up first,
then layer these sanitizer jobs onto it.

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
- [ ] Generic CI structure (layered gates, SHA pinning, aggregation gate, retention) handled per the `ci-hygiene` skill
