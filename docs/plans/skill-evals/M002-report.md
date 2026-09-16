---
class: plan
---

# M002 report — Eval corpus and harness, locally runnable

Status: current (2026-09-16)

Review record for milestone M002 of `docs/plans/skill-evals/ledger.md`,
generated at the `/jk:auto` review gate. Next step: read this, then
`/jk:ship`.

**Vision:** Any developer with an API key can score every corpus skill —
compliance with a with/without-skill delta, plus selection — from one make
target, with no Claude Code CLI anywhere in the loop.

**Branch:** `milestone/M002-eval-corpus-harness` (4 commits on `main`).

## Slices

| Slice | Title | Rows | Status |
|---|---|---|---|
| M002/S01 | Harness end-to-end on one skill | R4, R7–R13, R19 done; N1 accepted | done |
| M002/S02 | Corpus breadth and selection eval | R5, R6 done; N3 accepted | done |

## Definition of done

Every box in both slices is checked; none reworded.

## Validation

| Slice | Token | Result |
|---|---|---|
| M002/S01 | format | exit 0 |
| M002/S01 | unit | pytest: 558→560 passed across the slice |
| M002/S01 | eval | make eval: first case passed live |
| M002/S01 | gate | verify.sh: all locally-runnable gates passed |
| M002/S02 | format | exit 0 |
| M002/S02 | eval | make eval: the recorded run, 10/10 passed, 19m20s |

## The recorded run (medians, with vs without, threshold 0.6)

| Case | with | without |
|---|---|---|
| versioned-state-serialization-basic | 1.00 | 0.40 |
| versioned-state-serialization-migration | 0.90 | 0.50 |
| realtime-audio-safety-callback | 1.00 | 0.20 |
| realtime-audio-safety-review | 1.00 | 1.00 (lift-exempt, reason in case.yaml) |
| doc-anti-drift-newdoc | 0.70 | 0.60 |
| doc-anti-drift-review | 1.00 | 0.60 |

Selection eval: 4/4 exact matches including the no-skill-applies
negative, on every live run.

## Traceability

- `f6d944c` plan: M002 slice plans and decisions — Slice: M002/S01, M002/S02
- `67431a9` feat: offline eval harness — Slice: M002/S01, Rows: R7,R8,R10,R11,R12
- `b1a865d` feat: live eval gate, first judged run — Slice: M002/S01, Rows: R4,R13,R19
- `0fa1091` feat: corpus breadth, selection, recorded run — Slice: M002/S02, Rows: R5,R6

No untraced commits.

## Things a reviewer should look at twice

- **The `require_lift` design decision** (asked and answered mid-run):
  review-shaped cases can tie a perfect unaided critique, so they may
  declare `require_lift: false` with a mandatory written reason; absolute
  thresholds still gate them. Both review cases carry the flag. The
  structural insight — strong models ace review tasks unaided — is worth
  remembering when authoring future cases: temptation-style generation
  prompts discriminated decisively (1.00 vs 0.20).
- **Two environment facts fixed in flight**, both now harness features:
  non-workspace-scoped keys need `ANTHROPIC_WORKSPACE_ID` (supported);
  claude-sonnet-5 thinking can exhaust tight token caps (cap 8000 +
  honest sentinel).
- **doc-anti-drift-newdoc's margin is thin** (0.70 vs 0.60 without):
  authoring-from-scratch is partially in Sonnet's unaided repertoire; a
  candidate for the same temptation treatment if it flakes in future runs.
- **`.github/pull_request_template.md` exists** and was missed by every
  prior ship's template check (a zsh glob aborted on its first failed
  pattern); this milestone's ship must follow it.
- Cost of the whole milestone's live iteration: roughly six full-or-partial
  suite runs at ~35–75 API calls each, all under the configured caps.

## Decisions (verbatim from M002-decisions.md)


# M002 decisions

Status: current (2026-09-16)

Append-only record per `/jk:auto` for skill-evals M002.

## 2026-09-16 — planning M002/S01 and M002/S02

- **Q:** How should `ANTHROPIC_API_KEY` reach the eval runs? — **A:**
  Gitignored `.env` at the repo root; `make eval` sources it; the
  staged-files gitleaks gate (M001/S01) guards against committing it.
- **Q:** Approve the designs (harness module layout, plain-pytest
  `make eval`, `deepeval==4.2.3`, corpus shape)? — **A:** Approve.
- **Decision:** S01 announced as greenfield-adjacent but executed as
  bounded: every interface was specified at assess time in rows R4–R13,
  so the ledger is the approved design and the front-load approval is the
  gate. — **Why:** a separate design doc would restate the rows.
- **Decision:** `deepeval==4.2.3` exact pin (latest on PyPI at planning,
  probed 2026-09-15; far past the documented 1.0 `evaluate()` API break),
  plus `anthropic` unpinned-lower-bounded. — **Why:** R8 requires an
  exact deepeval pin chosen at implementation time.
- **Decision:** `make eval` runs plain pytest over `evals/`
  (`testpaths=["tests"]` keeps it out of the `unit` token), not the
  `deepeval test run` CLI wrapper. — **Why:** fewer moving parts, no
  dependency on the wrapper's telemetry/login surface; deepeval metrics
  and `assert_test` work under plain pytest.
- **Decision:** Offline harness tests live in `tests/test_eval_harness.py`
  with a one-line `sys.path` insert to import `evals/harness`; they mock
  the Anthropic client. — **Why:** keeps them inside the `unit` token's
  collection so CI runs them for free.
- **Decision:** Judge and agent both default `claude-sonnet-5` (recorded
  at assess in the ledger's configuration-defaults section); run count 3,
  median scoring; thresholds start generous (0.6 absolute, delta > 0)
  time-boxed for ratcheting after two releases. — **Why:** assess-time
  defaults carried into config.
- **Decision:** Budget defaults: max_output_tokens 1500 per call, suite
  cap 40 cases, usage summary printed per run. — **Why:** R12 requires
  caps; a runaway scenario stops at the cap, not the quota.
- **Deferred:** the first live-run step (S01 Task 2's `eval` token and
  S02's recorded run) waits at the `.env` boundary — the user creates the
  file when ready; absence at that step is a planned pause, not a failure.

## 2026-09-16 — in-flight judgment calls, executing M002/S01 Task 2

- **Decision:** `ANTHROPIC_WORKSPACE_ID` support in the client (the API
  rejects non-workspace-scoped keys without the header). — **Why:** any
  consumer with an org-level key hits the same wall; five lines plus docs.
- **Decision:** max_output_tokens 1500 → 4000, and the runner substitutes
  "[no output produced within the token budget]" for empty text. —
  **Why:** claude-sonnet-5 emits thinking blocks that can exhaust a tight
  cap leaving no text; deepeval refuses an empty actual_output. The
  sentinel keeps an empty run honestly scoreable instead of crashing.

## 2026-09-16 — executing M002/S02: scenario findings and the delta rule

- **Decision:** results files now store per-arm transcripts. — **Why:** a
  failing case was undiagnosable without them (judgment call, in flight).
- **Decision:** judge implements deepeval's schema path (JSON verdict
  validated into the passed pydantic model, one corrective retry) and
  takes its max_tokens from config. — **Why:** raw-text verdicts were
  truncated at the old default and crashed deepeval's JSON trimming.
- **Decision:** max_output_tokens 4000 → 8000. — **Why:** design-shaped
  tasks exhaust 4000 in thinking alone, yielding sentinel outputs and
  zero scores on both arms.
- **Decision:** two scenarios rewritten as recorded scenario defects:
  realtime-audio-safety-review (blatant violations → hidden ones), then
  realtime-audio-safety-callback (neutral ask → temptation: the prompt
  requests two RT violations, so unaided compliance fails the rubric and
  the skilled arm must push back). Temptation discriminated decisively
  (1.00 vs 0.20). — **Why:** the plan's own rule: adjust scenarios that
  fail to discriminate; never touch thresholds silently.
- **Q:** How should the delta assertion treat ceiling-prone review-type
  cases (observed 1.0/1.0 ties run-to-run)? — **A:** Per-case
  `require_lift: false` flag with a mandatory written reason; absolute
  thresholds always still gate. Both review cases carry the flag with the
  observed-tie reason recorded in their case.yaml.
