"""gitutil tests: real git fixture repos + monkeypatched fetch for CI branches."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from jk_standards import gitutil
from jk_standards.gitutil import (
    GitError,
    changed_files,
    commit_trailers,
    file_diff,
    last_touched_date,
    resolve_base_ref,
    tracked_paths,
)


def _run(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _run(root, "init", "-q", "-b", "main")
    _run(root, "config", "user.email", "test@example.com")
    _run(root, "config", "user.name", "Test User")
    _run(root, "config", "commit.gpgsign", "false")


def _commit(root: Path, path: str, content: str, msg: str) -> None:
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(content, encoding="utf-8")
    _run(root, "add", path)
    _run(root, "commit", "-q", "-m", msg)


@pytest.fixture
def repo(tmp_path):
    """Fresh git repo on `main` with one initial commit and a fake `origin/main` ref."""
    _init_repo(tmp_path)
    _commit(tmp_path, "seed.txt", "seed\n", "initial")
    # Fake an origin/main pointer at HEAD so resolve_base_ref finds it without a real remote.
    _run(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path


# --- _git failure path ------------------------------------------------------


def test_git_failure_raises_giterror(tmp_path):
    _init_repo(tmp_path)
    # rev-parse an unknown ref → non-zero exit → GitError with stderr.
    with pytest.raises(GitError, match="git rev-parse"):
        gitutil._git(tmp_path, "rev-parse", "--verify", "does-not-exist")


# --- resolve_base_ref: three branches ---------------------------------------


def test_resolve_base_ref_uses_override(repo, monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    _run(repo, "update-ref", "refs/heads/feature-base", "HEAD")
    assert resolve_base_ref(repo, "feature-base") == "feature-base"


def test_resolve_base_ref_uses_github_env(repo, monkeypatch):
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    # origin/main already exists in the fixture.
    assert resolve_base_ref(repo, None) == "origin/main"


def test_resolve_base_ref_default_origin_main(repo, monkeypatch):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    assert resolve_base_ref(repo, None) == "origin/main"


# --- resolve_base_ref: fetch-fallback branches ------------------------------


def test_resolve_base_ref_fetches_when_ref_missing(tmp_path, monkeypatch):
    """When the ref isn't local, resolve_base_ref runs `git fetch origin <bare> --depth=100`.

    We can't hit a real remote in a test, so monkeypatch _git: rev-parse fails,
    fetch is recorded and returns "", then resolve_base_ref returns the base name.
    """
    _init_repo(tmp_path)
    _commit(tmp_path, "seed.txt", "seed\n", "initial")
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    calls: list[tuple[str, ...]] = []

    def fake_git(root, *args):
        calls.append(args)
        if args[:2] == ("rev-parse", "--verify"):
            raise GitError("not found")
        if args[0] == "fetch":
            return ""
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(gitutil, "_git", fake_git)
    assert resolve_base_ref(tmp_path, None) == "origin/main"
    assert calls == [
        ("rev-parse", "--verify", "origin/main"),
        ("fetch", "origin", "main", "--depth=100"),
    ]


def test_resolve_base_ref_hard_fails_when_fetch_fails(tmp_path, monkeypatch):
    _init_repo(tmp_path)
    _commit(tmp_path, "seed.txt", "seed\n", "initial")
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    def fake_git(root, *args):
        if args[:2] == ("rev-parse", "--verify"):
            raise GitError("not found")
        if args[0] == "fetch":
            raise GitError("network down")
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(gitutil, "_git", fake_git)
    with pytest.raises(GitError, match="cannot resolve base ref origin/main"):
        resolve_base_ref(tmp_path, None)


def test_resolve_base_ref_override_without_origin_prefix(tmp_path, monkeypatch):
    """Non-origin base override still fetches the bare name on fallback."""
    _init_repo(tmp_path)
    _commit(tmp_path, "seed.txt", "seed\n", "initial")
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)

    calls: list[tuple[str, ...]] = []

    def fake_git(root, *args):
        calls.append(args)
        if args[:2] == ("rev-parse", "--verify"):
            raise GitError("not found")
        if args[0] == "fetch":
            return ""
        raise AssertionError(f"unexpected git call: {args}")

    monkeypatch.setattr(gitutil, "_git", fake_git)
    resolve_base_ref(tmp_path, "release/1.2")
    # bare = base.removeprefix("origin/") — no prefix, so bare == base
    assert ("fetch", "origin", "release/1.2", "--depth=100") in calls


# --- tracked_paths ----------------------------------------------------------


def test_tracked_paths_lists_committed_files(repo):
    _commit(repo, "docs/a.md", "a\n", "add a")
    result = tracked_paths(repo)
    assert result == {"seed.txt", "docs/a.md"}


def test_tracked_paths_excludes_untracked_and_ignored(repo):
    _commit(repo, ".gitignore", "ignored.txt\n", "add gitignore")
    (repo / "untracked.txt").write_text("u\n", encoding="utf-8")
    (repo / "ignored.txt").write_text("i\n", encoding="utf-8")
    result = tracked_paths(repo)
    assert result == {"seed.txt", ".gitignore"}
    assert "untracked.txt" not in result
    assert "ignored.txt" not in result


def test_tracked_paths_uses_posix_separators(repo):
    _commit(repo, "docs/nested/deep.md", "d\n", "add nested")
    result = tracked_paths(repo)
    assert "docs/nested/deep.md" in result
    assert not any("\\" in p for p in result)


def test_tracked_paths_none_when_not_a_repo(tmp_path):
    # A bare tmp dir is not a git repo → git ls-files exits non-zero → None (fail open).
    assert tracked_paths(tmp_path) is None


def test_tracked_paths_none_when_git_unreadable(tmp_path, monkeypatch):
    def fake_git(root, *args):
        raise GitError("git unreadable")

    monkeypatch.setattr(gitutil, "_git", fake_git)
    assert tracked_paths(tmp_path) is None


def test_tracked_paths_none_on_oserror(tmp_path, monkeypatch):
    def fake_git(root, *args):
        raise OSError("git binary missing")

    monkeypatch.setattr(gitutil, "_git", fake_git)
    assert tracked_paths(tmp_path) is None


# --- changed_files ----------------------------------------------------------


def test_changed_files_lists_diff_since_base(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "docs/new.md", "new\n", "add doc")
    _commit(repo, "src/mod.py", "x = 1\n", "add src")
    result = changed_files(repo, "main")
    assert sorted(result) == ["docs/new.md", "src/mod.py"]


def test_changed_files_empty_when_no_diff(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    assert changed_files(repo, "main") == []


# --- file_diff --------------------------------------------------------------


def test_file_diff_returns_unified_diff(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "docs/a.md", "hello world\n", "add a")
    diff = file_diff(repo, "main", "docs/a.md")
    assert "+hello world" in diff
    assert "docs/a.md" in diff


# --- commit_trailers --------------------------------------------------------


def test_commit_trailers_finds_matching_lines(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    _commit(
        repo,
        "docs/a.md",
        "x\n",
        "add a\n\nDocs-Not-Affected: refactor only\nSigned-off-by: dev\n",
    )
    _commit(
        repo,
        "docs/b.md",
        "y\n",
        "add b\n\nDocs-Not-Affected: docs pending followup\n",
    )
    trailers = commit_trailers(repo, "main", "Docs-Not-Affected")
    # `git log` returns newest-first, so the second commit appears first.
    assert trailers == [
        "Docs-Not-Affected: docs pending followup",
        "Docs-Not-Affected: refactor only",
    ]


def test_commit_trailers_returns_empty_when_absent(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "docs/a.md", "x\n", "add a with no trailer")
    assert commit_trailers(repo, "main", "Docs-Not-Affected") == []


# --- last_touched_date ------------------------------------------------------


def _commit_dated(root: Path, path: str, content: str, msg: str, date: str) -> None:
    """Commit `path` with a fixed author+committer date (YYYY-MM-DD)."""
    (root / path).parent.mkdir(parents=True, exist_ok=True)
    (root / path).write_text(content, encoding="utf-8")
    subprocess.run(["git", "add", path], cwd=root, check=True, capture_output=True)
    stamp = f"{date}T12:00:00"
    env = {"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp}
    subprocess.run(
        ["git", "commit", "-q", "-m", msg],
        cwd=root,
        check=True,
        capture_output=True,
        env={**os.environ, **env},
    )


def test_last_touched_date_returns_last_commit_date(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    _commit_dated(repo, "docs/a.md", "v1\n", "add a", "2024-01-10")
    assert last_touched_date(repo, "main", "docs/a.md") == "2024-01-10"


def test_last_touched_date_picks_most_recent_of_several(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    _commit_dated(repo, "docs/a.md", "v1\n", "first", "2024-01-10")
    _commit_dated(repo, "docs/a.md", "v2\n", "second", "2024-03-20")
    assert last_touched_date(repo, "main", "docs/a.md") == "2024-03-20"


def test_last_touched_date_none_when_path_untouched_in_range(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    _commit(repo, "docs/other.md", "x\n", "touch other")
    # docs/a.md was never committed on this branch → no commit in range → None.
    assert last_touched_date(repo, "main", "docs/a.md") is None


def test_last_touched_date_none_when_only_in_working_tree(repo):
    _run(repo, "checkout", "-q", "-b", "feature")
    (repo / "docs" / "a.md").parent.mkdir(parents=True, exist_ok=True)
    (repo / "docs" / "a.md").write_text("uncommitted\n", encoding="utf-8")
    # Present but never committed → no commit touches it → None (skip accuracy check).
    assert last_touched_date(repo, "main", "docs/a.md") is None


def test_last_touched_date_none_when_range_unresolvable(tmp_path, monkeypatch):
    def fake_git(root, *args):
        raise GitError("bad base ref")

    monkeypatch.setattr(gitutil, "_git", fake_git)
    assert last_touched_date(tmp_path, "origin/main", "docs/a.md") is None


def test_last_touched_date_none_on_oserror(tmp_path, monkeypatch):
    def fake_git(root, *args):
        raise OSError("git binary missing")

    monkeypatch.setattr(gitutil, "_git", fake_git)
    assert last_touched_date(tmp_path, "origin/main", "docs/a.md") is None
