"""file-line-refs: enduring docs and source comments cite symbols, not lines.

`foo.cpp:429`-style references rot on the next edit — by the following
commit they point at the wrong code. Docs are scanned on every line; source
files are scanned only inside comments (string literals are left alone).

Escape hatches:
  - dirs listed in exempt_dirs (dated review docs are frozen at their write
    date, so their line refs are pinned and don't rot the same way)
  - a `[file-line-ok]` marker on the line, for consciously accepted cases
    (commit-SHA-pinned permalinks and the like)
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import output
from jk_standards.config import Config, iter_docs

_MARKER = "[file-line-ok]"


def _ref_re(extensions: list[str]) -> re.Pattern:
    alternation = "|".join(re.escape(e) for e in extensions)
    return re.compile(rf"\b[A-Za-z_][A-Za-z0-9_]*\.(?:{alternation})\b:\d+(?:[-,]\d+)*")


def _comment_ranges(line: str, in_block: bool) -> tuple[str, bool]:
    """Return the comment-only portion of a source line and the new
    block-comment state. Naive (ignores comment markers inside string
    literals) but sufficient for conventional codebases."""
    scan = []
    idx = 0
    while idx < len(line):
        if in_block:
            end = line.find("*/", idx)
            if end == -1:
                scan.append(line[idx:])
                idx = len(line)
            else:
                scan.append(line[idx:end])
                idx = end + 2
                in_block = False
        else:
            start_block = line.find("/*", idx)
            start_line = line.find("//", idx)
            hash_comment = line.find("#", idx) if "#" in line[idx:] else -1
            candidates = [c for c in (start_block, start_line, hash_comment) if c != -1]
            if not candidates:
                break
            start = min(candidates)
            if start == start_block:
                in_block = True
                idx = start + 2
            else:
                scan.append(line[start:])
                idx = len(line)
    return " ".join(scan), in_block


def run(root: Path, cfg: Config) -> int:
    ref_re = _ref_re(cfg.file_line_extensions)
    errors = 0

    for path in iter_docs(root, cfg):
        rel = path.relative_to(root).as_posix()
        for lineno, line in enumerate(
            path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
        ):
            if _MARKER in line:
                continue
            m = ref_re.search(line)
            if m:
                output.error(
                    rel,
                    lineno,
                    f"file:line reference — cite a symbol/region name instead "
                    f"(or add {_MARKER} if legitimately pinned)  [{m.group(0)}]",
                )
                errors += 1

    for source_root in cfg.file_line_source_roots:
        base = root / source_root.path
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if source_root.extensions and not any(
                path.name.endswith(e) for e in source_root.extensions
            ):
                continue
            rel = path.relative_to(root).as_posix()
            in_block = False
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8", errors="replace").splitlines(), start=1
            ):
                if _MARKER in line:
                    _, in_block = _comment_ranges(line, in_block)
                    continue
                scan, in_block = _comment_ranges(line, in_block)
                if not scan:
                    continue
                m = ref_re.search(scan)
                if m:
                    output.error(
                        rel,
                        lineno,
                        f"file:line reference in comment — cite a symbol/region name "
                        f"instead (or add {_MARKER})  [{m.group(0)}]",
                    )
                    errors += 1

    if errors == 0:
        output.summary("file-line-refs: no file:line references in enduring docs or comments")
    return errors
