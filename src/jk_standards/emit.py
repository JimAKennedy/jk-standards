"""Emitters that project the toolkit's own source of truth as JSON fixtures.

Every fixture is:

  * byte-idempotent — two runs on the same source produce identical bytes;
  * consumed by `site/` MDX pages via `import`;
  * gated by `generated-freshness` (see `jk-standards.yaml`) so a source
    change that isn't followed by a regeneration fails CI.

Adding a new fixture: write an `emit_<name>()` returning `bytes`, register it
in `EMITTERS`, add it to `jk-standards.yaml` `generated:`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Callable
from dataclasses import MISSING, fields
from pathlib import Path

import yaml

from jk_standards import __version__
from jk_standards.checks import CHECKS, STATIC_CHECKS, doc_coverage
from jk_standards.config import DEFAULT_CONFIG_NAME, Config, load_config

GENERATED_DIR = Path("site/src/generated")

# Emitters that are non-deterministic across environments (Python version,
# platform branches). `emit --check` treats them as pass-through when the
# committed fixture exists so CI doesn't flap on numeric noise.
NON_DETERMINISTIC = frozenset({"coverage"})


def _serialize(payload: object) -> bytes:
    """Stable JSON serialization: sorted keys, 2-space indent, trailing newline."""
    return (
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False, default=str) + "\n"
    ).encode("utf-8")


def _module_summary(module) -> str:
    doc = (module.__doc__ or "").strip()
    if not doc:
        return ""
    return doc.split("\n\n", 1)[0].replace("\n", " ").strip()


def _rel_to_root(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def emit_checks(root: Path) -> bytes:
    # source_file is derived from the module's dotted name, not __file__,
    # so it stays stable across install locations (editable-install repo vs
    # pip-installed-from-git into a tempdir — the reusable-workflow context).
    entries = []
    for name, fn in CHECKS.items():
        module = sys.modules[fn.__module__]
        source_file = fn.__module__.replace(".", "/") + ".py"
        entries.append(
            {
                "name": name,
                "is_static": name in STATIC_CHECKS,
                "summary": _module_summary(module),
                "source_file": f"src/{source_file}",
            }
        )
    entries.sort(key=lambda e: e["name"])
    return _serialize({"toolkit_version": __version__, "checks": entries})


# Match a fence line that closes YAML frontmatter: `---` or `...` alone on the
# line (optional trailing whitespace). Anchored so mid-line `---` in block
# scalars doesn't false-match.
_FRONTMATTER_CLOSE_RE = re.compile(r"^(?:---|\.\.\.)\s*$", re.MULTILINE)


def _read_skill_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    # Skip past the opening fence, then find the next line that is exactly
    # `---` or `...`. text.find("\n---", 3) would match a mid-line `---` inside
    # a block scalar (common in markdown-with-YAML skill files).
    body_start = text.find("\n", 3)
    if body_start == -1:
        return {}
    match = _FRONTMATTER_CLOSE_RE.search(text, body_start + 1)
    if match is None:
        return {}
    data = yaml.safe_load(text[body_start + 1 : match.start()])
    return data if isinstance(data, dict) else {}


def emit_skills(root: Path) -> bytes:
    entries = []
    for skill_md in sorted((root / "skills").glob("*/SKILL.md")):
        fm = _read_skill_frontmatter(skill_md)
        entries.append(
            {
                "name": fm.get("name", skill_md.parent.name),
                "description": fm.get("description", ""),
                "path": _rel_to_root(skill_md, root),
            }
        )
    entries.sort(key=lambda e: e["name"])
    return _serialize({"toolkit_version": __version__, "skills": entries})


def _default_repr(value: object, _seen: set[int] | None = None) -> object:
    """JSON-safe rendering of a dataclass default value. Cycle-safe."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    _seen = set() if _seen is None else _seen
    ident = id(value)
    if ident in _seen:
        return "<cycle>"
    _seen.add(ident)
    if isinstance(value, (list, tuple)):
        return [_default_repr(v, _seen) for v in value]
    if isinstance(value, dict):
        return {str(k): _default_repr(v, _seen) for k, v in value.items()}
    # Only inspect __dict__ on things that look like plain data objects, not
    # modules, functions, methods, or types (all of which have __dict__).
    if hasattr(value, "__dict__") and not callable(value) and not isinstance(value, type):
        return {k: _default_repr(v, _seen) for k, v in vars(value).items()}
    return repr(value)


def emit_config_schema(root: Path) -> bytes:
    del root  # Config is fully described in-process; source root not needed.
    entries = []
    for f in fields(Config):
        # dataclasses uses the MISSING sentinel (not None) when a default is
        # absent; the public API is `is not MISSING` via the field object.
        has_factory = f.default_factory is not MISSING
        if has_factory:
            default = _default_repr(f.default_factory())
        else:
            default = _default_repr(f.default) if f.default is not MISSING else None
        entries.append(
            {
                "name": f.name,
                "type": str(f.type),
                "default": default,
                "has_default_factory": has_factory,
            }
        )
    entries.sort(key=lambda e: e["name"])
    return _serialize(
        {
            "toolkit_version": __version__,
            "config_file_name": DEFAULT_CONFIG_NAME,
            "fields": entries,
        }
    )


class CoverageToolingMissing(Exception):
    """Raised when the `coverage` CLI isn't installed (downstream consumer)."""


def _coverage_run_and_read(root: Path) -> dict:
    """Produce `.coverage` if missing, then read `coverage json -o -`.

    Raises CoverageToolingMissing if the coverage CLI isn't on PATH.
    Propagates CalledProcessError from real test failures (they are NOT the
    same as tooling being absent, and must not be silently swallowed).
    """
    coverage_file = root / ".coverage"
    if not coverage_file.exists():
        try:
            subprocess.run(
                ["coverage", "run", "-m", "pytest", "tests/"],
                cwd=root,
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as e:
            raise CoverageToolingMissing("coverage CLI not on PATH") from e
    try:
        result = subprocess.run(
            ["coverage", "json", "-o", "-"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError as e:
        raise CoverageToolingMissing("coverage CLI not on PATH") from e
    return json.loads(result.stdout)


def _coverage_payload(raw: dict) -> dict:
    totals = raw.get("totals") or {}
    files_raw = raw.get("files") or {}
    files = {
        name: {
            "percent_covered": round(
                float((data.get("summary") or {}).get("percent_covered", 0.0)), 2
            ),
            "missing_lines": (data.get("summary") or {}).get("missing_lines", 0),
        }
        for name, data in sorted(files_raw.items())
    }
    return {
        "toolkit_version": __version__,
        "totals": {
            "percent_covered": round(float(totals.get("percent_covered", 0.0)), 2),
            "num_statements": totals.get("num_statements", 0),
            "missing_lines": totals.get("missing_lines", 0),
            "covered_lines": totals.get("covered_lines", 0),
        },
        "files": files,
    }


def emit_coverage(root: Path) -> bytes:
    """Emit the coverage fixture. Falls back to the committed file only when
    the coverage CLI is genuinely absent (downstream consumer) or when we're
    already inside a pytest run and can't recurse. Real test failures
    propagate — this is not a "silent green" surface.
    """
    fallback_path = root / GENERATED_DIR / "coverage.json"

    # Inside pytest: never recurse. If .coverage already exists (parent
    # `coverage run` produced it) we can still emit fresh numbers via
    # `coverage json`; otherwise we must fall back so the test suite doesn't
    # invoke itself.
    in_pytest = "PYTEST_CURRENT_TEST" in os.environ
    if in_pytest and not (root / ".coverage").exists():
        if fallback_path.is_file():
            return fallback_path.read_bytes()
        # Test suite calling emit_coverage in a fresh checkout with no
        # fixture: nothing we can do, and there's no honest number to invent.
        raise RuntimeError(
            "emit_coverage: called from inside pytest with no .coverage and no "
            "committed fixture — cannot compute coverage without recursing"
        )

    try:
        raw = _coverage_run_and_read(root)
    except CoverageToolingMissing:
        # Downstream consumer (reusable-workflow smoke, end-user CI) — no dev
        # tooling installed. Read back the committed fixture unchanged so
        # generated-freshness reports "fresh" instead of crashing.
        if fallback_path.is_file():
            return fallback_path.read_bytes()
        raise

    return _serialize(_coverage_payload(raw))


def emit_doc_coverage(root: Path) -> bytes:
    """Project the S01 doc-coverage walk as a symbol-level worklist.

    Reuses the ``doc_coverage.enumerate_units`` seam (no re-walk / re-parse):
    each DocUnit becomes a row carrying all three OR-signals, so a
    ``documented: false`` row is a concrete file+symbol remediation target.
    Rows are sorted by (file, name, lineno) for byte-stable output, and no
    timestamp / absolute path / env-sensitive value is emitted — the fixture is
    deterministic and thus diff-gated by generated-freshness (unlike coverage).
    """
    cfg = load_config(root)
    units = doc_coverage.enumerate_units(root, cfg)
    rows = [
        {
            "file": u.file,
            "kind": u.kind,
            "name": u.name,
            "lineno": u.lineno,
            "documented": u.documented,
            "signals": {
                "docstring": u.has_docstring,
                "drift": u.drift_match,
                "mention": u.mention,
            },
        }
        for u in units
    ]
    rows.sort(key=lambda r: (r["file"], r["name"], r["lineno"]))
    return _serialize({"toolkit_version": __version__, "units": rows})


EMITTERS: dict[str, tuple[Callable[[Path], bytes], str]] = {
    "checks": (emit_checks, "checks.json"),
    "config-schema": (emit_config_schema, "config-schema.json"),
    "skills": (emit_skills, "skills.json"),
    "coverage": (emit_coverage, "coverage.json"),
    "doc-coverage": (emit_doc_coverage, "doc-coverage.json"),
}


def run(root: Path, name: str, check_only: bool) -> int:
    """Emit (or diff-check) one fixture. Returns 0 on success, 1 on drift."""
    if name == "all":
        return max((run(root, n, check_only) for n in EMITTERS), default=0)
    if name not in EMITTERS:
        print(f"unknown emitter: {name}", file=sys.stderr)
        return 2
    fn, filename = EMITTERS[name]
    out_path = root / GENERATED_DIR / filename

    # `--check` for non-deterministic emitters (coverage): don't shell out or
    # recompute. Presence of the committed fixture is the whole gate. This
    # keeps `emit --check` cheap and read-only for CI and pre-commit hooks.
    if check_only and name in NON_DETERMINISTIC:
        if not out_path.exists():
            print(
                f"emit --check: {out_path} missing — run `jk-standards emit {name}`",
                file=sys.stderr,
            )
            return 1
        return 0

    fresh = fn(root)
    if check_only:
        if not out_path.exists():
            print(
                f"emit --check: {out_path} missing — run `jk-standards emit {name}`",
                file=sys.stderr,
            )
            return 1
        existing = out_path.read_bytes()
        if existing != fresh:
            print(
                f"emit --check: {out_path} is stale — run `jk-standards emit {name}` and commit",
                file=sys.stderr,
            )
            return 1
        return 0
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(fresh)
    print(f"wrote {_rel_to_root(out_path, root)}")
    return 0
