"""action-pinning: every GitHub Actions `uses:` is pinned to a commit SHA.

Floating refs (`actions/checkout@v5`, `@main`) let an upstream owner — or
anyone who compromises their account — change what runs in your CI without a
diff on your side. Pinning to a full 40-char commit SHA freezes the code; a
Dependabot bump then surfaces every update as a reviewable PR.

Scope: `.github/workflows/**/*.yml` and `*.yaml` (configurable). Each
`uses:` value is examined:
  - `owner/repo@<40-hex-sha>` (optionally `/subdir`) — accepted.
  - local `uses: ./…` or `../…` action / reusable-workflow refs — accepted;
    they live in your own tree and move with it.
  - anything else (`@v6`, `@main`, a bare tag, an unpinned `docker://` image)
    — flagged with `file:line`.

Escape hatch: a `# action-pin-ok: <reason>` marker on the offending line or
the line immediately above it suppresses the finding, for the rare ref that
genuinely cannot be SHA-pinned.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import output
from jk_standards.config import Config

_USES_RE = re.compile(r"^\s*(?:-\s*)?uses:\s*(?P<ref>\S+)")
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_MARKER_RE = re.compile(r"#\s*action-pin-ok\b")


def _is_pinned(ref: str) -> bool:
    """True when the `uses:` value is acceptably pinned (SHA or local ref)."""
    ref = ref.strip().strip("'\"")
    if ref.startswith(("./", "../")):
        return True  # local action / reusable workflow — moves with your tree
    if "@" not in ref:
        return False  # bare tag, docker image, or malformed — not pinned
    _, _, rev = ref.rpartition("@")
    return bool(_SHA_RE.match(rev))


def run(root: Path, cfg: Config) -> int:
    base = root / cfg.action_pin_workflow_dir
    if not base.is_dir():
        output.summary(
            f"action-pinning: no workflows dir ({cfg.action_pin_workflow_dir}) — skipped"
        )
        return 0

    errors = 0
    for path in sorted(base.rglob("*")):
        if not path.is_file() or not any(
            path.name.endswith(ext) for ext in cfg.action_pin_extensions
        ):
            continue
        rel = path.relative_to(root).as_posix()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for lineno, line in enumerate(lines, start=1):
            m = _USES_RE.match(line)
            if not m:
                continue
            if _is_pinned(m.group("ref")):
                continue
            if _MARKER_RE.search(line) or (lineno >= 2 and _MARKER_RE.search(lines[lineno - 2])):
                continue
            output.error(
                rel,
                lineno,
                f"unpinned action reference — pin to a 40-char commit SHA "
                f"(or add # action-pin-ok: <reason>)  [{m.group('ref')}]",
            )
            errors += 1

    if errors == 0:
        output.summary("action-pinning: all action references are SHA-pinned")
    return errors
