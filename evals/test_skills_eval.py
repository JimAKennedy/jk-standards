"""LLM-judged two-arm skill evaluation (the `eval` validation token).

Runs each corpus case twice — with the skill's SKILL.md as system context
and without — judges both outputs against the case rubric with a
deepeval G-Eval metric on an Anthropic judge, and asserts the with-arm
clears its threshold AND beats the without-arm. Skips (never fails) when
ANTHROPIC_API_KEY is absent: this file is the paid path, run via
`make eval`, not part of the offline `unit` token.
"""

from __future__ import annotations

import datetime
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))

from harness import config as hconfig  # noqa: E402
from harness import corpus as hcorpus  # noqa: E402
from harness import judge as hjudge  # noqa: E402
from harness import results as hresults  # noqa: E402
from harness import runner as hrunner  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — run via `make eval` with .env present",
)

CFG = hconfig.load_config(ROOT)
CASES = hcorpus.load_corpus(ROOT, CFG)
_RESULTS: list[dict] = []


def _client():
    """Anthropic client; honors ANTHROPIC_WORKSPACE_ID for org-level keys.

    A key not scoped to a workspace is rejected by the API unless the
    request names one — consumers with org keys set the env var instead
    of minting a new key.
    """
    import anthropic

    headers = {}
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if workspace:
        headers["anthropic-workspace-id"] = workspace
    return anthropic.Anthropic(default_headers=headers or None)


def _geval(case, judge):
    from deepeval.metrics import GEval
    from deepeval.test_case import LLMTestCaseParams

    return GEval(
        name=f"rubric:{case.name}",
        criteria=" ".join(["Judge the response strictly against each point:", *case.rubric]),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
        ],
        model=judge,
        threshold=case.threshold,
        async_mode=False,
    )


def _score(case, judge, output: str) -> float:
    from deepeval.test_case import LLMTestCase

    metric = _geval(case, judge)
    metric.measure(LLMTestCase(input=case.prompt, actual_output=output))
    return float(metric.score or 0.0)


@pytest.fixture(scope="session")
def session_state():
    client = _client()
    judge = hjudge.AnthropicJudge(client, model=CFG.judge_model, max_tokens=CFG.max_output_tokens)
    hrunner.check_suite_budget(CASES, CFG)
    usage = hrunner.Usage()
    yield client, judge, usage
    if _RESULTS:
        out = ROOT / "evals" / "results" / (datetime.date.today().isoformat() + ".json")
        hresults.write_results(out, CFG, _RESULTS)
        print(
            f"\n[skill-evals] {len(_RESULTS)} case(s); usage: "
            f"{usage.input_tokens} in / {usage.output_tokens} out tokens; "
            f"results: {out.relative_to(ROOT)}"
        )


@pytest.mark.parametrize("case", CASES, ids=[c.name for c in CASES])
def test_skill_compliance(case, session_state):
    client, judge, usage = session_state
    run = hrunner.run_case(client, case, CFG, ROOT)
    usage.add(run.usage)

    with_scores = [_score(case, judge, o) for o in run.outputs["with"]]
    without_scores = [_score(case, judge, o) for o in run.outputs["without"]]
    with_med = hresults.median(with_scores)
    without_med = hresults.median(without_scores)

    _RESULTS.append(
        {
            "name": case.name,
            "scores": with_scores,
            "without_scores": without_scores,
            "threshold": case.threshold,
            # transcripts: without these a failing case cannot be diagnosed
            "outputs": run.outputs,
        }
    )
    assert with_med >= case.threshold, (
        f"{case.name}: with-skill median {with_med:.2f} below threshold {case.threshold:.2f}"
    )
    if case.require_lift:
        assert with_med > without_med, (
            f"{case.name}: no with-skill lift (with {with_med:.2f} <= "
            f"without {without_med:.2f}) — the skill text changed nothing"
        )
