---
class: plan
---

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
