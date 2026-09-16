"""Results serialization with full provenance.

A score is never written without the models, run count, and thresholds
that produced it — a results file read months later must answer "what
exactly ran" by itself.
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from harness.config import EvalConfig


def median(scores: list[float]) -> float:
    return float(statistics.median(scores))


def write_results(
    path: Path, cfg: EvalConfig, cases: list[dict], extra: dict | None = None
) -> None:
    payload = {
        "provenance": {
            "agent_model": cfg.agent_model,
            "judge_model": cfg.judge_model,
            "runs": cfg.runs,
            "default_threshold": cfg.default_threshold,
            "max_output_tokens": cfg.max_output_tokens,
            "max_cases": cfg.max_cases,
        },
        "cases": [{**c, "median": median(list(c["scores"]))} for c in cases],
    }
    if extra:
        payload.update(extra)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
