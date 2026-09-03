"""sdlc-retro collector tests: real git fixture repos, dated commits, snapshot shape.

The collector lives beside its skill (skills/sdlc-retro/collect.py) rather than
in src/, so it is loaded here by file path. It must stay stdlib-only: it travels
with the skill into consuming repos via the skills installer.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

_COLLECT_PY = Path(__file__).resolve().parents[1] / "skills" / "sdlc-retro" / "collect.py"


def _load_collect():
    spec = importlib.util.spec_from_file_location("sdlc_retro_collect", _COLLECT_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


collect_mod = _load_collect()


def _run(root: Path, *args: str, date: str | None = None) -> None:
    env = None
    if date is not None:
        import os

        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = f"{date}T12:00:00"
        env["GIT_COMMITTER_DATE"] = f"{date}T12:00:00"
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, env=env)


def _init_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    _run(root, "init", "-q", "-b", "main")
    _run(root, "config", "user.email", "test@example.com")
    _run(root, "config", "user.name", "Test User")
    _run(root, "config", "commit.gpgsign", "false")


def _commit(root: Path, path: str, content: str, msg: str, date: str) -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(content, encoding="utf-8")
    _run(root, "add", path)
    _run(root, "commit", "-q", "-m", msg, date=date)


@pytest.fixture
def portfolio(tmp_path):
    """A --root dir holding one repo with three dated commits, plus a non-repo dir."""
    root = tmp_path / "dev"
    repo = root / "alpha"
    _init_repo(repo)
    _commit(repo, "a.txt", "one\n", "feat: first", date="2026-01-05")
    _commit(
        repo,
        "CLAUDE.md",
        "# instructions\n",
        "chore: add CLAUDE.md\n\nCo-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>",
        date="2026-01-06",
    )
    _commit(
        repo,
        "b.txt",
        "two\nthree\n",
        "feat: second\n\nCo-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>",
        date="2026-02-10",
    )
    _run(repo, "tag", "v0.1.0")
    (root / "not-a-repo").mkdir()
    (root / "not-a-repo" / "junk.txt").write_text("x\n", encoding="utf-8")
    return root


def _snapshot(root: Path, out: Path, **kwargs):
    path = collect_mod.collect(root=root, out=out, today="2026-03-01", **kwargs)
    return path, json.loads(path.read_text(encoding="utf-8"))


# --- repo discovery and shape ----------------------------------------------


def test_snapshot_lists_repos_and_skips_non_repos(portfolio, tmp_path):
    path, snap = _snapshot(portfolio, tmp_path / "snaps")
    assert path.name == "2026-03-01.json"
    assert set(snap["repos"]) == {"alpha"}
    assert snap["repos"]["alpha"]["commit_count"] == 3
    assert snap["schema"] == 1


def test_weekly_commit_and_line_volumes(portfolio, tmp_path):
    _, snap = _snapshot(portfolio, tmp_path / "snaps")
    weekly = snap["repos"]["alpha"]["weekly"]
    # 2026-01-05/06 fall in ISO week 2026-W02; 2026-02-10 in 2026-W07.
    assert weekly["2026-W02"]["commits"] == 2
    assert weekly["2026-W07"]["commits"] == 1
    assert weekly["2026-W07"]["insertions"] == 2


def test_trailer_variants_carry_first_last_and_count(portfolio, tmp_path):
    _, snap = _snapshot(portfolio, tmp_path / "snaps")
    trailers = snap["repos"]["alpha"]["trailers"]
    v46 = trailers["Claude Opus 4.6 <noreply@anthropic.com>"]
    assert v46 == {"first": "2026-01-06", "last": "2026-01-06", "count": 1}
    assert trailers["Claude Opus 4.7 <noreply@anthropic.com>"]["first"] == "2026-02-10"


def test_marker_first_appearance_dates(portfolio, tmp_path):
    _, snap = _snapshot(portfolio, tmp_path / "snaps")
    assert snap["repos"]["alpha"]["markers"]["CLAUDE.md"] == "2026-01-06"
    # Markers that never appeared are omitted, not null-filled.
    assert "jk-standards.yaml" not in snap["repos"]["alpha"]["markers"]


def test_tags_recorded_with_dates(portfolio, tmp_path):
    _, snap = _snapshot(portfolio, tmp_path / "snaps")
    assert snap["repos"]["alpha"]["tags"]["v0.1.0"] == "2026-02-10"


# --- incremental (--since auto) --------------------------------------------


def test_since_auto_limits_window_to_new_commits(portfolio, tmp_path):
    out = tmp_path / "snaps"
    _snapshot(portfolio, out)  # baseline on 2026-03-01
    _commit(portfolio / "alpha", "c.txt", "new\n", "feat: third", date="2026-03-20")
    path = collect_mod.collect(root=portfolio, out=out, today="2026-04-01", since="auto")
    snap = json.loads(path.read_text(encoding="utf-8"))
    weekly = snap["repos"]["alpha"]["weekly"]
    assert snap["window"]["from"] == "2026-03-01"
    assert list(weekly) == ["2026-W12"]
    # Marker scan stays full-history even in a windowed run: first-appearance
    # dates are the point of the exercise and must not shift with the window.
    assert snap["repos"]["alpha"]["markers"]["CLAUDE.md"] == "2026-01-06"


def test_since_auto_ignores_same_day_snapshot_on_rerun(portfolio, tmp_path):
    # Re-collecting on the same day must not treat the just-written snapshot
    # as the previous one — that yields a degenerate today→today window.
    # The window should come from the latest snapshot dated BEFORE today.
    out = tmp_path / "snaps"
    _snapshot(portfolio, out)  # 2026-03-01 baseline
    collect_mod.collect(root=portfolio, out=out, today="2026-04-01", since="auto")
    path = collect_mod.collect(root=portfolio, out=out, today="2026-04-01", since="auto")
    snap = json.loads(path.read_text(encoding="utf-8"))
    assert snap["window"]["from"] == "2026-03-01"


def test_window_end_is_enforced_not_just_recorded(portfolio, tmp_path):
    # A snapshot claiming window.to = 2026-01-31 must not contain commits made
    # after that date (backdated regeneration, clock skew) — otherwise two
    # snapshots of the same window can disagree and diffs lie.
    path = collect_mod.collect(root=portfolio, out=tmp_path / "snaps", today="2026-01-31")
    snap = json.loads(path.read_text(encoding="utf-8"))
    assert snap["repos"]["alpha"]["commit_count"] == 2
    assert "2026-W07" not in snap["repos"]["alpha"]["weekly"]
    assert "Claude Opus 4.7 <noreply@anthropic.com>" not in snap["repos"]["alpha"]["trailers"]


def test_since_auto_without_prior_snapshot_is_full_history(portfolio, tmp_path):
    _, snap = _snapshot(portfolio, tmp_path / "empty-snaps", since="auto")
    assert snap["window"]["from"] is None
    assert snap["repos"]["alpha"]["commit_count"] == 3


def test_broken_gitdir_pointer_is_recorded_not_fatal(portfolio, tmp_path):
    # An orphaned worktree leaves a .git *file* pointing at a gitdir that no
    # longer exists; git commands there exit 128. The collector must survive
    # and record the skip rather than silently dropping the directory.
    broken = portfolio / "orphan"
    broken.mkdir()
    (broken / ".git").write_text("gitdir: /nonexistent/worktrees/orphan\n", encoding="utf-8")
    _, snap = _snapshot(portfolio, tmp_path / "snaps")
    assert "orphan" not in snap["repos"]
    assert snap["unreadable"] == ["orphan"]


# --- environment scan -------------------------------------------------------


def test_mcp_servers_recorded_per_repo(portfolio, tmp_path):
    mcp = {"mcpServers": {"gsd-workflow": {"command": "npx", "args": ["@opengsd/gsd-pi@1.16.0"]}}}
    (portfolio / "alpha" / ".mcp.json").write_text(json.dumps(mcp), encoding="utf-8")
    _, snap = _snapshot(portfolio, tmp_path / "snaps")
    assert snap["repos"]["alpha"]["mcp_servers"]["gsd-workflow"] == "npx @opengsd/gsd-pi@1.16.0"


def test_environment_plugins_from_claude_dir(portfolio, tmp_path):
    claude = tmp_path / "claude-home"
    (claude / "plugins").mkdir(parents=True)
    manifest = {"superpowers": {"version": "6.3.0", "installedAt": "2026-08-25T14:57:56Z"}}
    (claude / "plugins" / "installed_plugins.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    _, snap = _snapshot(portfolio, tmp_path / "snaps", claude_dir=claude)
    assert snap["environment"]["plugins"] == manifest


def test_missing_claude_dir_yields_empty_environment(portfolio, tmp_path):
    _, snap = _snapshot(portfolio, tmp_path / "snaps", claude_dir=tmp_path / "nope")
    assert snap["environment"] == {}
