"""behavioral-claims: prose claims cite tests that actually exist.

Opt-in by design: authors mark claims where machine-verified truth matters.

  [verified: Suite.TestName]   — must resolve against the scraped test index
                                  (gtest, js, pytest sources; see testindex)
  [⚠ unverified]               — allowed, but counted and surfaced as a
                                  warning: the honest-state metric

An unresolved citation is an error: fix the citation, add the test, or
downgrade the marker to [⚠ unverified]. Deliberately no verb-based
auto-detection — prose that *sounds* behavioral usually isn't a checkable
implementation claim.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import output, testindex
from jk_standards.config import Config, iter_docs

_VERIFIED_RE = re.compile(r"\[verified:\s*([^\]]+?)\s*\]")
_UNVERIFIED_RE = re.compile(r"\[⚠\s*unverified\]")


def run(root: Path, cfg: Config) -> int:
    if not cfg.claim_sources:
        output.summary("behavioral-claims: no test-index sources configured — skipped")
        return 0

    index = testindex.build_index(root, cfg.claim_sources)
    errors = 0
    unverified = 0

    for path in iter_docs(root, cfg):
        rel = path.relative_to(root).as_posix()
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            for m in _VERIFIED_RE.finditer(line):
                citation = m.group(1)
                if citation not in index:
                    output.error(
                        rel,
                        lineno,
                        f"unresolved test citation: [verified: {citation}] — fix the "
                        f"citation, add the test, or replace with [⚠ unverified]",
                    )
                    errors += 1
            unverified += len(_UNVERIFIED_RE.findall(line))
            for _ in _UNVERIFIED_RE.finditer(line):
                output.warning(rel, lineno, "unverified behavioral claim")

    if errors == 0:
        output.summary(
            f"behavioral-claims: {len(index)} test(s) indexed, {unverified} unverified marker(s)"
        )
    return errors
