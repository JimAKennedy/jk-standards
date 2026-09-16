"""Skill-selection eval: does the model pick the right skill from the
inventory? (part of the `eval` validation token, judge-free)

The agent model sees every skill's name and description exactly as the
generated inventory records them, plus one task statement, and must answer
with a single skill name — or `none` when nothing applies. Scored by exact
match; a failure here means a description's trigger phrasing does not do
its job, which no other check can see.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "evals"))

from harness import config as hconfig  # noqa: E402

pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — run via `make eval` with .env present",
)

CFG = hconfig.load_config(ROOT)

# One task statement per corpus skill, plus a negative where no skill
# applies. Expected answers are exact skill names from the inventory.
SELECTION = [
    (
        "I need to save synth presets to disk so future versions of the "
        "plugin can still load files written by old versions.",
        "versioned-state-serialization",
    ),
    (
        "My audio processing callback occasionally glitches; I suspect "
        "something inside it is blocking or allocating.",
        "realtime-audio-safety",
    ),
    (
        "Our docs keep going stale — counts are wrong and status lines "
        "say 'current' about things that changed months ago.",
        "doc-anti-drift",
    ),
    (
        "Update the npm dependencies in the website package to their "
        "latest minor versions.",
        "none",
    ),
]


def _inventory() -> str:
    data = json.loads(
        (ROOT / "site/src/generated/skills.json").read_text(encoding="utf-8")
    )
    return "\n".join(f"- {s['name']}: {s['description']}" for s in data["skills"])


def _client():
    import anthropic

    headers = {}
    workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID")
    if workspace:
        headers["anthropic-workspace-id"] = workspace
    return anthropic.Anthropic(default_headers=headers or None)


@pytest.mark.parametrize(("task", "expected"), SELECTION, ids=[e for _, e in SELECTION])
def test_skill_selection(task, expected):
    client = _client()
    prompt = (
        "Here is a catalog of engineering skills:\n\n"
        f"{_inventory()}\n\n"
        f"Task: {task}\n\n"
        "Answer with exactly one skill name from the catalog that applies "
        "to the task, or the single word `none` if no listed skill applies. "
        "Answer with only that word."
    )
    resp = client.messages.create(
        model=CFG.agent_model,
        max_tokens=CFG.max_output_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    answer = (
        "".join(getattr(b, "text", "") for b in resp.content)
        .strip()
        .strip("`")
        .lower()
    )
    assert answer == expected, f"selection: expected {expected!r}, got {answer!r}"
