---
class: gated
---

# Skill evaluation discipline

Status: current (2026-09-16)

The skills under `skills/` are prose whose whole value is changing agent
behavior — and prose regressions, trigger failures, and model drift are
invisible to every deterministic check. The eval suite under `evals/` is
the gate for all three. This doc is the discipline; `evals/README.md` is
the hands-on corpus reference; the delivery record is
`docs/plans/skill-evals/ledger.md`.

## What a run proves

Each corpus case runs **two arms** — the agent model with the skill's
SKILL.md as system context, and without — for a configured number of
attempts each. A deepeval G-Eval metric on an Anthropic judge scores every
output against the case's rubric of observable outcomes. A case passes
when the with-arm's median clears its absolute threshold and, unless the
case declares `require_lift: false` with a written reason (review-shaped
tasks, where a strong unaided model can tie a perfect critique), beats the
without-arm's median. A separate judge-free selection eval shows the
model, given the generated skill inventory, names the right skill for a
task — including `none` when nothing applies.

Every knob a score depends on — agent and judge model ids, run count,
thresholds, token and case caps — lives in the
`region:skill-evals-config` block of `jk-standards.yaml` and is stamped
into each results file with the transcripts, so a recorded score always
says exactly what produced it. Thresholds start deliberately generous;
ratcheting them is a recorded decision, time-boxed in the ledger's
decisions file, never a quiet edit to make a run pass.

## Where it runs

- **Locally**: `make eval`, given `ANTHROPIC_API_KEY` (a gitignored
  `.env` works; org-level keys also need `ANTHROPIC_WORKSPACE_ID`).
  Without a key the suite skips with a pointed message — it never
  false-greens. This is the `eval` validation token in
  `.jk/validations.yml`.
- **Per pull request**: the `eval-paths` job in CI detects changes to
  skills, commands, the corpus, the config, or the workflow itself, and
  only then runs the paid gate; `ci-complete` sanctions a skip solely on
  eval-paths' own not-relevant verdict.
- **On every release tag**: `release.yml` runs the full corpus before
  publishing — no release ships unevaluated skills. A flaky judge
  failure there is resolved by re-running the job, never by re-tagging.
- **Weekly**: the scheduled run re-scores the unchanged corpus on
  current models — the model-drift watch no diff-based check can
  provide. Failures drive a single label-deduped `skill-evals-drift`
  issue; green closes it.

## Reading a failure

*Below threshold*: read the transcript in the results artifact before
touching anything — the rubric point it misses is usually visible in one
read. *No with-skill lift*: the scenario is too easy or the skill's prose
adds nothing; both are findings worth a ledger row. Scenario authoring
lore, learned the expensive way: temptation-style generation prompts (the
prompt requests what the skill forbids) discriminate decisively, while
review-shaped prompts ceiling.

## Cost model

A full run is corpus × runs × two arms in agent calls, plus one judge
call per output, bounded by the config's per-call token cap and
suite-level case cap. The per-PR path-filter keeps unrelated changes
free; the scheduled and tag runs are the standing weekly and per-release
spend, minutes and cents at current corpus size.
