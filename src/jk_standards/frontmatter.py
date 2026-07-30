"""Minimal YAML front-matter reader.

Only the fields the checks need are extracted; full YAML parsing of
front-matter bodies is deliberately avoided so a malformed doc fails the
taxonomy check rather than crashing the run.
"""

from __future__ import annotations


def read_field(text: str, name: str) -> str | None:
    """Return a top-level scalar field from the first front-matter block, or None."""
    key = f"{name}:"
    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    if end == -1:
        return None
    for raw in text[3:end].splitlines():
        stripped = raw.strip()
        if stripped.startswith(key):
            value = stripped[len(key) :].strip()
            return value.strip("\"'") or None
    return None


def read_class(text: str) -> str | None:
    """Return the `class:` value from the first front-matter block, or None."""
    return read_field(text, "class")
