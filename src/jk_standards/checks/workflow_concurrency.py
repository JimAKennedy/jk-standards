"""workflow-concurrency: a concurrency group is either ref-scoped or a declared lock.

A `concurrency:` group is a mutex whose name is a string. Two runs sharing a
name queue; with `cancel-in-progress: false` GitHub cancels the older *pending*
entry once a third contender arrives. That is the right behaviour when the name
stands for something genuinely shared — a Pages deployment, a staging
environment — and a silent, repo-wide serialiser when it does not.

The failure mode is nasty because it does not look like a config bug. A group
that omits `github.ref` funnels every branch and every pull request into one
lock, so unrelated PRs cancel each other's jobs. The symptom is a CANCELLED job
and a failing aggregate gate on a pull request containing nothing wrong, which
reads as CI flake; it also only appears under concurrent load, so a quiet repo
looks fine right up until it does not.

This check makes the distinction explicit. Every `concurrency:` block — at the
workflow level and on individual jobs — must either:

  - carry a ref-scoping expression in its group (`github.ref` and friends), so
    each branch or PR gets its own lock; or
  - name a lock declared in `workflow_concurrency.global_locks`, which is how a
    deliberately repo-wide mutex says so out loud.

Anything else is reported at the `group:` line. A group built from an
expression that *contains* a ref token passes even if one branch of that
expression is a literal — a ternary yielding a global lock for a real deploy and
a ref-scoped name for a build-only smoke is exactly the intended shape.

Escape hatch: a `# concurrency-scope-ok: <reason>` marker on the `group:` line
or the line immediately above it suppresses the finding.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import output, workflows
from jk_standards.config import Config

_MARKER_RE = re.compile(r"#\s*concurrency-scope-ok\b")


def _is_ref_scoped(group: str, tokens: list[str]) -> bool:
    """True when the group text mentions any configured ref-scoping token."""
    return any(token in group for token in tokens)


def _suppressed(lines: list[str], lineno: int) -> bool:
    """True when the escape-hatch marker sits on the line or the one above."""
    if lineno < 1 or lineno > len(lines):
        return False
    if _MARKER_RE.search(lines[lineno - 1]):
        return True
    return lineno >= 2 and bool(_MARKER_RE.search(lines[lineno - 2]))


def _blocks(data: dict) -> list[tuple[tuple, object]]:
    """Return every ``(path, concurrency_value)`` in one workflow document."""
    found: list[tuple[tuple, object]] = []
    if "concurrency" in data:
        found.append((("concurrency",), data["concurrency"]))
    jobs = data.get("jobs")
    if isinstance(jobs, dict):
        for job_name, job in jobs.items():
            if isinstance(job, dict) and "concurrency" in job:
                found.append((("jobs", job_name, "concurrency"), job["concurrency"]))
    return found


def run(root: Path, cfg: Config) -> int:
    paths = workflows.iter_workflow_files(
        root, cfg.workflow_concurrency_dir, cfg.workflow_concurrency_extensions
    )
    if not paths:
        output.summary(
            f"workflow-concurrency: no workflows dir ({cfg.workflow_concurrency_dir}) — skipped"
        )
        return 0

    locks = set(cfg.workflow_concurrency_global_locks)
    tokens = cfg.workflow_concurrency_ref_tokens
    errors = 0
    groups = 0
    declared = 0

    for path in paths:
        data, node_lines = workflows.load_workflow(path)
        if not isinstance(data, dict):
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()

        for prefix, block in _blocks(data):
            # `concurrency: my-group` is the shorthand for `{group: my-group}`;
            # the group line is then the concurrency key's own line.
            if isinstance(block, str):
                group, key_path = block, prefix
            elif isinstance(block, dict):
                raw = block.get("group")
                if raw is None:
                    continue
                group, key_path = str(raw), prefix + ("group",)
            else:
                continue

            groups += 1
            if _is_ref_scoped(group, tokens):
                continue
            if group.strip() in locks:
                declared += 1
                continue

            lineno = node_lines.get(key_path, 1)
            if _suppressed(text, lineno):
                continue

            output.error(
                rel,
                lineno,
                f"concurrency group {group!r} is neither ref-scoped nor a declared "
                f"global lock — every branch and pull request shares this one "
                f"mutex, so unrelated runs cancel each other. Add a ref token "
                f"({tokens[0]}) to the group, list it under "
                f"workflow_concurrency.global_locks if the lock is deliberately "
                f"repo-wide, or add # concurrency-scope-ok: <reason>",
            )
            errors += 1

    if errors == 0:
        output.summary(
            f"workflow-concurrency: {groups} group(s), all ref-scoped or declared "
            f"({declared} declared global lock(s))"
        )
    return errors
