# Skill evaluations

LLM-judged evidence that each skill under `skills/` actually changes agent
behavior — the `eval` validation token, run via `make eval`. Design record:
`docs/plans/skill-evals/ledger.md`.

## How a case works

Each case directory under `cases/` holds one `case.yaml`:

```yaml
skill: versioned-state-serialization   # must exist in skills/
prompt: |                              # the task given to the agent model
  ...
rubric:                                # judged criteria, observable outcomes
  - Writes a version tag before any payload bytes
threshold: 0.6                         # optional; default from config
```

Every case runs **two arms** — the agent model with the skill's SKILL.md as
system context, and without — for `runs` attempts each. A deepeval G-Eval
metric on an Anthropic judge scores each output against the rubric; the
case passes when the with-arm's median clears its threshold **and** beats
the without-arm's median. The delta is the point: it proves the skill text
changed behavior rather than merely reading well.

Configuration lives in `region:skill-evals-config` of `jk-standards.yaml`
(models, run count, thresholds, budget caps) and is stamped into every
results file under `results/` (gitignored), so a score always says what
produced it. Thresholds start generous; the ratchet is time-boxed — see
the decisions file in the ledger directory.

## Running

```
make eval
```

Needs `ANTHROPIC_API_KEY` — either exported, or in a gitignored `.env` at
the repo root (`ANTHROPIC_API_KEY=sk-ant-...`), which the make target
sources. A key not scoped to a workspace additionally needs
`ANTHROPIC_WORKSPACE_ID=wsid_...` (same file), which the harness passes as
the `anthropic-workspace-id` header; a workspace-scoped key needs nothing
extra. The pre-commit gitleaks gate guards the file against accidental
commit. Without the key the suite skips with a pointed message; it never
fails for absence. Cost scales with corpus size × runs × two arms plus one
judge call per output; the per-call `max_output_tokens` and suite-level
`max_cases` caps bound a runaway.

## Reading a failure

- *below threshold*: the with-skill output did not satisfy the rubric —
  read the transcript in the results file before touching anything.
- *no with-skill lift*: the model already does the right thing without the
  skill; the scenario is too easy, or the skill's prose adds nothing —
  both are findings worth a row, not a threshold tweak. Review-shaped
  cases are ceiling-prone by nature (a strong unaided model can tie a
  perfect critique), so a case may declare `require_lift: false` with a
  mandatory `require_lift_reason`; its absolute threshold still applies,
  which keeps catching a skill that makes outputs *worse*.
- Never lower a threshold to make a run pass; a threshold change is a
  deliberate, recorded decision.

## The corpus

| Case | Skill exercised |
|---|---|
| versioned-state-serialization-basic | versioned-state-serialization |
| versioned-state-serialization-migration | versioned-state-serialization |
| realtime-audio-safety-callback | realtime-audio-safety |
| realtime-audio-safety-review | realtime-audio-safety |
| doc-anti-drift-newdoc | doc-anti-drift |
| doc-anti-drift-review | doc-anti-drift |

`test_skill_selection.py` additionally checks that the agent model, shown
the generated skill inventory, names the right skill for a task — including
answering `none` when nothing applies. Exact match, no judge call.

Offline harness logic is covered by `tests/test_eval_harness.py` (mocked
client, runs in the ordinary `unit` token).
