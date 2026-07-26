"""jk-standards CLI.

  jk-standards <check-name> [--root DIR] [--config FILE] [--base REF]
  jk-standards all           run every configured static check; doc-drift
                             too when a git base ref is available
  jk-standards list          list available checks

Exit codes: 0 clean, 1 violations found, 2 usage/config error.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from jk_standards import __version__, emit
from jk_standards.checks import CHECKS, STATIC_CHECKS
from jk_standards.config import ConfigError, load_config
from jk_standards.gitutil import GitError


def _emit_main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="jk-standards emit")
    parser.add_argument("name", choices=[*emit.EMITTERS, "all"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--check", action="store_true", help="fail on drift instead of writing")
    args = parser.parse_args(argv)
    return emit.run(args.root.resolve(), args.name, args.check)


def main(argv: list[str] | None = None) -> int:
    raw = sys.argv[1:] if argv is None else argv
    if raw and raw[0] == "emit":
        return _emit_main(raw[1:])

    parser = argparse.ArgumentParser(prog="jk-standards", description=__doc__)
    parser.add_argument("check", choices=[*CHECKS, "all", "list"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--base", default=None, help="git base ref for doc-drift")
    parser.add_argument("--version", action="version", version=__version__)
    # pre-commit passes matched filenames; the checks scan configured roots
    # themselves, so filenames are accepted and ignored.
    parser.add_argument("files", nargs="*", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)

    if args.check == "list":
        for name in CHECKS:
            print(name)
        return 0

    root = args.root.resolve()
    try:
        cfg = load_config(root, args.config)
    except ConfigError as e:
        print(f"config error: {e}", file=sys.stderr)
        return 2

    try:
        if args.check == "all":
            errors = sum(CHECKS[name](root, cfg) for name in STATIC_CHECKS)
            if args.base or os.environ.get("GITHUB_BASE_REF"):
                errors += CHECKS["doc-drift"](root, cfg, base=args.base)
            else:
                print("doc-drift: no --base or GITHUB_BASE_REF — skipped")
        elif args.check == "doc-drift":
            errors = CHECKS["doc-drift"](root, cfg, base=args.base)
        else:
            errors = CHECKS[args.check](root, cfg)
    except GitError as e:
        print(f"git error: {e}", file=sys.stderr)
        return 2

    if errors:
        print(f"\n{errors} violation(s) found.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
