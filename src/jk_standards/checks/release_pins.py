"""release-pins: released versions are tagged, and every pin to this repo resolves.

Adoption instructions pin by tag. That makes the tag the load-bearing artefact:
`rev: v0.2.0` in a consumer's `.pre-commit-config.yaml`, or
`uses: OWNER/REPO/.github/workflows/x.yml@v0.2.0` in their CI, works only if
`v0.2.0` actually exists. When a release ships a changelog entry but the final
`git tag && git push` is skipped, nothing notices — the tree is green, the
changelog reads correctly, and the documented instructions quietly become
dangling refs that fail at *the consumer's* CI rather than this repo's.

This check closes that loop with two rules:

  1. **Every released version is tagged.** Each `## [X.Y.Z]` heading in the
     changelog must have a matching `vX.Y.Z` tag. `[Unreleased]` is skipped —
     that is the section's whole purpose — and so is the *newest* release
     section, which is the release in flight: a release commit dates its
     section before the tag is pushed, so requiring one there would make the
     release pull request unmergeable and the tag uncuttable. That costs one
     release of detection latency and no more, because the next release pushes
     the section down to where it is judged like any other. Versions released
     before this check existed can be recorded in `untagged_versions`, which
     keeps the check a ratchet instead of an unwinnable argument with history.
     Both the declared and awaiting-tag counts are reported so neither state
     fades into silence.

  2. **Every pin to this repo resolves.** Any `uses: <repo>/…@<ref>`,
     `rev: <ref>` under a `repo:` line naming this repo, or
     `git+<repo_url>@<ref>` is checked against the tag list. Only
     release-shaped refs (`vX.Y.Z`) are judged: a SHA, a branch name, or a
     non-release tag is somebody else's rule to enforce.

Pins belonging to *other* projects are never touched — a `rev:` under a
third-party `repo:` line, or a `uses:` naming another owner, does not match.
Historical records that must keep their original pins (a migration note
describing what a project actually adopted at the time) belong in `exclude`,
since rewriting them would falsify the record.

Escape hatch: a `# release-pin-ok: <reason>` marker on the offending line or
the line immediately above it suppresses the finding.
"""

from __future__ import annotations

import re
from pathlib import Path

from jk_standards import gitutil, output
from jk_standards.config import Config

# `## [1.2.3] - 2026-01-01` — the Keep a Changelog release heading. The date is
# not matched: an unreleased-but-headed section is still a claim of release.
_HEADING_RE = re.compile(r"^##\s*\[(?P<version>\d+\.\d+\.\d+)\]")
# A release-shaped ref. Anything else (SHA, branch, `-rc` build tag) is out of
# scope rather than silently assumed wrong.
_RELEASE_REF_RE = re.compile(r"^v\d+\.\d+\.\d+$")
# Recognised after any language-appropriate comment opener, matching the
# `boundary-ok` / `import-cycle-ok` hatches. The HTML form matters most here:
# pins live in markdown, where `<!-- -->` is the only comment available.
_MARKER_RE = re.compile(r"(?:#|//|/\*|<!--|--|;)\s*release-pin-ok\b")
_REPO_LINE_RE = re.compile(r"^\s*(?:[-#]\s*)*repo:\s*(?P<url>\S+)")
_REV_LINE_RE = re.compile(r"^\s*(?:[-#]\s*)*rev:\s*(?P<ref>\S+)")

# Directories never worth scanning for adoption pins.
_SKIP_DIRS = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", ".mypy_cache"}


def _suppressed(lines: list[str], lineno: int) -> bool:
    """True when the escape-hatch marker sits on the line or the one above."""
    if lineno < 1 or lineno > len(lines):
        return False
    if _MARKER_RE.search(lines[lineno - 1]):
        return True
    return lineno >= 2 and bool(_MARKER_RE.search(lines[lineno - 2]))


def _iter_files(root: Path, cfg: Config) -> list[Path]:
    """Scannable files: configured extensions, minus skip dirs and excludes."""
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root).as_posix()
        if any(part in _SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if any(rel.startswith(prefix) for prefix in cfg.release_pin_exclude):
            continue
        if not any(rel.endswith(ext) for ext in cfg.release_pin_extensions):
            continue
        out.append(path)
    return out


def _pins_in(lines: list[str], repo: str, repo_url: str) -> list[tuple[int, str, str]]:
    """Find every pin to this repo. Returns (lineno, ref, form) triples.

    `rev:` is context-sensitive — it names no repository itself — so it counts
    only when the nearest preceding `repo:` line names this one. That is what
    keeps a third-party hook's `rev:` in the same file from being judged.
    """
    found: list[tuple[int, str, str]] = []
    current_repo: str | None = None
    # `uses: owner/repo/path@ref` and the pip `git+url@ref` install form.
    uses_re = re.compile(rf"uses:\s*{re.escape(repo)}/\S*?@(?P<ref>[\w.\-]+)")
    giturl_re = re.compile(rf"git\+{re.escape(repo_url)}(?:\.git)?@(?P<ref>[\w.\-]+)")

    for lineno, line in enumerate(lines, start=1):
        m = _REPO_LINE_RE.match(line)
        if m:
            current_repo = m.group("url").rstrip("/")
        for pattern, form in ((uses_re, "uses:"), (giturl_re, "git+ install")):
            for hit in pattern.finditer(line):
                found.append((lineno, hit.group("ref"), form))
        rev = _REV_LINE_RE.match(line)
        if rev and current_repo and current_repo.removesuffix(".git") == repo_url:
            found.append((lineno, rev.group("ref"), "rev:"))
    return found


def run(root: Path, cfg: Config) -> int:
    if not cfg.release_pin_repo:
        output.summary("release-pins: no release_pins.repo configured — skipped")
        return 0

    tags = gitutil.list_tags(root)
    if tags is None:
        output.summary("release-pins: tags unreadable (not a git checkout) — skipped")
        return 0
    if not tags:
        # Distinguishing "no releases yet" from "tags were not fetched" is not
        # possible here, and reporting every pin as dangling on a shallow
        # checkout would be worse than staying quiet.
        output.summary("release-pins: no tags present — skipped")
        return 0

    errors = 0
    declared = set(cfg.release_pin_untagged_versions)
    used_declared = 0
    pending = 0

    # Rule 1 — every released version is tagged.
    changelog = root / cfg.release_pin_changelog
    if changelog.is_file():
        lines = changelog.read_text(encoding="utf-8", errors="replace").splitlines()
        rel = changelog.relative_to(root).as_posix()
        seen_release_heading = False
        for lineno, line in enumerate(lines, start=1):
            m = _HEADING_RE.match(line)
            if not m:
                continue
            version = m.group("version")
            topmost = not seen_release_heading
            seen_release_heading = True
            if f"v{version}" in tags:
                continue
            if version in declared:
                used_declared += 1
                continue
            if topmost:
                # The release in flight. A release commit necessarily dates its
                # changelog section *before* the tag is pushed — the tag is cut
                # from the merged result — so requiring one here would make the
                # release pull request unmergeable and the tag uncuttable: the
                # check would block the process it exists to protect. Exempting
                # exactly the newest section costs one release of detection
                # latency, no more: skip the tag and the next release pushes
                # this section down, where it is judged like any other. The
                # count is reported so the pending state stays visible.
                pending += 1
                continue
            if _suppressed(lines, lineno):
                continue
            output.error(
                rel,
                lineno,
                f"changelog releases {version} but no v{version} tag exists — the "
                f"release was never tagged, so every adoption pin naming it is a "
                f"dangling ref (push the tag, record it under "
                f"release_pins.untagged_versions, or add # release-pin-ok: <reason>)",
            )
            errors += 1

    # Rule 2 — every pin to this repo resolves.
    pins = 0
    for path in _iter_files(root, cfg):
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        rel = path.relative_to(root).as_posix()
        for lineno, ref, form in _pins_in(lines, cfg.release_pin_repo, cfg.release_pin_repo_url):
            if not _RELEASE_REF_RE.match(ref):
                continue  # a SHA or branch is not a release pin
            pins += 1
            if ref in tags:
                continue
            if _suppressed(lines, lineno):
                continue
            output.error(
                rel,
                lineno,
                f"{form} pins {ref}, which is not a tag in this repository — an "
                f"adopter copying this gets a ref-resolution failure, not an old "
                f"version (or add # release-pin-ok: <reason>)",
            )
            errors += 1

    if errors == 0:
        output.summary(
            f"release-pins: {pins} pin(s) resolve, {used_declared} release(s) declared "
            f"untagged, {pending} awaiting its tag"
        )
    return errors
