# Copyright 2026 Jim Kennedy
# SPDX-License-Identifier: Apache-2.0
# Adapted from nfr-review's scripts/install_skills.py (Apache-2.0); this copy
# adds --dest so consuming repos can choose their skills directory
# (.agents/skills for generic agents, .claude/skills for Claude Code) and
# folds the installer into the jk-standards CLI as `install-skills`.
"""Install vendored skills from skills-lock.json.

Downloads skill directories from their source GitHub repositories and
places them under the skills directory (default .agents/skills/). Only
installs skills listed in skills-lock.json that are not already present
locally, unless --force is given.

This is the importable, in-process-testable backend for the
`jk-standards install-skills` subcommand. Every command entrypoint returns
an int exit code (0 clean, 1 violations/failures, 2 usage/config error)
instead of calling sys.exit, so callers and tests can drive it directly.

Usage (via the CLI):
    jk-standards install-skills                          # install missing skills
    jk-standards install-skills --dest .claude/skills    # Claude Code layout
    jk-standards install-skills --force                  # reinstall all skills
    jk-standards install-skills --check                  # verify installed hashes
    jk-standards install-skills --update-lock            # pin hashes + toolkit version
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path, PurePosixPath

from jk_standards import __version__

LOCK_FILE = "skills-lock.json"
SKILLS_DIR = Path(".agents/skills")
GITHUB_ARCHIVE_URL = "https://github.com/{source}/archive/refs/heads/main.tar.gz"


class LockError(Exception):
    """Raised when skills-lock.json is missing or unreadable."""


def load_lock(project_root: Path) -> dict:
    lock_path = project_root / LOCK_FILE
    if not lock_path.exists():
        raise LockError(f"{LOCK_FILE} not found in {project_root}")
    with lock_path.open(encoding="utf-8") as f:
        return json.load(f)


def compute_hash(file_path: Path) -> str:
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def download_archive(source: str) -> tarfile.TarFile:
    url = GITHUB_ARCHIVE_URL.format(source=source)
    print(f"  Downloading {source} archive...")
    try:
        req = urllib.request.Request(url)
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            req.add_header("Authorization", f"token {token}")
        with urllib.request.urlopen(req) as resp:
            data = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            for branch in ("master", "HEAD"):
                fallback = url.replace("/main.tar.gz", f"/{branch}.tar.gz")
                try:
                    req = urllib.request.Request(fallback)
                    if token:
                        req.add_header("Authorization", f"token {token}")
                    with urllib.request.urlopen(req) as resp:
                        data = resp.read()
                    break
                except urllib.error.HTTPError:
                    continue
            else:
                print(
                    f"  Error: could not download {source} (tried main/master/HEAD)",
                    file=sys.stderr,
                )
                raise
        else:
            raise
    return tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")


def extract_skill(
    tar: tarfile.TarFile,
    skill_path_in_repo: str,
    dest: Path,
) -> int:
    """Extract a skill directory from a tarball. Returns file count."""
    prefix = None
    for member in tar.getmembers():
        if prefix is None:
            prefix = member.name.split("/")[0]
        full_prefix = f"{prefix}/{skill_path_in_repo}/"
        if member.name.startswith(full_prefix) or member.name == f"{prefix}/{skill_path_in_repo}":
            rel = member.name[len(f"{prefix}/{skill_path_in_repo}") :].lstrip("/")
            if member.isdir():
                (dest / rel).mkdir(parents=True, exist_ok=True)
            elif member.isfile():
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with tar.extractfile(member) as src:  # type: ignore[union-attr]
                    target.write_bytes(src.read())
    return sum(1 for _ in dest.rglob("*") if _.is_file()) if dest.exists() else 0


def install_skills(
    project_root: Path, *, force: bool = False, skills_dir: Path = SKILLS_DIR
) -> int:
    lock = load_lock(project_root)
    skills = lock.get("skills", {})
    if not skills:
        print("No skills in lock file.")
        return 0

    by_source: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for name, info in skills.items():
        by_source[info["source"]].append((name, info))

    installed = 0
    skipped = 0
    failed = 0

    for source, skill_list in sorted(by_source.items()):
        to_install = []
        for name, info in skill_list:
            dest = project_root / skills_dir / name
            skill_md = dest / "SKILL.md"
            if not force and skill_md.exists():
                existing_hash = compute_hash(skill_md)
                if existing_hash == info["computedHash"]:
                    print(f"  {name}: up to date (skipped)")
                    skipped += 1
                    continue
                print(f"  {name}: hash mismatch, reinstalling")
            to_install.append((name, info))

        if not to_install:
            continue

        try:
            tar = download_archive(source)
        except (urllib.error.URLError, tarfile.TarError, OSError) as e:
            print(f"  Failed to download {source}: {e}", file=sys.stderr)
            failed += len(to_install)
            continue

        for name, info in to_install:
            dest = project_root / skills_dir / name
            # PurePosixPath, not Path: this value is interpolated into tar
            # member names, which are always "/"-separated. Path().parent
            # would emit backslashes on Windows and never match a member.
            skill_dir_in_repo = str(PurePosixPath(info["skillPath"]).parent)

            if dest.exists():
                shutil.rmtree(dest)

            dest.mkdir(parents=True, exist_ok=True)
            count = extract_skill(tar, skill_dir_in_repo, dest)

            skill_md = dest / "SKILL.md"
            if not skill_md.exists():
                print(f"  {name}: SKILL.md not found after extraction (FAILED)", file=sys.stderr)
                failed += 1
                continue

            actual_hash = compute_hash(skill_md)
            if actual_hash != info["computedHash"]:
                print(
                    f"  {name}: hash verification failed "
                    f"(expected {info['computedHash'][:12]}..., "
                    f"got {actual_hash[:12]}...)",
                    file=sys.stderr,
                )
                print(f"  {name}: installed anyway ({count} files) — source may have updated")
            else:
                print(f"  {name}: installed ({count} files, hash verified)")
            installed += 1

        tar.close()

    print(f"\nDone: {installed} installed, {skipped} up-to-date, {failed} failed")
    return 1 if failed else 0


def check_skills(project_root: Path, skills_dir: Path = SKILLS_DIR) -> int:
    lock = load_lock(project_root)
    skills = lock.get("skills", {})
    ok = 0
    mismatch = 0
    missing = 0

    for name, info in sorted(skills.items()):
        skill_md = project_root / skills_dir / name / "SKILL.md"
        if not skill_md.exists():
            print(f"  {name}: MISSING")
            missing += 1
        else:
            actual = compute_hash(skill_md)
            if actual == info["computedHash"]:
                print(f"  {name}: OK")
                ok += 1
            else:
                expected = info["computedHash"][:12]
                print(f"  {name}: HASH MISMATCH (expected {expected}..., got {actual[:12]}...)")
                mismatch += 1

    print(f"\n{ok} ok, {mismatch} mismatch, {missing} missing")
    if missing or mismatch:
        print("Run 'jk-standards install-skills' to fix.")
        return 1
    return 0


def update_lock(project_root: Path, skills_dir: Path = SKILLS_DIR) -> int:
    """Update lock hashes to match installed skills and pin the toolkit version.

    Records the producing jk-standards version in the top-level
    ``jkStandardsVersion`` field so consumers can tell which toolkit version
    generated their skills-lock.json. The file is rewritten whenever a hash
    changes or the version pin is missing/stale.
    """
    lock = load_lock(project_root)
    skills = lock.get("skills", {})
    updated = 0

    for name, info in sorted(skills.items()):
        skill_md = project_root / skills_dir / name / "SKILL.md"
        if not skill_md.exists():
            print(f"  {name}: not installed, skipping")
            continue
        actual = compute_hash(skill_md)
        if actual != info["computedHash"]:
            info["computedHash"] = actual
            print(f"  {name}: hash updated")
            updated += 1
        else:
            print(f"  {name}: unchanged")

    version_changed = lock.get("jkStandardsVersion") != __version__
    if version_changed:
        lock["jkStandardsVersion"] = __version__
        print(f"  jkStandardsVersion pinned to {__version__}")

    if updated or version_changed:
        lock_path = project_root / LOCK_FILE
        with lock_path.open("w", encoding="utf-8") as f:
            json.dump(lock, f, indent=2)
            f.write("\n")
        print(f"\nUpdated {updated} hashes in {LOCK_FILE} (jkStandardsVersion={__version__})")
    else:
        print("\nAll hashes already current")
    return 0


def find_project_root() -> Path:
    """Walk up from cwd to find the directory containing skills-lock.json."""
    cwd = Path.cwd()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / LOCK_FILE).exists():
            return candidate
    return cwd


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jk-standards install-skills",
        description="Install third-party skills from skills-lock.json",
    )
    parser.add_argument(
        "--force", action="store_true", help="Reinstall all skills even if up to date"
    )
    parser.add_argument(
        "--check", action="store_true", help="Verify installed skills match lock file hashes"
    )
    parser.add_argument(
        "--update-lock",
        action="store_true",
        help="Update lock hashes to match installed skills and pin jkStandardsVersion",
    )
    parser.add_argument(
        "--root", type=Path, default=None, help="Project root (default: auto-detect)"
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=SKILLS_DIR,
        help="Skills directory relative to project root (default: .agents/skills)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the install-skills subcommand. Returns an exit code."""
    args = _build_parser().parse_args(argv)

    project_root = args.root or find_project_root()

    print(f"Skills lock: {project_root / LOCK_FILE}")
    print(f"Skills dir:  {project_root / args.dest}\n")

    try:
        if args.check:
            return check_skills(project_root, skills_dir=args.dest)
        if args.update_lock:
            return update_lock(project_root, skills_dir=args.dest)
        return install_skills(project_root, force=args.force, skills_dir=args.dest)
    except LockError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
