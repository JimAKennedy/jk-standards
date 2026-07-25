"""Minimal YAML front-matter reader.

Only the fields the checks need are extracted; full YAML parsing of
front-matter bodies is deliberately avoided so a malformed doc fails the
taxonomy check rather than crashing the run.
"""

from __future__ import annotations


def read_class(text: str) -> str | None:
    """Return the `class:` value from the first front-matter block, or None."""
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    for raw in text[3:end].splitlines():
        stripped = raw.strip()
        if stripped.startswith("class:"):
            value = stripped[len("class:") :].strip()
            return value.strip("\"'") or None
    return None
