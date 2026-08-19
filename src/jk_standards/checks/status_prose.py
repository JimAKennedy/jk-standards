"""status-prose: ban stale progress-tracking prose in gated docs.

Two rules, applied only to docs whose front-matter class is `gated`:

  1. `Status:` lines must carry a `(YYYY-MM-DD)` date anchor — undated
     status is a permanent lie in waiting.
  2. Forbidden progress phrases ("not yet implemented", phase tracking,
     TODO-count claims) are rejected outright; that state belongs in
     CHANGELOG/issues/dashboards, not in prose that describes contracts.

Archived and generated docs are never checked.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

from jk_standards import frontmatter, gitutil, output
from jk_standards.config import Config, iter_docs

# Repeated verbatim by the two progress-claim patterns below; named once so the
# wording cannot drift between them.
_PROGRESS_CLAIM = (
    "progress claim — describe the current contract or delete; state belongs in CHANGELOG/issues"
)

_DEFAULT_FORBIDDEN = [
    (
        re.compile(
            r"\bnot\s+yet\s+(implemented|applied|evaluated|resolved|wired)\b", re.IGNORECASE
        ),
        _PROGRESS_CLAIM,
    ),
    (
        re.compile(r"\bnot\s+implemented\s+yet\b", re.IGNORECASE),
        _PROGRESS_CLAIM,
    ),
    (
        re.compile(r"\bTODO\s+markers?\s+remain\b", re.IGNORECASE),
        "progress claim — counts drift the moment code moves; belongs in a generated dashboard",
    ),
    (
        re.compile(r"^\s*Status:\s+Phase\s+[A-Z]\b", re.IGNORECASE),
        "phase-tracking prose — belongs in the roadmap/issues, not in gated docs",
    ),
]

_STATUS_LINE_RE = re.compile(r"^Status:\s+", re.IGNORECASE)
_DATE_ANCHOR_RE = re.compile(r"\(20\d{2}-\d{2}-\d{2}\)")
# The first dated Status anchor in a doc; captures the YYYY-MM-DD the accuracy
# arm compares against the doc's last-touched commit date.
_STATUS_ANCHOR_DATE_RE = re.compile(r"^Status:.*\((20\d{2}-\d{2}-\d{2})\)", re.IGNORECASE)


def run(root: Path, cfg: Config, base: str | None = None) -> int:
    forbidden = list(_DEFAULT_FORBIDDEN) + [
        (re.compile(p.pattern, re.IGNORECASE), p.hint) for p in cfg.status_forbidden_extra
    ]
    errors = 0
    gated: list[tuple[str, str]] = []  # (rel, text) for the accuracy arm below
    for path in iter_docs(root, cfg):
        text = path.read_text(encoding="utf-8", errors="replace")
        if frontmatter.read_class(text) != "gated":
            continue
        rel = path.relative_to(root).as_posix()
        gated.append((rel, text))
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _STATUS_LINE_RE.match(line) and not _DATE_ANCHOR_RE.search(line):
                output.error(
                    rel,
                    lineno,
                    "Status: prose needs a (YYYY-MM-DD) date anchor — undated status will drift",
                )
                errors += 1
            for pattern, hint in forbidden:
                if pattern.search(line):
                    output.error(rel, lineno, f"{hint}  [{line.strip()[:120]}]")
                    errors += 1
                    break

    errors += _accuracy_arm(root, cfg, base, gated)

    if errors == 0:
        output.summary("status-prose: no violations in gated docs")
    return errors


def _find_status_anchor(text: str) -> tuple[int, str] | None:
    """First dated ``Status:`` line as ``(lineno, YYYY-MM-DD)``, or ``None``.

    Only a dated anchor is returned — an undated Status line is the presence
    arm's concern, so the accuracy arm has nothing to compare and skips it.
    """
    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _STATUS_ANCHOR_DATE_RE.match(line)
        if m:
            return lineno, m.group(1)
    return None


def _diff_is_status_only(diff: str) -> bool:
    """True when every changed line in ``diff`` is a ``Status:`` line.

    A doc whose only substantive change since its anchor is the Status line
    itself must not be flagged — otherwise re-stamping the date to silence the
    check would immediately re-trip it (the re-stamp *is* a change in range).
    Returns ``False`` when the diff has no changed lines (nothing to judge) so a
    doc with no real diff is never mistaken for a Status-only edit.
    """
    saw_change = False
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@", "diff ", "index ")):
            continue
        if not line.startswith(("+", "-")):
            continue
        saw_change = True
        if _STATUS_LINE_RE.match(line[1:]):
            continue
        return False
    return saw_change


def _beyond_tolerance(anchor_date: str, last_date: str, tolerance_days: int) -> bool:
    """True when ``last_date`` is newer than ``anchor_date`` beyond the window.

    Both are ``YYYY-MM-DD``. Unparseable dates return ``False`` — the accuracy
    arm fails open rather than flagging on a value it cannot reason about.
    """
    try:
        anchor = date.fromisoformat(anchor_date)
        last = date.fromisoformat(last_date)
    except ValueError:
        return False
    return (last - anchor).days > tolerance_days


def _accuracy_arm(root: Path, cfg: Config, base: str | None, gated: list[tuple[str, str]]) -> int:
    """Flag gated docs whose Status anchor predates their last commit in range.

    Diff-scoped like doc-drift (D019): only docs in ``changed_files`` are
    checked, so the whole tree is never re-dated. When no base ref is available
    — a local run with no ``--base`` and no ``GITHUB_BASE_REF`` — the arm skips
    cleanly and returns 0; it must NEVER fail (D020), so every git error is a
    skip, not a raise (unlike doc-drift, which lets ``GitError`` surface as exit
    2). A distinct summary line records whether the arm ran or skipped so
    CI-vs-local behaviour is legible.
    """
    if not (base or os.environ.get("GITHUB_BASE_REF")):
        output.summary("status-prose: accuracy arm skipped — no base ref (local run)")
        return 0

    try:
        base_ref = gitutil.resolve_base_ref(root, base)
        changed = set(gitutil.changed_files(root, base_ref))
    except gitutil.GitError as e:
        output.summary(f"status-prose: accuracy arm skipped — base ref unresolvable ({e})")
        return 0

    errors = 0
    for rel, text in gated:
        if rel not in changed:
            continue
        anchor = _find_status_anchor(text)
        if anchor is None:
            continue
        lineno, anchor_date = anchor
        last = gitutil.last_touched_date(root, base_ref, rel)
        if last is None:
            continue
        if not _beyond_tolerance(anchor_date, last, cfg.status_date_tolerance_days):
            continue
        try:
            file_diff = gitutil.file_diff(root, base_ref, rel)
        except gitutil.GitError:
            continue
        if _diff_is_status_only(file_diff):
            continue
        output.error(
            rel,
            lineno,
            f"Status: anchor date {anchor_date} predates the doc's last commit in range "
            f"({last}) — the doc changed after its Status date; refresh the anchor or "
            f"limit the change to the Status line",
        )
        errors += 1

    output.summary(f"status-prose: accuracy arm ran vs {base_ref} — {len(changed)} changed file(s)")
    return errors
