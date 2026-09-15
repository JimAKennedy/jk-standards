"""The two gitleaks version pins move together.

The gitleaks version is pinned in two files with different update
mechanisms: `pre-commit autoupdate` bumps the dev config's `rev:` but
nothing auto-bumps the shipped hook's `additional_dependencies`. Left
unguarded, the developers' daily gate and the consumers' shipped hook
silently diverge — exactly the drift this toolkit exists to catch. A
nonexistent tag needs no check (the hook's environment build fails
loudly); equality between the two files does.
"""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


def _shipped_hook_version() -> str:
    hooks = yaml.safe_load((REPO_ROOT / ".pre-commit-hooks.yaml").read_text(encoding="utf-8"))
    (hook,) = [h for h in hooks if h["id"] == "secrets-scan"]
    (dep,) = hook["additional_dependencies"]
    return dep.rpartition("@")[2]


def _dev_config_version() -> str:
    config = yaml.safe_load((REPO_ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    (repo,) = [r for r in config["repos"] if r["repo"].endswith("gitleaks/gitleaks")]
    return repo["rev"]


def test_gitleaks_pins_agree():
    shipped = _shipped_hook_version()
    dev = _dev_config_version()
    assert shipped == dev, (
        f"gitleaks pins have diverged: .pre-commit-hooks.yaml additional_dependencies "
        f"pins {shipped!r} but .pre-commit-config.yaml rev pins {dev!r} — bump them "
        f"together (autoupdate only moves the dev config), and rerun the staged-key "
        f"rejection demo recorded in docs/plans/skill-evals/evidence/M001-S01.md"
    )
