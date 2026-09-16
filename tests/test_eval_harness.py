"""Offline tests for the evals/harness package (no API key, no network).

The harness lives outside the shipped package (evals/harness) so the
check-registry boundaries stay untouched; these tests import it via a
sys.path entry and mock the Anthropic client at the harness's own seam.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "evals"))

from harness import config as hconfig  # noqa: E402
from harness import corpus as hcorpus  # noqa: E402
from harness import judge as hjudge  # noqa: E402
from harness import results as hresults  # noqa: E402
from harness import runner as hrunner  # noqa: E402

CONFIG_BLOCK = """\
# region:skill-evals-config
skill_evals:
  agent_model: claude-sonnet-5
  judge_model: claude-sonnet-5
  runs: 3
  default_threshold: 0.6
  max_output_tokens: 1500
  max_cases: 40
# endregion:skill-evals-config
"""


def _repo(tmp_path: Path, *, cases: dict[str, str] | None = None) -> Path:
    (tmp_path / "jk-standards.yaml").write_text(CONFIG_BLOCK, encoding="utf-8")
    skill = tmp_path / "skills/versioned-state-serialization/SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: versioned-state-serialization\ndescription: Use when x.\n---\n\nWrite a version tag first.\n",
        encoding="utf-8",
    )
    for name, body in (cases or {}).items():
        case = tmp_path / "evals/cases" / name / "case.yaml"
        case.parent.mkdir(parents=True)
        case.write_text(body, encoding="utf-8")
    return tmp_path


GOOD_CASE = """\
skill: versioned-state-serialization
prompt: Serialize a preset struct to bytes and read it back.
rubric:
  - Writes a version tag before any payload bytes
  - Branches on the tag when reading
"""


def test_config_reads_region(tmp_path):
    cfg = hconfig.load_config(_repo(tmp_path))
    assert cfg.agent_model == "claude-sonnet-5"
    assert cfg.judge_model == "claude-sonnet-5"
    assert cfg.runs == 3
    assert cfg.default_threshold == 0.6
    assert cfg.max_output_tokens == 1500
    assert cfg.max_cases == 40


def test_corpus_loads_cases(tmp_path):
    root = _repo(tmp_path, cases={"vss-basic": GOOD_CASE})
    cfg = hconfig.load_config(root)
    cases = hcorpus.load_corpus(root, cfg)
    assert len(cases) == 1
    c = cases[0]
    assert c.skill == "versioned-state-serialization"
    assert "version tag" in c.rubric[0]
    assert c.threshold == 0.6  # default applied


def test_corpus_rejects_unknown_skill(tmp_path):
    bad = GOOD_CASE.replace("versioned-state-serialization", "no-such-skill")
    root = _repo(tmp_path, cases={"bad": bad})
    cfg = hconfig.load_config(root)
    with pytest.raises(hcorpus.CorpusError):
        hcorpus.load_corpus(root, cfg)


def test_arm_construction(tmp_path):
    root = _repo(tmp_path, cases={"vss-basic": GOOD_CASE})
    cfg = hconfig.load_config(root)
    (case,) = hcorpus.load_corpus(root, cfg)
    arms = hrunner.build_arms(case, root)
    assert set(arms) == {"with", "without"}
    assert "Write a version tag first." in arms["with"]
    assert "Write a version tag first." not in (arms["without"] or "")
    # both arms share the same user prompt (carried on the case)
    assert case.prompt.startswith("Serialize")


class _FakeMessages:
    def __init__(self, log: list) -> None:
        self._log = log

    def create(self, **kwargs):
        self._log.append(kwargs)

        class _Block:
            text = "fake completion"

        class _Usage:
            input_tokens = 10
            output_tokens = 5

        class _Resp:
            content = [_Block()]
            usage = _Usage()

        return _Resp()


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list = []
        self.messages = _FakeMessages(self.calls)


def test_runner_respects_budget_caps(tmp_path):
    root = _repo(tmp_path, cases={"vss-basic": GOOD_CASE})
    cfg = hconfig.load_config(root)
    (case,) = hcorpus.load_corpus(root, cfg)
    client = _FakeClient()
    out = hrunner.run_case(client, case, cfg, root)
    assert all(k["max_tokens"] == 1500 for k in client.calls)
    # runs per arm, two arms
    assert len(client.calls) == cfg.runs * 2
    assert out.usage.input_tokens > 0

    # suite cap: more cases than max_cases aborts before any call
    small = hconfig.EvalConfig(**{**cfg.__dict__, "max_cases": 0})
    with pytest.raises(hrunner.BudgetError):
        hrunner.check_suite_budget([case], small)


def test_results_record_provenance_and_median(tmp_path):
    root = _repo(tmp_path)
    cfg = hconfig.load_config(root)
    path = tmp_path / "results.json"
    hresults.write_results(
        path,
        cfg,
        cases=[{"name": "vss-basic", "scores": [0.5, 0.9, 0.7], "threshold": 0.6}],
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    prov = data["provenance"]
    assert prov["agent_model"] == "claude-sonnet-5"
    assert prov["judge_model"] == "claude-sonnet-5"
    assert prov["runs"] == 3
    assert prov["default_threshold"] == 0.6
    assert data["cases"][0]["median"] == 0.7


def test_judge_uses_anthropic_only():
    client = _FakeClient()
    j = hjudge.AnthropicJudge(client, model="claude-sonnet-5")
    assert j.generate("rate this") == "fake completion"
    assert j.get_model_name() == "claude-sonnet-5"
    # the no-OpenAI DoD, made greppable: no harness module names OPENAI
    for mod in (hconfig, hcorpus, hjudge, hresults, hrunner):
        assert "OPENAI" not in Path(mod.__file__).read_text(encoding="utf-8").upper()
