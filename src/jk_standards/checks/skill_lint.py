"""skill-lint: every skill directory is internally consistent.

A skill is a `skills/<name>/SKILL.md` instruction file, optionally with
bundled assets beside it. Nothing else validates the pieces an agent runtime
actually depends on: the front-matter that names and triggers the skill, and
the assets its body tells the reader to run. Each rule here is a way a skill
silently stops working with no test failing:

  - front-matter missing or unparseable, or its `name` differing from the
    directory name — the generated inventory and the installer key on both;
  - `description` lacking the "Use when" trigger phrasing every skill in
    this repo uses to make an agent select it;
  - a backtick-referenced same-directory script (`foo.sh` / `foo.py`, no
    path separator) that does not exist — a dangling asset;
  - a sibling `*.sh` without the owner-executable bit. `*.py` files are
    exempt: skill bodies invoke them as `python <file>`.

Scope: `skills/*/SKILL.md`. A repo without a `skills/` directory (every
downstream consumer) is skipped, not failed.

Escape hatch: a `skill-lint-ok: <reason>` marker on the offending line or
the line immediately above it suppresses the finding.
"""

from __future__ import annotations

import re
import stat
from pathlib import Path

import yaml

from jk_standards import output
from jk_standards.config import Config

_REF_RE = re.compile(r"`([A-Za-z0-9_.-]+\.(?:sh|py))`")
_MARKER_RE = re.compile(r"skill-lint-ok\b")
_TRIGGER = "Use when"


def _suppressed(lines: list[str], lineno: int) -> bool:
    """True when the 1-based line, or the line above it, carries the marker."""
    if lineno <= len(lines) and _MARKER_RE.search(lines[lineno - 1]):
        return True
    return lineno >= 2 and bool(_MARKER_RE.search(lines[lineno - 2]))


def _parse_frontmatter(lines: list[str]) -> tuple[dict | None, int]:
    """Parse a leading `---` block. Returns (mapping, first body line index)."""
    if not lines or lines[0].strip() != "---":
        return None, 0
    for j in range(1, len(lines)):
        if lines[j].strip() == "---":
            try:
                data = yaml.safe_load("\n".join(lines[1:j]))
            except yaml.YAMLError:
                return None, j + 1
            return (data, j + 1) if isinstance(data, dict) else (None, j + 1)
    return None, 0


def _key_line(lines: list[str], key: str, end: int) -> int:
    """1-based line of `key:` within the front-matter block, else 1."""
    for i, line in enumerate(lines[:end], start=1):
        if line.startswith(f"{key}:"):
            return i
    return 1


def run(root: Path, cfg: Config) -> int:
    base = root / "skills"
    if not base.is_dir():
        output.summary("skill-lint: no skills directory — skipped")
        return 0

    errors = 0
    skills = 0
    for skill_md in sorted(base.glob("*/SKILL.md")):
        skills += 1
        rel = skill_md.relative_to(root).as_posix()
        lines = skill_md.read_text(encoding="utf-8", errors="replace").splitlines()
        fm, body_start = _parse_frontmatter(lines)

        if fm is None:
            if not _suppressed(lines, 1):
                output.error(
                    rel,
                    1,
                    "missing or unparseable front-matter — a skill needs `name` and "
                    "`description` keys (or add skill-lint-ok: <reason>)",
                )
                errors += 1
        else:
            dirname = skill_md.parent.name
            name = fm.get("name")
            name_line = _key_line(lines, "name", body_start)
            if name != dirname and not _suppressed(lines, name_line):
                output.error(
                    rel,
                    name_line,
                    f"front-matter name '{name}' does not match directory '{dirname}' — "
                    f"the inventory and installer key on both (or add skill-lint-ok: <reason>)",
                )
                errors += 1
            desc_line = _key_line(lines, "description", body_start)
            if _TRIGGER not in str(fm.get("description") or "") and not _suppressed(
                lines, desc_line
            ):
                output.error(
                    rel,
                    desc_line,
                    "description lacks 'Use when' trigger phrasing, so an agent has no "
                    "cue to select this skill (or add skill-lint-ok: <reason>)",
                )
                errors += 1

        # First reference line per asset name; body only, so front-matter
        # prose can name files without asserting they ship here.
        referenced: dict[str, int] = {}
        for i, line in enumerate(lines[body_start:], start=body_start + 1):
            for m in _REF_RE.finditer(line):
                referenced.setdefault(m.group(1), i)

        for fname, lineno in sorted(referenced.items()):
            if (skill_md.parent / fname).is_file() or _suppressed(lines, lineno):
                continue
            output.error(
                rel,
                lineno,
                f"references `{fname}`, which does not exist in the skill directory — "
                f"a dangling asset (or add skill-lint-ok: <reason>)",
            )
            errors += 1

        for script in sorted(skill_md.parent.glob("*.sh")):
            if script.stat().st_mode & stat.S_IXUSR:
                continue
            anchor = referenced.get(script.name)
            if anchor is not None and _suppressed(lines, anchor):
                continue
            output.error(
                script.relative_to(root).as_posix(),
                1,
                "script lacks the owner-executable bit its skill tells the reader "
                "to run (or add skill-lint-ok: <reason> where it is referenced)",
            )
            errors += 1

    if errors == 0:
        output.summary(f"skill-lint: {skills} skill(s) conform")
    return errors
