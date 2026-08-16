"""workflow-permissions: a reusable-workflow caller grants what its callee needs.

A `workflow_call` producer can never exceed the token scope its caller was
granted. If `ci.yml` grants `contents: read` and calls a reusable workflow whose
own `permissions:` block asks for `pages: write`, the run does not fail *inside*
a job — it fails to compose, before any job starts, as a `startup_failure` with
zero annotations. Nothing points at the cause, and a green-looking PR can hide
it entirely when the callee only exists on the branch.

This check reads that relationship statically. For every job that calls a local
reusable workflow (`uses: ./…`), it resolves the caller's effective grant and
compares it against the union of every scope the callee requests — top-level and
per-job, since a job-level `permissions:` block inside the callee is bounded by
the same ceiling. A scope the callee asks for and the caller does not confer is
reported at the `uses:` line.

Two deliberate silences keep the check honest rather than noisy:

  - A caller that declares no `permissions:` block at all is skipped. The
    effective grant then comes from a repository-level default this check cannot
    see, so any finding would be a guess.
  - A callee that declares no `permissions:` anywhere requests nothing, so there
    is nothing to satisfy.

Only local `./…` callees are resolved. A `owner/repo/.github/workflows/x.yml@sha`
reference lives outside the tree and cannot be read from disk.

Escape hatch: a `# workflow-permissions-ok: <reason>` marker on the `uses:` line
or the line immediately above it suppresses the finding.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import output, workflows
from jk_standards.config import Config

_MARKER_RE = re.compile(r"#\s*workflow-permissions-ok\b")
_LEVEL_NAMES = {0: "none", 1: "read", 2: "write"}


def _required_scopes(callee: object) -> dict[str, int]:
    """Union every scope a callee workflow requests, at its highest level.

    Both the workflow-level block and each job's block count: the ceiling
    applies to the whole called workflow, so a single job asking for
    `issues: write` makes the caller's grant insufficient without it.
    """
    required: dict[str, int] = {}
    if not isinstance(callee, dict):
        return required

    def absorb(value: object) -> None:
        grant = workflows.normalise_permissions(value)
        if not grant:
            return
        for scope, level in grant.items():
            required[scope] = max(required.get(scope, 0), level)

    absorb(callee.get("permissions"))
    jobs = callee.get("jobs")
    if isinstance(jobs, dict):
        for job in jobs.values():
            if isinstance(job, dict):
                absorb(job.get("permissions"))
    return required


def _caller_grant(workflow: dict, job: dict) -> dict[str, int] | None:
    """Effective grant for a calling job: its own block, else the workflow's.

    Returns ``None`` when neither declares one — the repository default applies
    and is not knowable from the tree.
    """
    job_grant = workflows.normalise_permissions(job.get("permissions"))
    if job_grant is not None:
        return job_grant
    return workflows.normalise_permissions(workflow.get("permissions"))


def _suppressed(lines: list[str], lineno: int) -> bool:
    """True when the escape-hatch marker sits on the line or the one above."""
    if lineno < 1 or lineno > len(lines):
        return False
    if _MARKER_RE.search(lines[lineno - 1]):
        return True
    return lineno >= 2 and bool(_MARKER_RE.search(lines[lineno - 2]))


def run(root: Path, cfg: Config) -> int:
    paths = workflows.iter_workflow_files(root, cfg.workflow_perm_dir, cfg.workflow_perm_extensions)
    if not paths:
        output.summary(
            f"workflow-permissions: no workflows dir ({cfg.workflow_perm_dir}) — skipped"
        )
        return 0

    # Callees are parsed once and reused: ci.yml alone calls deploy-site.yml
    # twice, and a repo of any size re-references the same producers.
    cache: dict[Path, dict[str, int]] = {}
    errors = 0
    edges = 0

    for path in paths:
        data, node_lines = workflows.load_workflow(path)
        if not isinstance(data, dict):
            continue
        jobs = data.get("jobs")
        if not isinstance(jobs, dict):
            continue
        rel = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()

        for job_name, job in jobs.items():
            if not isinstance(job, dict):
                continue
            uses = job.get("uses")
            if not isinstance(uses, str) or not uses.strip().startswith("./"):
                continue

            # removeprefix, not lstrip: lstrip takes a character *set*, so
            # "./.github/…" would lose the leading dot of ".github" too.
            callee_path = root / uses.strip().removeprefix("./")
            if not callee_path.is_file():
                # A `./` ref to a file that is not there is GitHub's error to
                # raise at compose time; inventing a permissions finding here
                # would just mislabel it.
                continue
            edges += 1

            grant = _caller_grant(data, job)
            if grant is None:
                continue  # repository default — unknowable, so unjudgeable

            if callee_path not in cache:
                callee_data, _ = workflows.load_workflow(callee_path)
                cache[callee_path] = _required_scopes(callee_data)
            required = cache[callee_path]

            missing = sorted(
                (scope, need)
                for scope, need in required.items()
                if workflows.granted_level(grant, scope) < need
            )
            if not missing:
                continue

            lineno = node_lines.get(("jobs", job_name, "uses"), 1)
            if _suppressed(text, lineno):
                continue

            detail = ", ".join(
                f"{'all scopes' if scope == workflows.ALL_SCOPES else scope}: {_LEVEL_NAMES[need]}"
                for scope, need in missing
            )
            output.error(
                rel,
                lineno,
                f"job '{job_name}' calls {uses.strip()} but does not grant the "
                f"permissions it declares ({detail}) — a callee can never exceed "
                f"its caller's scope, so the run fails to compose before any job "
                f"starts (or add # workflow-permissions-ok: <reason>)",
            )
            errors += 1

    if errors == 0:
        output.summary(
            f"workflow-permissions: {edges} reusable-workflow call(s), "
            f"all within the caller's grant"
        )
    return errors
