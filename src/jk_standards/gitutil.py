"""Git helpers for the diff-scoped checks (doc-drift)."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


class GitError(Exception):
    pass


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise GitError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


def resolve_base_ref(root: Path, base_override: str | None) -> str:
    """--base flag, then GITHUB_BASE_REF (GitHub Actions), then origin/main.

    If the ref is not present locally (shallow CI checkout), fetch it
    just-in-time; failure is loud, never a silent skip.
    """
    if base_override:
        base = base_override
    elif os.environ.get("GITHUB_BASE_REF"):
        base = f"origin/{os.environ['GITHUB_BASE_REF']}"
    else:
        base = "origin/main"

    try:
        _git(root, "rev-parse", "--verify", base)
    except GitError:
        bare = base.removeprefix("origin/")
        try:
            _git(root, "fetch", "origin", bare, "--depth=100")
        except GitError as e:
            raise GitError(f"cannot resolve base ref {base}: {e}") from e
    return base


def changed_files(root: Path, base: str) -> list[str]:
    merge_base = _git(root, "merge-base", base, "HEAD").strip()
    diff = _git(root, "diff", "--name-only", f"{merge_base}...HEAD")
    return [line for line in diff.splitlines() if line]


def commit_trailers(root: Path, base: str, trailer: str) -> list[str]:
    """All `<trailer>: value` lines in commit messages on the PR range."""
    merge_base = _git(root, "merge-base", base, "HEAD").strip()
    log = _git(root, "log", "--format=%B", f"{merge_base}..HEAD")
    prefix = f"{trailer}:"
    return [line.strip() for line in log.splitlines() if line.startswith(prefix)]
