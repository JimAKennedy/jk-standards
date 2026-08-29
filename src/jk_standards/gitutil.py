"""Git helpers for the diff-scoped checks (doc-drift) and release-pins."""

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


def commit_exists(root: Path, sha: str) -> bool | None:
    """Whether ``sha`` resolves to a commit, or ``None`` when git cannot say.

    ``None`` is deliberately distinct from ``False``, for the same reason
    :func:`list_tags` distinguishes them: outside a repository, or in a shallow
    clone whose history does not reach the commit, "cannot resolve" is not
    evidence of "does not exist". A caller must be able to skip rather than
    report a truthful record as fabricated on the strength of a thin checkout.
    """
    try:
        _git(root, "rev-parse", "--is-inside-work-tree")
    except (GitError, OSError):
        return None
    try:
        _git(root, "cat-file", "-e", f"{sha}^{{commit}}")
    except OSError:
        return None
    except GitError:
        # The object is not here. That is only evidence of fabrication when
        # the repository holds its whole history: in a truncated checkout —
        # pre-commit.ci, or any `fetch-depth: 1` CI job — a commit recorded
        # months ago is legitimately absent, and reporting it would fail a
        # truthful record on the strength of a thin clone.
        try:
            shallow = _git(root, "rev-parse", "--is-shallow-repository").strip()
        except (GitError, OSError):
            return None
        return None if shallow == "true" else False
    return True


def list_tags(root: Path) -> set[str] | None:
    """Every tag name in the repository, or ``None`` when they cannot be read.

    ``None`` is deliberately distinct from an empty set. A checkout with no
    tags fetched (the default for `actions/checkout`, which fetches none unless
    `fetch-depth: 0`) and a repository genuinely before its first release both
    yield nothing, and a caller must be able to skip rather than report every
    pin as dangling on the strength of an incomplete checkout.
    """
    try:
        out = _git(root, "tag", "--list")
    except (GitError, OSError):
        return None
    return {line.strip() for line in out.splitlines() if line.strip()}


def tracked_paths(root: Path) -> set[str] | None:
    """Every git-tracked working-tree path (repo-relative, posix), or ``None``.

    Returns the set produced by ``git ls-files`` — paths are already relative to
    the repository root and slash-separated on every platform. ``None`` is
    deliberately distinct from an empty set, mirroring :func:`list_tags`: it
    signals that tracking cannot be determined (``root`` is not a git repo, or
    git is unreadable) so a caller must *fail open* rather than treat every file
    as untracked. An empty set means a real repository that happens to track no
    files.
    """
    try:
        out = _git(root, "ls-files")
    except (GitError, OSError):
        return None
    return {line.strip() for line in out.splitlines() if line.strip()}


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


def file_diff(root: Path, base: str, path: str) -> str:
    merge_base = _git(root, "merge-base", base, "HEAD").strip()
    return _git(root, "diff", f"{merge_base}...HEAD", "--", path)


def last_touched_date(root: Path, base: str, path: str) -> str | None:
    """Author date (YYYY-MM-DD) of the last commit touching ``path`` in the diff range.

    Scoped to the ``merge-base(base, HEAD)..HEAD`` range so it answers "when was
    this doc last changed *on this branch*", matching the diff-scope of
    :func:`changed_files` — it never re-dates the whole history. Returns ``None``
    when the date cannot be determined: the range cannot be resolved (git
    unreadable, bad base), or ``path`` has no commit in the range (untouched, or
    changed only in the working tree). ``None`` is the None-sentinel signal for
    the caller to skip this doc's accuracy check rather than treat it as stale.
    """
    try:
        merge_base = _git(root, "merge-base", base, "HEAD").strip()
        out = _git(
            root,
            "log",
            "-1",
            "--format=%ad",
            "--date=short",
            f"{merge_base}..HEAD",
            "--",
            path,
        )
    except (GitError, OSError):
        return None
    date = out.strip()
    return date or None


def commit_trailers(root: Path, base: str, trailer: str) -> list[str]:
    """All `<trailer>: value` lines in commit messages on the PR range."""
    merge_base = _git(root, "merge-base", base, "HEAD").strip()
    log = _git(root, "log", "--format=%B", f"{merge_base}..HEAD")
    prefix = f"{trailer}:"
    return [line.strip() for line in log.splitlines() if line.startswith(prefix)]
