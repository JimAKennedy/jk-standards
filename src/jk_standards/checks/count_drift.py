"""count-drift: inventory facts live in one place, not restated as numerals.

Facts like "N presets" or "N chapters" drift the moment the inventory
changes. This check flags a numeral (Arabic or spelled-out) adjacent to a
configured trigger phrase, so those facts are forced into a generated
source of truth and interpolated (`{counts.x}`) instead of restated.

The trigger list is deliberately project-supplied and deliberately
conservative — inventory-scoped phrases ("factory presets", "chapters in
total"), not bare nouns, so compositional prose ("three lanes at prime
cycle lengths") never matches. No triggers configured means the check is
skipped.

Exemptions: archived docs; fenced code blocks; markdown table rows;
`counts-ok` markers (same line, immediately preceding line, or whole-file
before the first heading); `{counts.<field>}` template literals.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import frontmatter, output
from jk_standards.config import Config, iter_docs

_SPELLED = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|"
    "fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|"
    "fifty|sixty|seventy|eighty|ninety|hundred|thousand"
)
_COUNTS_TEMPLATE_RE = re.compile(r"\{\s*counts\.\w+\s*\}")
_LINE_MARKER_RE = re.compile(r"<!--\s*counts-ok|\{/\*\s*counts-ok|/\*\s*counts-ok")


def _whole_file_exempt(lines: list[str]) -> bool:
    for line in lines:
        if line.lstrip().startswith("#"):
            return False
        if _LINE_MARKER_RE.search(line):
            return True
    return False


def run(root: Path, cfg: Config) -> int:
    if not cfg.count_triggers:
        output.summary("count-drift: no triggers configured — skipped")
        return 0

    claim_re = re.compile(
        rf"\b(?P<num>\d{{1,4}}|{_SPELLED})"
        rf"(?:[-\s]+(?:[A-Za-z][A-Za-z-]*\s+){{0,3}})?"
        rf"(?P<phrase>{'|'.join(cfg.count_triggers)})",
        re.I,
    )

    errors = 0
    for path in iter_docs(root, cfg):
        text = path.read_text(encoding="utf-8", errors="replace")
        if frontmatter.read_class(text) == "archived":
            continue
        lines = text.splitlines()
        if _whole_file_exempt(lines):
            continue

        rel = path.relative_to(root).as_posix()
        in_fence = False
        prev_marker = False
        for lineno, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                prev_marker = False
                continue
            if in_fence or stripped.startswith("|"):
                prev_marker = False
                continue
            if not stripped:
                continue  # blank lines preserve a preceding marker

            this_marker = bool(_LINE_MARKER_RE.search(raw))
            if this_marker or prev_marker:
                prev_marker = this_marker
                continue
            prev_marker = False

            scrubbed = _COUNTS_TEMPLATE_RE.sub(" ", raw)
            m = claim_re.search(scrubbed)
            if m:
                snippet = stripped if len(stripped) <= 120 else stripped[:117] + "..."
                output.error(
                    rel,
                    lineno,
                    f"Hardcoded inventory count '{m.group('num')} ... {m.group('phrase')}': "
                    f"interpolate from the generated source of truth or add "
                    f"<!-- counts-ok: reason -->  [{snippet}]",
                )
                errors += 1

    if errors == 0:
        output.summary("count-drift: no hardcoded inventory counts")
    return errors
