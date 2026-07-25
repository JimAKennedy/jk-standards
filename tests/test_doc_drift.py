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
