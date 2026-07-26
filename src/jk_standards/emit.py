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
import subprocess
import sys
from collections.abc import Callable
from dataclasses import MISSING, fields
from pathlib import Path

import yaml

from jk_standards import __version__
from jk_standards.checks import CHECKS, STATIC_CHECKS
from jk_standards.config import DEFAULT_CONFIG_NAME, Config

GENERATED_DIR = Path("site/src/generated")


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
    entries = []
    for name, fn in CHECKS.items():
        module = sys.modules[fn.__module__]
        entries.append(
            {
                "name": name,
                "is_static": name in STATIC_CHECKS,
                "summary": _module_summary(module),
                "source_file": _rel_to_root(Path(module.__file__), root),
            }
        )
    entries.sort(key=lambda e: e["name"])
    return _serialize({"toolkit_version": __version__, "checks": entries})


def _read_skill_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    return yaml.safe_load(text[3:end]) or {}


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


def _default_repr(value: object) -> object:
    """JSON-safe rendering of a dataclass default value."""
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple)):
        return [_default_repr(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _default_repr(v) for k, v in value.items()}
    if hasattr(value, "__dict__"):
        return {k: _default_repr(v) for k, v in vars(value).items()}
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


def emit_coverage(root: Path) -> bytes:
    coverage_file = root / ".coverage"
    if not coverage_file.exists():
        subprocess.run(
            ["coverage", "run", "-m", "pytest", "tests/"],
            cwd=root,
            check=True,
            capture_output=True,
        )
    result = subprocess.run(
        ["coverage", "json", "-o", "-"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    raw = json.loads(result.stdout)
    totals = raw.get("totals", {})
    percent = round(float(totals.get("percent_covered", 0.0)), 2)
    files = {
        name: {
            "percent_covered": round(float(data.get("summary", {}).get("percent_covered", 0.0)), 2),
            "missing_lines": data.get("summary", {}).get("missing_lines", 0),
        }
        for name, data in sorted(raw.get("files", {}).items())
    }
    payload = {
        "toolkit_version": __version__,
        "totals": {
            "percent_covered": percent,
            "num_statements": totals.get("num_statements", 0),
            "missing_lines": totals.get("missing_lines", 0),
            "covered_lines": totals.get("covered_lines", 0),
        },
        "files": files,
    }
    return _serialize(payload)


EMITTERS: dict[str, tuple[Callable[[Path], bytes], str]] = {
    "checks": (emit_checks, "checks.json"),
    "config-schema": (emit_config_schema, "config-schema.json"),
    "skills": (emit_skills, "skills.json"),
    "coverage": (emit_coverage, "coverage.json"),
}


def run(root: Path, name: str, check_only: bool) -> int:
    """Emit (or diff-check) one fixture. Returns 0 on success, 1 on drift."""
    if name == "all":
        return max(run(root, n, check_only) for n in EMITTERS)
    if name not in EMITTERS:
        print(f"unknown emitter: {name}", file=sys.stderr)
        return 2
    fn, filename = EMITTERS[name]
    out_path = root / GENERATED_DIR / filename
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
