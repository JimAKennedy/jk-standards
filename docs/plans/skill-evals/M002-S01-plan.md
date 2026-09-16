---
class: plan
---

# Plan M002/S01 — Harness end-to-end on one skill

Status: current (2026-09-16)

**Slice:** M002/S01 — Harness end-to-end on one skill, in
`docs/plans/skill-evals/ledger.md`

**Task status**

- [ ] Task 1 — offline harness: extra, modules, mocked tests
- [ ] Task 2 — eval entry, make target, config region, live run

**Definition of Done**

- [ ] `evals/README.md` documents the corpus format
- [ ] One skill's scenarios run both arms (with/without skill text) and are
      judged by the Anthropic-backed deepeval model with no OpenAI key
      referenced anywhere
- [ ] `region:skill-evals-config` in `jk-standards.yaml` holds agent model
      id, judge model id, run count, and thresholds; every results file
      records them
- [ ] Budget caps (per-case tokens, suite case cap) abort a run that
      exceeds them
- [ ] `make eval` runs the suite given `ANTHROPIC_API_KEY`;
      `scripts/verify.sh`'s documented exclusion list names it
- [ ] Offline harness logic (corpus loading, config, arm construction,
      results serialization) has pytest coverage with the API mocked

**Validation**

- `format` → `pre-commit run --all-files`
- `unit` → `pytest -q`
- `eval` → `make eval`
- `gate` → `scripts/verify.sh`

## Task 1 — offline harness: extra, modules, mocked tests

Consumes: nothing. Produces: importable `evals/harness` package with
offline test coverage; `[eval]` extra installable.

1. `pyproject.toml`: add optional extra
   `eval = ["deepeval==4.2.3", "anthropic>=0.40"]`. Run
   `.venv/bin/pip install -e ".[eval]"` and record the result.
2. Failing tests first in `tests/test_eval_harness.py` (inside the `unit`
   collection; two-line header: `sys.path.insert(0, str(REPO/"evals"))`
   then `from harness import ...`). Cases, all offline, Anthropic client
   mocked at the harness's own seam:
   - `test_config_reads_region` — `load_config(root)` returns agent model,
     judge model, run count, thresholds, budget caps parsed from the
     `region:skill-evals-config` block of `jk-standards.yaml` (use a
     tmp_path copy with a minimal region).
   - `test_corpus_loads_cases` — `load_corpus(root)` finds
     `evals/cases/<name>/case.yaml`, returning skill name, prompt, rubric
     criteria, and per-case threshold with defaults from config.
   - `test_corpus_rejects_unknown_skill` — a case naming a skill without
     `skills/<name>/SKILL.md` raises/reports.
   - `test_arm_construction` — `build_arms(case, root)` yields exactly
     two arms; the with-arm system prompt contains the SKILL.md body, the
     without-arm does not; both share the user prompt.
   - `test_runner_respects_budget_caps` — a fake client records
     max_tokens on every call == config cap; a corpus larger than the
     suite cap aborts with the documented message before any call.
   - `test_results_record_provenance` — `write_results(...)` output JSON
     carries agent model id, judge model id, run count, thresholds, and
     per-case scores; `test_results_median` — median of 3 fake run scores
     is what lands in the summary.
   - `test_judge_uses_anthropic_only` — the deepeval custom model class
     instantiates from an injected client and its `generate()` returns
     the fake completion; plus a source-level assertion that no harness
     module contains the string `OPENAI` (the no-OpenAI-key DoD, made
     greppable).
3. Watch them fail (ImportError — modules absent), the right reason.
4. Implement `evals/harness/` (`__init__.py`, `config.py`, `corpus.py`,
   `runner.py`, `judge.py`, `results.py`), each small and typed:
   - `config.py`: parse the `region:skill-evals-config` block (plain YAML
     under the markers) — keys: `agent_model`, `judge_model`, `runs`,
     `default_threshold`, `max_output_tokens`, `max_cases`.
   - `corpus.py`: case dirs under `evals/cases/`; `case.yaml` keys:
     `skill`, `prompt`, `rubric` (list of criteria strings), optional
     `threshold`; validates the named skill exists.
   - `runner.py`: `build_arms` + `run_case(client, case, cfg)` — for each
     arm, `runs` calls to `client.messages.create` with
     `max_tokens=cfg.max_output_tokens`, collecting text and usage;
     suite-cap check up front; usage totals accumulated for the printed
     summary.
   - `judge.py`: `AnthropicJudge(DeepEvalBaseLLM)` wrapping an injected
     `anthropic.Anthropic` client; `generate`/`a_generate` via
     `messages.create` on `cfg.judge_model`.
   - `results.py`: dataclass + `write_results(path, cfg, scores)` JSON
     with provenance block; median helper.
5. Tests green; `pytest -q` full suite green; ruff clean.
6. Evidence, tick box, `jk-standards ledger`, commit with trailers
   `Slice: M002/S01`, `Rows: R7,R8,R10,R11,R12` (partial rows noted as
   in-progress in the message body, closed in Task 2 where their live
   half lands — rows stay `open` in the ledger until then).

Check that closes the task: `unit` (`pytest -q` exit 0).

## Task 2 — eval entry, make target, config region, live run

Consumes: Task 1's modules. Produces: the runnable gate and the first
recorded two-arm judged run.

1. `jk-standards.yaml`: append the `region:skill-evals-config` block
   (agent_model claude-sonnet-5, judge_model claude-sonnet-5, runs 3,
   default_threshold 0.6, max_output_tokens 1500, max_cases 40) with a
   comment tying thresholds to the two-release ratchet time-box.
2. First corpus case (proves the pipeline; breadth is S02):
   `evals/cases/versioned-state-serialization-basic/case.yaml` — prompt:
   a short serialization task in C++-flavoured pseudocode; rubric: writes
   a version tag before payload bytes; reader branches on the tag;
   unversioned bytes are never reinterpreted.
3. `evals/test_skills_eval.py`: skips cleanly with the documented message
   when `ANTHROPIC_API_KEY` is absent; otherwise parametrizes over the
   corpus, runs both arms via the harness, judges the with-arm output
   with deepeval `GEval` (criteria from the rubric, `AnthropicJudge`),
   asserts per-case threshold and with>without delta, writes
   `evals/results/<date>.json` (gitignored) via `write_results`, prints
   the usage summary.
4. `evals/README.md`: corpus format, adding a case, thresholds/ratchet,
   reading a failure, the `.env` convention, cost expectations.
5. Wiring: `.gitignore` gains `.env` and `evals/results/`; `Makefile`
   gains `eval:` target — sources `.env` if present, refuses with a
   pointed message if `ANTHROPIC_API_KEY` is still unset, runs
   `.venv/bin/python -m pytest evals/ -q`; `scripts/verify.sh` exclusion
   list gains the eval (paid API, not laptop-reproducible by default).
6. **Planned pause boundary:** if `.env` is absent here, stop and hand
   the user the one-liner to create it; on resume re-enter at this step.
   With the key: run `make eval`, read the output, record the scores and
   usage in evidence.
7. All tokens: `format`, `unit`, `eval`, `gate` (+ the two range arms vs
   main). Evidence; tick task and DoD boxes; rows R4, R7–R13, R19 done;
   slice `done`; ledger check; commit with trailers `Slice: M002/S01`,
   `Rows: R4,R13,R19`.

Check that closes the task: `eval` (`make eval` exit 0).
