"""Read the region:skill-evals-config block of jk-standards.yaml.

The block is plain YAML inside the repo config; every knob a score depends
on lives here so a results file can record exactly what produced it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class EvalConfig:
    agent_model: str
    judge_model: str
    runs: int
    default_threshold: float
    max_output_tokens: int
    max_cases: int


def load_config(root: Path) -> EvalConfig:
    data = yaml.safe_load((root / "jk-standards.yaml").read_text(encoding="utf-8")) or {}
    block = data.get("skill_evals") or {}
    return EvalConfig(
        agent_model=str(block.get("agent_model", "claude-sonnet-5")),
        judge_model=str(block.get("judge_model", "claude-sonnet-5")),
        runs=int(block.get("runs", 3)),
        default_threshold=float(block.get("default_threshold", 0.6)),
        max_output_tokens=int(block.get("max_output_tokens", 1500)),
        max_cases=int(block.get("max_cases", 40)),
    )
