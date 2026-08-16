"""Fixture-repo tests for the release-pins check.

Every test builds a real git repository in `tmp_path` and tags it, because the
check's whole subject is the relationship between what the changelog claims was
released and what tags actually exist — mocking the tag list away would test
nothing.
"""

import subprocess
from pathlib import Path

import pytest

from jk_standards.checks import release_pins
from jk_standards.config import Config, ConfigError, load_config

REPO = "OWNER/PROJ"
URL = f"https://github.com/{REPO}"


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def repo(tmp_path: Path, tags: list[str]) -> Path:
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@example.com")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / "seed.txt").write_text("seed\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "seed")
    for tag in tags:
        git(tmp_path, "tag", tag)
    return tmp_path


def cfg(**kw) -> Config:
    c = Config()
    c.release_pin_repo = REPO
    c.release_pin_repo_url = URL
    for k, v in kw.items():
        setattr(c, k, v)
    return c


def write(root: Path, rel: str, text: str) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# rule 1 — every released version is tagged
# --------------------------------------------------------------------------


def test_released_version_without_tag_flagged(tmp_path):
    # 1.2.0 on top is tagged, so it does not consume the in-flight exemption
    # and 1.1.0 below it is judged on its own merits.
    repo(tmp_path, ["v1.0.0", "v1.2.0"])
    write(
        tmp_path,
        "CHANGELOG.md",
        "# C\n\n## [1.2.0] - 2026-02-01\n\n## [1.1.0] - 2026-01-01\n\n## [1.0.0] - 2025-01-01\n",
    )
    assert release_pins.run(tmp_path, cfg()) == 1


def test_released_version_with_tag_passes(tmp_path):
    repo(tmp_path, ["v1.0.0", "v1.1.0"])
    write(tmp_path, "CHANGELOG.md", "# C\n\n## [1.1.0] - 2026-01-01\n\n## [1.0.0] - 2025-01-01\n")
    assert release_pins.run(tmp_path, cfg()) == 0


def test_unreleased_heading_never_requires_a_tag(tmp_path):
    """`[Unreleased]` exists precisely to hold work that has not shipped."""
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "CHANGELOG.md", "# C\n\n## [Unreleased]\n\n## [1.0.0] - 2025-01-01\n")
    assert release_pins.run(tmp_path, cfg()) == 0


def test_newest_release_section_may_await_its_tag(tmp_path):
    """The release in flight: a release commit dates its section before tagging.

    Requiring a tag here would fail the release pull request on a required
    check, leaving it unmergeable and the tag uncuttable — the check would
    block the process it protects.
    """
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "CHANGELOG.md", "# C\n\n## [1.1.0] - 2026-01-01\n\n## [1.0.0] - 2025-01-01\n")
    assert release_pins.run(tmp_path, cfg()) == 0


def test_skipped_tag_is_caught_once_the_next_release_lands(tmp_path):
    """The exemption costs one release of latency, not permanent blindness."""
    repo(tmp_path, ["v1.0.0"])
    write(
        tmp_path,
        "CHANGELOG.md",
        "# C\n\n## [1.2.0] - 2026-02-01\n\n## [1.1.0] - 2026-01-01\n\n## [1.0.0] - 2025-01-01\n",
    )
    assert release_pins.run(tmp_path, cfg()) == 1


def test_unreleased_heading_does_not_consume_the_in_flight_exemption(tmp_path):
    """`[Unreleased]` is not a release section, so it shields nothing below it."""
    repo(tmp_path, ["v1.0.0"])
    write(
        tmp_path,
        "CHANGELOG.md",
        "# C\n\n## [Unreleased]\n\n## [1.2.0] - 2026-02-01\n\n## [1.1.0] - 2026-01-01\n",
    )
    # 1.2.0 is the newest release section and is exempt; 1.1.0 is not.
    assert release_pins.run(tmp_path, cfg()) == 1


def test_declared_untagged_version_exempted(tmp_path):
    repo(tmp_path, ["v1.0.0", "v1.2.0"])
    write(
        tmp_path,
        "CHANGELOG.md",
        "# C\n\n## [1.2.0] - 2026-02-01\n\n## [1.1.0] - 2026-01-01\n\n## [1.0.0] - 2025-01-01\n",
    )
    assert release_pins.run(tmp_path, cfg(release_pin_untagged_versions=["1.1.0"])) == 0


def test_declaring_one_version_does_not_exempt_another(tmp_path):
    repo(tmp_path, ["v1.3.0"])
    write(
        tmp_path,
        "CHANGELOG.md",
        "# C\n\n## [1.3.0] - 2026-03-01\n\n## [1.2.0] - 2026-02-01\n\n## [1.1.0] - 2026-01-01\n",
    )
    assert release_pins.run(tmp_path, cfg(release_pin_untagged_versions=["1.1.0"])) == 1


def test_changelog_marker_above_heading_exempts(tmp_path):
    repo(tmp_path, ["v1.2.0"])
    write(
        tmp_path,
        "CHANGELOG.md",
        "# C\n\n## [1.2.0] - 2026-02-01\n\n<!-- release-pin-ok: yanked -->\n"
        "## [1.1.0] - 2026-01-01\n",
    )
    assert release_pins.run(tmp_path, cfg()) == 0


def test_missing_changelog_skips_rule_one(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    assert release_pins.run(tmp_path, cfg()) == 0


# --------------------------------------------------------------------------
# rule 2 — every pin to this repo resolves
# --------------------------------------------------------------------------


def test_uses_pin_to_missing_tag_flagged(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "README.md", f"```yaml\n    uses: {REPO}/.github/workflows/x.yml@v9.9.9\n```\n")
    assert release_pins.run(tmp_path, cfg()) == 1


def test_uses_pin_to_existing_tag_passes(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "README.md", f"```yaml\n    uses: {REPO}/.github/workflows/x.yml@v1.0.0\n```\n")
    assert release_pins.run(tmp_path, cfg()) == 0


def test_rev_under_this_repo_checked(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "README.md", f"```yaml\n- repo: {URL}\n  rev: v9.9.9\n```\n")
    assert release_pins.run(tmp_path, cfg()) == 1


def test_rev_under_a_third_party_repo_ignored(tmp_path):
    """A `rev:` names no repository itself; only the nearest `repo:` line does."""
    repo(tmp_path, ["v1.0.0"])
    write(
        tmp_path,
        ".pre-commit-config.yaml",
        "repos:\n  - repo: https://github.com/other/thing\n    rev: v9.9.9\n",
    )
    assert release_pins.run(tmp_path, cfg()) == 0


def test_rev_switches_back_to_this_repo_after_a_third_party_block(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(
        tmp_path,
        ".pre-commit-config.yaml",
        "repos:\n"
        "  - repo: https://github.com/other/thing\n    rev: v9.9.9\n"
        f"  - repo: {URL}\n    rev: v8.8.8\n",
    )
    assert release_pins.run(tmp_path, cfg()) == 1


def test_uses_naming_another_owner_ignored(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "README.md", "    uses: other/proj/.github/workflows/x.yml@v9.9.9\n")
    assert release_pins.run(tmp_path, cfg()) == 0


def test_pip_git_install_form_checked(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "README.md", f'`pip install "git+{URL}@v9.9.9"`\n')
    assert release_pins.run(tmp_path, cfg()) == 1


def test_commented_pin_in_a_workflow_header_checked(tmp_path):
    """The consume-from-a-pinned-tag examples are comments, and still guidance."""
    repo(tmp_path, ["v1.0.0"])
    write(
        tmp_path,
        ".github/workflows/w.yml",
        f"# Consume from a pinned tag:\n#   uses: {REPO}/.github/workflows/w.yml@v9.9.9\nname: W\n",
    )
    assert release_pins.run(tmp_path, cfg()) == 1


def test_sha_pin_is_not_a_release_pin(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "README.md", f"    uses: {REPO}/.github/workflows/x.yml@{'a' * 40}\n")
    assert release_pins.run(tmp_path, cfg()) == 0


def test_branch_pin_is_not_a_release_pin(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "README.md", f"    uses: {REPO}/.github/workflows/x.yml@main\n")
    assert release_pins.run(tmp_path, cfg()) == 0


def test_excluded_path_not_scanned(tmp_path):
    """Historical migration notes keep the pins those projects actually used."""
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "MIGRATION-old.md", f"```yaml\n- repo: {URL}\n  rev: v9.9.9\n```\n")
    assert release_pins.run(tmp_path, cfg(release_pin_exclude=["MIGRATION-old.md"])) == 0


def test_excluded_path_still_flagged_when_not_excluded(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "MIGRATION-old.md", f"```yaml\n- repo: {URL}\n  rev: v9.9.9\n```\n")
    assert release_pins.run(tmp_path, cfg()) == 1


def test_pin_marker_same_line_exempts(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(
        tmp_path,
        "README.md",
        f"    uses: {REPO}/.github/workflows/x.yml@v9.9.9  # release-pin-ok: historical\n",
    )
    assert release_pins.run(tmp_path, cfg()) == 0


def test_pin_marker_line_above_exempts(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(
        tmp_path,
        "README.md",
        f"    # release-pin-ok: historical\n    uses: {REPO}/.github/workflows/x.yml@v9.9.9\n",
    )
    assert release_pins.run(tmp_path, cfg()) == 0


def test_node_modules_not_scanned(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "node_modules/pkg/readme.md", f"    uses: {REPO}/x.yml@v9.9.9\n")
    assert release_pins.run(tmp_path, cfg()) == 0


# --------------------------------------------------------------------------
# skip contracts
# --------------------------------------------------------------------------


def test_unconfigured_repo_skips(tmp_path):
    repo(tmp_path, ["v1.0.0"])
    write(tmp_path, "README.md", "    uses: OWNER/PROJ/.github/workflows/x.yml@v9.9.9\n")
    assert release_pins.run(tmp_path, Config()) == 0


def test_repo_without_tags_skips(tmp_path):
    """A shallow checkout and a pre-first-release repo look identical here."""
    repo(tmp_path, [])
    write(tmp_path, "CHANGELOG.md", "# C\n\n## [1.1.0] - 2026-01-01\n")
    write(tmp_path, "README.md", f"    uses: {REPO}/x.yml@v9.9.9\n")
    assert release_pins.run(tmp_path, cfg()) == 0


def test_non_git_directory_skips(tmp_path):
    write(tmp_path, "CHANGELOG.md", "# C\n\n## [1.1.0] - 2026-01-01\n")
    assert release_pins.run(tmp_path, cfg()) == 0


# --------------------------------------------------------------------------
# config validation
# --------------------------------------------------------------------------


def test_repo_url_defaults_from_repo_slug(tmp_path):
    (tmp_path / "jk-standards.yaml").write_text(
        f"version: 1\nrelease_pins:\n  repo: {REPO}\n", encoding="utf-8"
    )
    assert load_config(tmp_path).release_pin_repo_url == URL


def test_untagged_versions_non_list_raises(tmp_path):
    (tmp_path / "jk-standards.yaml").write_text(
        "version: 1\nrelease_pins:\n  untagged_versions: 0.7.0\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_untagged_versions_non_string_entry_raises(tmp_path):
    """`[0.7]` would exempt a string no changelog heading ever produces."""
    (tmp_path / "jk-standards.yaml").write_text(
        "version: 1\nrelease_pins:\n  untagged_versions:\n    - 0.7\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        load_config(tmp_path)
