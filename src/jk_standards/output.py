"""GitHub-Actions-format annotation emitters.

All checks report through these helpers so output is uniform: `::error` /
`::warning` lines that GitHub surfaces inline on PRs, and plain text
everywhere else.
"""

from __future__ import annotations

import sys


def error(file: str, line: int, message: str) -> None:
    print(f"::error file={file},line={line}::{message}", file=sys.stderr)


def warning(file: str, line: int, message: str) -> None:
    print(f"::warning file={file},line={line}::{message}")


def summary(message: str) -> None:
    print(message)
