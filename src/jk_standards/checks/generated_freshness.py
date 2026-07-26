"""generated-freshness: generated docs must diff clean against their generator.

For each configured (doc, command) pair: snapshot the tracked content, run
the generator, diff, then restore the snapshot so the check is idempotent
and never leaves the working tree modified. A drifted doc means someone
edited the source of truth without committing the regenerated output — the
fix is to run the command and commit.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from jk_standards import output
from jk_standards.config import Config


def run(root: Path, cfg: Config) -> int:
    if not cfg.generated:
        output.summary("generated-freshness: no generated docs configured — skipped")
        return 0

    errors = 0
    for entry in cfg.generated:
        doc_path = root / entry.doc
        if not doc_path.is_file():
            output.error(entry.doc, 1, f"generated doc missing — run: {entry.command}")
            errors += 1
            continue

        tracked = doc_path.read_bytes()
        result = subprocess.run(
            entry.command, shell=True, cwd=root, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            output.error(
                entry.doc,
                1,
                f"generator failed ({entry.command}): {result.stderr.strip()[:200]}",
            )
            doc_path.write_bytes(tracked)
            errors += 1
            continue

        regenerated = doc_path.read_bytes()
        doc_path.write_bytes(tracked)
        if regenerated != tracked:
            output.error(
                entry.doc,
                1,
                f"generated content drifted — run '{entry.command}' and commit the result",
            )
            errors += 1

    if errors == 0:
        output.summary(f"generated-freshness: {len(cfg.generated)} generated doc(s) fresh")
    return errors
