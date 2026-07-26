"""Test-index scrapers for the behavioral-claims check.

Each scraper walks a configured path and returns the set of citation keys a
`[verified: <key>]` marker may resolve to:

  gtest   — `Suite.Name` from TEST(Suite, Name) / TEST_F(Suite, Name) in *.cpp
  js      — `filestem/slug` from test('name') in *.spec.ts, *.test.mjs, *.test.js
  pytest  — `filestem::test_name` from `def test_...` in test_*.py / *_test.py
"""

from __future__ import annotations

import re
from pathlib import Path

_GTEST_RE = re.compile(
    r"\bTEST(?:_F)?\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*,\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
)
_JS_TEST_RE = re.compile(r"\btest\s*\(\s*['\"`]([^'\"`]+)['\"`]")
_PYTEST_RE = re.compile(r"^\s*def\s+(test_\w+)\s*\(", re.MULTILINE)

_JS_SUFFIXES = (".spec.ts", ".test.mjs", ".test.js")


def _slug(name: str) -> str:
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", name.lower()))


def _stem(path: Path) -> str:
    name = path.name
    for suffix in (*_JS_SUFFIXES, ".py", ".cpp"):
        if name.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


def scrape_gtest(base: Path) -> set[str]:
    index: set[str] = set()
    for path in base.rglob("*.cpp"):
        for m in _GTEST_RE.finditer(path.read_text(encoding="utf-8", errors="replace")):
            index.add(f"{m.group(1)}.{m.group(2)}")
    return index


def scrape_js(base: Path) -> set[str]:
    index: set[str] = set()
    for path in base.rglob("*"):
        if not path.is_file() or not path.name.endswith(_JS_SUFFIXES):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _JS_TEST_RE.finditer(text):
            index.add(f"{_stem(path)}/{_slug(m.group(1))}")
    return index


def scrape_pytest(base: Path) -> set[str]:
    index: set[str] = set()
    for path in base.rglob("*.py"):
        if not (path.name.startswith("test_") or path.name.endswith("_test.py")):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for m in _PYTEST_RE.finditer(text):
            index.add(f"{_stem(path)}::{m.group(1)}")
    return index


_SCRAPERS = {"gtest": scrape_gtest, "js": scrape_js, "pytest": scrape_pytest}


def build_index(root: Path, sources: list) -> set[str]:
    index: set[str] = set()
    for source in sources:
        scraper = _SCRAPERS.get(source.type)
        if scraper is None:
            raise ValueError(f"unknown test-index source type: {source.type!r}")
        base = root / source.path
        if base.is_dir():
            index |= scraper(base)
    return index
