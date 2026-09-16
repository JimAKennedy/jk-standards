"""Load eval cases from evals/cases/<name>/case.yaml.

A case names the skill it exercises, the task prompt, and the rubric the
judge scores against. The named skill must exist in the tree — a corpus
entry for a renamed skill fails loudly here rather than judging nothing.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from harness.config import EvalConfig


class CorpusError(Exception):
    """A case is malformed or names a skill the tree does not carry."""


@dataclass(frozen=True)
class Case:
    name: str
    skill: str
    prompt: str
    rubric: tuple[str, ...]
    threshold: float


def load_corpus(root: Path, cfg: EvalConfig) -> list[Case]:
    cases: list[Case] = []
    base = root / "evals" / "cases"
    if not base.is_dir():
        return cases
    for case_yaml in sorted(base.glob("*/case.yaml")):
        data = yaml.safe_load(case_yaml.read_text(encoding="utf-8")) or {}
        name = case_yaml.parent.name
        skill = str(data.get("skill", ""))
        prompt = str(data.get("prompt", "")).strip()
        rubric = tuple(str(r) for r in data.get("rubric", []))
        if not (skill and prompt and rubric):
            raise CorpusError(f"{name}: case.yaml needs skill, prompt, and rubric")
        if not (root / "skills" / skill / "SKILL.md").is_file():
            raise CorpusError(f"{name}: names skill '{skill}', which does not exist")
        cases.append(
            Case(
                name=name,
                skill=skill,
                prompt=prompt,
                rubric=rubric,
                threshold=float(data.get("threshold", cfg.default_threshold)),
            )
        )
    return cases
