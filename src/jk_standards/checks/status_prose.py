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

import re
from pathlib import Path

from jk_standards import frontmatter, output
from jk_standards.config import Config, iter_docs

_DEFAULT_FORBIDDEN = [
    (
        re.compile(
            r"\bnot\s+yet\s+(implemented|applied|evaluated|resolved|wired)\b", re.IGNORECASE
        ),
        "progress claim — describe the current contract or delete; state belongs in CHANGELOG/issues",
    ),
    (
        re.compile(r"\bnot\s+implemented\s+yet\b", re.IGNORECASE),
        "progress claim — describe the current contract or delete; state belongs in CHANGELOG/issues",
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


def run(root: Path, cfg: Config) -> int:
    forbidden = list(_DEFAULT_FORBIDDEN) + [
        (re.compile(p.pattern, re.IGNORECASE), p.hint) for p in cfg.status_forbidden_extra
    ]
    errors = 0
    for path in iter_docs(root, cfg):
        text = path.read_text(encoding="utf-8", errors="replace")
        if frontmatter.read_class(text) != "gated":
            continue
        rel = path.relative_to(root).as_posix()
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

    if errors == 0:
        output.summary("status-prose: no violations in gated docs")
    return errors
