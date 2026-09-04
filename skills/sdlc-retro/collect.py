#!/usr/bin/env python3
"""Evidence collector for the sdlc-retro skill.

Walks the immediate subdirectories of --root, and for each git repository
extracts the evidence classes the skill's method interprets: weekly
commit/line volumes, Co-authored-by trailer variants, tooling-marker
first-appearance dates, and tags — plus a best-effort environment scan and
weekly token usage harvested from Claude Code transcripts. Writes one dated
JSON snapshot per run into --out.

Stdlib-only by design: this file travels with the skill when it is installed
into consuming repos, where nothing beyond Python 3.11 and git can be assumed.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import re
import subprocess
from datetime import date
from pathlib import Path

SCHEMA = 2

# Files whose first appearance in history dates a workflow change. Paths are
# relative to each repo root; directories cover any file added beneath them.
DEFAULT_MARKERS = (
    "CLAUDE.md",
    "AGENTS.md",
    ".claude",
    ".mcp.json",
    ".pre-commit-config.yaml",
    ".github/workflows",
    ".github/copilot-instructions.md",
    "jk-standards.yaml",
    "nfr-review.yaml",
    ".jk",
    ".gsd-id",
    ".planning",
    "skills-lock.json",
    "CHANGELOG.md",
    "docs/plans",
)


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _week(iso_date: str) -> str:
    year, week, _ = date.fromisoformat(iso_date).isocalendar()
    return f"{year}-W{week:02d}"


def _window_args(since: str | None, until: str) -> list[str]:
    # Both edges are enforced, not just recorded: a snapshot whose window.to
    # claims a date must not contain later commits (backdated regeneration,
    # clock skew), or two snapshots of the same window can disagree.
    args = [f"--until={until}T23:59:59"]
    if since:
        args.append(f"--since={since}")
    return args


def _weekly_volumes(repo: Path, since: str | None, until: str) -> tuple[dict, int]:
    args = ["log", "--format=COMMIT %as", "--numstat", *_window_args(since, until)]
    weekly: dict[str, dict[str, int]] = {}
    commit_count = 0
    current_week = None
    for line in _git(repo, *args).splitlines():
        if line.startswith("COMMIT "):
            commit_count += 1
            current_week = _week(line.split(" ", 1)[1])
            bucket = weekly.setdefault(
                current_week, {"commits": 0, "insertions": 0, "deletions": 0}
            )
            bucket["commits"] += 1
        elif line and current_week and "\t" in line:
            ins, dels, _path = line.split("\t", 2)
            bucket = weekly[current_week]
            if ins.isdigit():
                bucket["insertions"] += int(ins)
            if dels.isdigit():
                bucket["deletions"] += int(dels)
    return weekly, commit_count


def _trailer_variants(repo: Path, since: str | None, until: str) -> dict:
    args = [
        "log",
        "--format=%as\t%(trailers:key=Co-authored-by,valueonly,separator=%x1f)",
        *_window_args(since, until),
    ]
    variants: dict[str, dict] = {}
    for line in _git(repo, *args).splitlines():
        day, _, raw = line.partition("\t")
        for variant in filter(None, (v.strip() for v in raw.split("\x1f"))):
            entry = variants.setdefault(variant, {"first": day, "last": day, "count": 0})
            entry["count"] += 1
            # git log emits newest-first, so each earlier line pushes `first` back.
            entry["first"] = min(entry["first"], day)
            entry["last"] = max(entry["last"], day)
    return variants


def _marker_dates(repo: Path, markers: tuple[str, ...]) -> dict:
    found = {}
    for marker in markers:
        out = _git(repo, "log", "--reverse", "--diff-filter=A", "--format=%as", "--", marker)
        first = out.splitlines()[0] if out.splitlines() else None
        if first:
            found[marker] = first
    return found


def _tags(repo: Path) -> dict:
    tags = {}
    for tag in _git(repo, "for-each-ref", "refs/tags", "--format=%(refname:short)").splitlines():
        tags[tag] = _git(repo, "log", "-1", "--format=%as", tag).strip()
    return tags


def _mcp_servers(repo: Path) -> dict:
    mcp_path = repo / ".mcp.json"
    if not mcp_path.is_file():
        return {}
    try:
        config = json.loads(mcp_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    servers = {}
    for name, spec in config.get("mcpServers", {}).items():
        command = " ".join([spec.get("command", ""), *spec.get("args", [])]).strip()
        servers[name] = command
    return servers


def _environment(claude_dir: Path) -> dict:
    env = {}
    plugins_manifest = claude_dir / "plugins" / "installed_plugins.json"
    if plugins_manifest.is_file():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            env["plugins"] = json.loads(plugins_manifest.read_text(encoding="utf-8"))
    return env


def _token_usage(claude_dir: Path, root: Path) -> dict:
    # Claude Code transcripts are the only per-token record and they are
    # ephemeral (the transcript cleanup period deletes them after ~30 days),
    # so every run scans everything still readable rather than applying the
    # --since window: a windowed scan would permanently drop never-banked
    # usage at the window's left edge. Retention supplies the left edge.
    projects = claude_dir / "projects"
    if not projects.is_dir():
        return {}

    def munge(text: str) -> str:
        return re.sub(r"[^A-Za-z0-9]", "-", text)

    # Transcript dirs are named by munged cwd; a repo's worktrees munge to the
    # repo's dir name plus a suffix. Longest repo name first so e.g. a repo
    # "midi" cannot claim "midi-filter"'s transcripts.
    prefix = munge(str(root))
    repo_names = sorted((p.name for p in Path(root).iterdir() if p.is_dir()), key=len, reverse=True)
    usage: dict[str, dict] = {}
    for project in sorted(p for p in projects.iterdir() if p.is_dir()):
        owner = project.name
        for repo in repo_names:
            munged_repo = f"{prefix}-{munge(repo)}"
            if project.name == munged_repo or project.name.startswith(munged_repo + "-"):
                owner = repo
                break
        seen: set[tuple] = set()
        weekly = usage.setdefault(owner, {})
        for transcript in sorted(project.glob("*.jsonl")):
            try:
                lines = transcript.read_text(encoding="utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict) or obj.get("type") != "assistant":
                    continue
                message = obj.get("message") or {}
                tokens = message.get("usage")
                timestamp = obj.get("timestamp")
                if not isinstance(tokens, dict) or not timestamp:
                    continue
                # A streamed response can be rewritten to the transcript under
                # the same message id + request id; count it once.
                key = (message.get("id"), obj.get("requestId"))
                if key != (None, None):
                    if key in seen:
                        continue
                    seen.add(key)
                try:
                    week = _week(timestamp[:10])
                except ValueError:
                    continue
                bucket = weekly.setdefault(week, {}).setdefault(
                    message.get("model") or "unknown",
                    {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0},
                )
                bucket["input"] += tokens.get("input_tokens") or 0
                bucket["output"] += tokens.get("output_tokens") or 0
                bucket["cache_read"] += tokens.get("cache_read_input_tokens") or 0
                bucket["cache_creation"] += tokens.get("cache_creation_input_tokens") or 0
    return {owner: weeks for owner, weeks in usage.items() if weeks}


def _resolve_since(out: Path, since: str | None, today: str) -> str | None:
    if since != "auto":
        return since
    if not out.is_dir():
        return None
    # A same-day (or future-dated) snapshot is this run's own output or a
    # backdating mistake, not a previous period — using it as the window
    # start would make a same-day rerun collect a degenerate today→today
    # window. The previous period is the latest snapshot dated before today.
    snapshots = sorted(p.stem for p in out.glob("*.json") if p.stem < today)
    return snapshots[-1] if snapshots else None


def collect(
    root: Path,
    out: Path,
    today: str | None = None,
    since: str | None = None,
    claude_dir: Path | None = None,
    markers: tuple[str, ...] = DEFAULT_MARKERS,
) -> Path:
    """Collect one snapshot and return the path it was written to."""
    today = today or date.today().isoformat()
    window_from = _resolve_since(out, since, today)
    repos = {}
    unreadable = []
    for repo in sorted(p for p in Path(root).iterdir() if p.is_dir()):
        if not (repo / ".git").exists():
            continue
        try:
            weekly, commit_count = _weekly_volumes(repo, window_from, today)
        except subprocess.CalledProcessError:
            # e.g. an orphaned worktree whose .git file points at a deleted
            # gitdir — record the skip so nothing vanishes silently.
            unreadable.append(repo.name)
            continue
        repos[repo.name] = {
            "commit_count": commit_count,
            "weekly": weekly,
            "trailers": _trailer_variants(repo, window_from, today),
            # Always full-history: first-appearance dates must not shift with
            # the collection window.
            "markers": _marker_dates(repo, markers),
            "tags": _tags(repo),
            "mcp_servers": _mcp_servers(repo),
        }
    resolved_claude_dir = claude_dir if claude_dir else Path.home() / ".claude"
    snapshot = {
        "schema": SCHEMA,
        "collected_on": today,
        "root": str(root),
        "window": {"from": window_from, "to": today},
        "repos": repos,
        "unreadable": unreadable,
        "environment": _environment(resolved_claude_dir),
        "token_usage": _token_usage(resolved_claude_dir, Path(root)),
    }
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{today}.json"
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, required=True, help="directory whose subdirs are the repos"
    )
    parser.add_argument("--out", type=Path, required=True, help="snapshot directory")
    parser.add_argument(
        "--since", default=None, help="'auto' = window from the latest snapshot in --out"
    )
    parser.add_argument(
        "--claude-dir", type=Path, default=None, help="Claude home for the environment scan"
    )
    parser.add_argument("--today", default=None, help="override the snapshot date (YYYY-MM-DD)")
    args = parser.parse_args()
    path = collect(
        root=args.root,
        out=args.out,
        today=args.today,
        since=args.since,
        claude_dir=args.claude_dir,
    )
    print(path)


if __name__ == "__main__":
    main()
