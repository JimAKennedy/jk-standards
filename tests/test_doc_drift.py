"""Git-fixture tests for the doc-drift check."""

import subprocess
from pathlib import Path

import pytest

from jk_standards.checks import doc_drift
from jk_standards.config import Config


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test")

    (tmp_path / "src").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / ".github").mkdir()
    (tmp_path / "src/engine.py").write_text("x = 1\n")
    (tmp_path / "docs/spec.md").write_text("---\nclass: gated\n---\n# Spec\n")
    (tmp_path / ".github/docs-drift-map.yml").write_text(
        "version: 1\n"
        "mappings:\n"
        "  - sources:\n"
        '      - "src/**"\n'
        '    doc: "docs/spec.md"\n'
        '    reason: "spec describes src"\n'
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "feature")
    return tmp_path


def test_source_change_without_doc_flagged(repo):
    (repo / "src/engine.py").write_text("x = 2\n")
    git(repo, "commit", "-am", "change engine")
    assert doc_drift.run(repo, Config(), base="main") == 1


def test_source_change_with_doc_passes(repo):
    (repo / "src/engine.py").write_text("x = 2\n")
    (repo / "docs/spec.md").write_text("---\nclass: gated\n---\n# Spec v2\n")
    git(repo, "commit", "-am", "change engine + doc")
    assert doc_drift.run(repo, Config(), base="main") == 0


def test_trailer_bypasses(repo):
    (repo / "src/engine.py").write_text("x = 2\n")
    git(repo, "commit", "-am", "refactor\n\nDocs-Not-Affected: rename only, no contract change")
    assert doc_drift.run(repo, Config(), base="main") == 0


def test_unmapped_change_passes(repo):
    (repo / "unrelated.txt").write_text("hi\n")
    git(repo, "add", "unrelated.txt")
    git(repo, "commit", "-m", "unrelated")
    assert doc_drift.run(repo, Config(), base="main") == 0


# --- deps-only manifests ----------------------------------------------------

PACKAGE_JSON_V1 = """{
  "name": "site",
  "scripts": {
    "test": "vitest run"
  },
  "dependencies": {
    "astro": "^5.1.0",
    "left-pad": "^1.3.0"
  },
  "devDependencies": {
    "vitest": "^2.0.0"
  }
}
"""


@pytest.fixture
def manifest_repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "site").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / ".github").mkdir()
    (tmp_path / "site/package.json").write_text(PACKAGE_JSON_V1)
    (tmp_path / "docs/testing.md").write_text("---\nclass: gated\n---\n# Testing\n")
    (tmp_path / ".github/docs-drift-map.yml").write_text(
        "version: 1\n"
        "mappings:\n"
        "  - sources:\n"
        '      - "site/package.json"\n'
        '    doc: "docs/testing.md"\n'
        '    reason: "new test entry-points reshape the taxonomy"\n'
    )
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-m", "base")
    git(tmp_path, "checkout", "-b", "feature")
    return tmp_path


def deps_only_config() -> Config:
    return Config(deps_only_manifests=["site/package.json"])


def test_deps_only_bump_does_not_trigger(manifest_repo):
    bumped = PACKAGE_JSON_V1.replace('"astro": "^5.1.0"', '"astro": "^5.2.1"')
    (manifest_repo / "site/package.json").write_text(bumped)
    git(manifest_repo, "commit", "-am", "bump astro")
    assert doc_drift.run(manifest_repo, deps_only_config(), base="main") == 0


def test_scripts_block_change_still_triggers(manifest_repo):
    changed = PACKAGE_JSON_V1.replace(
        '"test": "vitest run"', '"test": "vitest run",\n    "test:e2e": "playwright test"'
    )
    (manifest_repo / "site/package.json").write_text(changed)
    git(manifest_repo, "commit", "-am", "add e2e entry point")
    assert doc_drift.run(manifest_repo, deps_only_config(), base="main") == 1


def test_unlisted_manifest_still_triggers_on_deps_bump(manifest_repo):
    bumped = PACKAGE_JSON_V1.replace('"astro": "^5.1.0"', '"astro": "^5.2.1"')
    (manifest_repo / "site/package.json").write_text(bumped)
    git(manifest_repo, "commit", "-am", "bump astro")
    assert doc_drift.run(manifest_repo, Config(), base="main") == 1
