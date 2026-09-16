"""Two-arm case execution against the Anthropic API.

The with-arm carries the skill's SKILL.md body as system context; the
without-arm carries none. The judged delta between them is what proves a
skill changes behavior rather than merely reading well. Budget caps are
enforced here: every call is bounded by max_output_tokens, and a corpus
larger than max_cases aborts before the first call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from harness.config import EvalConfig
from harness.corpus import Case


class BudgetError(Exception):
    """The suite exceeds the configured budget; nothing was called."""


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def add(self, resp_usage) -> None:
        self.input_tokens += int(getattr(resp_usage, "input_tokens", 0))
        self.output_tokens += int(getattr(resp_usage, "output_tokens", 0))


@dataclass
class CaseRun:
    case: Case
    outputs: dict[str, list[str]] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)


def check_suite_budget(cases: list[Case], cfg: EvalConfig) -> None:
    if len(cases) > cfg.max_cases:
        raise BudgetError(
            f"corpus has {len(cases)} cases, over the max_cases cap of "
            f"{cfg.max_cases} in region:skill-evals-config — raise the cap "
            f"deliberately or split the run"
        )


def build_arms(case: Case, root: Path) -> dict[str, str | None]:
    """System-context text per arm: the skill body, or nothing."""
    skill_md = root / "skills" / case.skill / "SKILL.md"
    return {"with": skill_md.read_text(encoding="utf-8"), "without": None}


def run_case(client, case: Case, cfg: EvalConfig, root: Path) -> CaseRun:
    run = CaseRun(case=case)
    for arm, system in build_arms(case, root).items():
        outputs: list[str] = []
        for _ in range(cfg.runs):
            kwargs = {
                "model": cfg.agent_model,
                "max_tokens": cfg.max_output_tokens,
                "messages": [{"role": "user", "content": case.prompt}],
            }
            if system is not None:
                kwargs["system"] = system
            resp = client.messages.create(**kwargs)
            text = "".join(getattr(b, "text", "") for b in resp.content)
            # A response whose budget went entirely to thinking blocks has no
            # text; hand the judge an honest sentinel instead of an empty
            # string deepeval refuses to score.
            outputs.append(text or "[no output produced within the token budget]")
            run.usage.add(resp.usage)
        run.outputs[arm] = outputs
    return run
