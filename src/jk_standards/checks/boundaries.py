"""boundaries: architectural layering rules are grep-enforced.

An architecture document's most common — and most easily violated — invariant
is a *boundary*: a directed constraint saying one component MUST NOT reference
another (the CLI may call the check registry, but a check must not reach back
into the CLI). Prose alone doesn't hold: someone adds an `import` and the
boundary is gone with no diff on the doc side to warn anyone.

This check turns a stated boundary into a grep-level gate. Each configured
rule names a `from` directory, an optional file-`extensions` filter, and a
`forbid` regex. Every line under that directory is scanned; a line matching
the regex is a boundary violation, flagged with `file:line`. This is a
line-level textual gate, not an import graph — it catches the reference forms
you name and nothing subtler, which is enough to keep an honest boundary
honest and cheap enough to run on every commit.

Escape hatch: a `# boundary-ok: <reason>` marker on the offending line or the
line immediately above it suppresses the finding. The marker is recognized
after any language-appropriate comment opener (`#`, `//`, `/*`, `<!--`, `--`,
`;`), so a genuinely-necessary crossing can be waived in place with its reason
recorded. The summary line always reports how many suppressions are live, so
rising escape-hatch usage is visible in CI logs rather than silent.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import output
from jk_standards.config import BoundaryRule, Config

# `boundary-ok` after any common comment opener. Requiring an opener keeps the
# marker from matching a `forbid` pattern that literally contains the word.
_MARKER_RE = re.compile(r"(?:#|//|/\*|<!--|--|;)\s*boundary-ok\b")


def _scan_rule(root: Path, rule: BoundaryRule) -> tuple[int, int]:
    """Scan one rule. Returns (violations, suppressions)."""
    base = root / rule.from_dir
    if not base.is_dir():
        output.summary(f"boundaries: '{rule.from_dir}' not present — rule skipped")
        return 0, 0

    try:
        forbid = re.compile(rule.forbid)
    except re.error as e:
        # A malformed `forbid` regex is a config bug, not a boundary crossing.
        # Surface it loudly and count it as a violation so CI fails visibly.
        output.summary(
            f"boundaries: rule {rule.name or rule.from_dir!r} has an invalid "
            f"forbid pattern {rule.forbid!r} — {e}"
        )
        return 1, 0

    label = f" [{rule.name}]" if rule.name else ""
    hint = f" — {rule.hint}" if rule.hint else ""
    violations = 0
    suppressions = 0
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if rule.extensions and not any(path.name.endswith(e) for e in rule.extensions):
            continue
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if not forbid.search(line):
                continue
            if _MARKER_RE.search(line) or (lineno >= 2 and _MARKER_RE.search(lines[lineno - 2])):
                suppressions += 1
                continue
            output.error(
                rel,
                lineno,
                f"forbidden cross-boundary reference{label}{hint} (or add # boundary-ok: <reason>)",
            )
            violations += 1
    return violations, suppressions


def run(root: Path, cfg: Config) -> int:
    if not cfg.boundaries:
        output.summary("boundaries: no boundary rules configured — skipped")
        return 0

    total_violations = 0
    total_suppressions = 0
    for rule in cfg.boundaries:
        v, s = _scan_rule(root, rule)
        total_violations += v
        total_suppressions += s

    # Always emit the suppression count so rising escape-hatch usage is visible
    # in CI logs even when the run is otherwise green.
    output.summary(
        f"boundaries: {len(cfg.boundaries)} rule(s), "
        f"{total_violations} violation(s), "
        f"{total_suppressions} suppression(s) via boundary-ok"
    )
    return total_violations
