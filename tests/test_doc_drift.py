"""Git-fixture tests for the doc-drift check."""

import subprocess
from pathlib import Path

import pytest

from jk_standards import cli
from jk_standards.checks import doc_drift
from jk_standards.config import Config, ConfigError


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


# --- is_deps_only_diff on raw diff fragments (issue #43) --------------------
#
# The fixtures above rewrite a whole small file, so every hunk happens to carry
# the `"dependencies": {` opening line in its context window. Real Dependabot
# diffs on a real manifest do not: the hunk opens mid-block, which is exactly
# the case the old brace-tracking implementation rejected.

# Verbatim from poly #236 — the diff reported in issue #43.
POLY_236_DIFF = """@@ -20,11 +20,11 @@
     "@fontsource-variable/inter": "^5.3.0",
     "@fontsource-variable/jetbrains-mono": "^5.3.0",
     "@fontsource-variable/source-serif-4": "^5.3.0",
-    "astro": "^7.2.0",
+    "astro": "^7.2.2",
     "sharp": "^0.35.3"
   },
   "devDependencies": {
     "@playwright/test": "^1.62.1",
-    "node-web-audio-api": "^2.1.0"
+    "node-web-audio-api": "^2.2.0"
   }
 }
"""


def test_deps_only_accepts_mid_block_hunk(manifest_repo):
    """The regression: the block-opening line is outside the hunk window."""
    assert doc_drift.is_deps_only_diff(POLY_236_DIFF) is True


def test_deps_only_accepts_both_blocks_without_either_opening_line(manifest_repo):
    diff = """@@ -21,7 +21,7 @@
     "astro": "^7.2.0",
-    "sharp": "^0.35.3",
+    "sharp": "^0.36.0",
@@ -30,7 +30,7 @@
     "@playwright/test": "^1.62.1",
-    "vitest": "^2.0.0"
+    "vitest": "^2.1.0"
"""
    assert doc_drift.is_deps_only_diff(diff) is True


def test_deps_only_rejects_scripts_edit(manifest_repo):
    diff = """@@ -3,5 +3,5 @@
   "scripts": {
-    "build": "astro build"
+    "build": "astro check && astro build"
   },
"""
    assert doc_drift.is_deps_only_diff(diff) is False


def test_deps_only_rejects_mixed_bump_and_scripts_edit(manifest_repo):
    diff = """@@ -3,9 +3,9 @@
   "scripts": {
-    "test": "vitest run"
+    "test": "vitest run --coverage"
   },
   "dependencies": {
-    "astro": "^7.2.0",
+    "astro": "^7.2.2",
"""
    assert doc_drift.is_deps_only_diff(diff) is False


def test_deps_only_rejects_single_token_script_value(manifest_repo):
    """A `"k": "v"`-shaped scripts entry is not a dependency pin.

    `"test": "vitest"` is the blind spot a "any string-valued entry" rule would
    have had; requiring a digit-led value closes it.
    """
    diff = """@@ -3,4 +3,4 @@
   "scripts": {
-    "test": "jest"
+    "test": "vitest"
"""
    assert doc_drift.is_deps_only_diff(diff) is False


def test_deps_only_rejects_package_rename(manifest_repo):
    """Top-level string keys are entry-shaped too, and are taxonomy changes."""
    diff = """@@ -1,4 +1,4 @@
 {
-  "name": "site",
+  "name": "docs-site",
"""
    assert doc_drift.is_deps_only_diff(diff) is False


def test_deps_only_rejects_empty_diff(manifest_repo):
    assert doc_drift.is_deps_only_diff("") is False


def test_deps_only_ignores_diff_metadata_lines(manifest_repo):
    """`---`/`+++` headers start with +/- but are not changed content."""
    diff = """diff --git a/site/package.json b/site/package.json
index 1234567..89abcde 100644
--- a/site/package.json
+++ b/site/package.json
@@ -21,7 +21,7 @@
-    "astro": "^7.2.0",
+    "astro": "^7.2.2",
"""
    assert doc_drift.is_deps_only_diff(diff) is True


def test_unlisted_manifest_still_triggers_on_deps_bump(manifest_repo):
    bumped = PACKAGE_JSON_V1.replace('"astro": "^5.1.0"', '"astro": "^5.2.1"')
    (manifest_repo / "site/package.json").write_text(bumped)
    git(manifest_repo, "commit", "-am", "bump astro")
    assert doc_drift.run(manifest_repo, Config(), base="main") == 1


# --- cannot_drift registry --------------------------------------------------

_BASE_MAP = (
    "version: 1\n"
    "mappings:\n"
    "  - sources:\n"
    '      - "src/**"\n'
    '    doc: "docs/spec.md"\n'
    '    reason: "spec describes src"\n'
)


def set_map(repo: Path, cannot_drift_yaml: str) -> None:
    """Overwrite the drift map with the base mappings plus a cannot_drift block.

    Reject cases need no commit: `run()` validates the registry (reading the
    working-tree map) before any git diff, so a malformed block raises up front.
    """
    (repo / ".github/docs-drift-map.yml").write_text(_BASE_MAP + cannot_drift_yaml)


def test_cannot_drift_valid_entry_parses(repo):
    set_map(
        repo,
        "cannot_drift:\n"
        '  - doc: "docs/skills.mdx"\n'
        '    reason: "prose overview, no checkable claim tied to code"\n',
    )
    (repo / "unrelated.txt").write_text("hi\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "valid cannot_drift + unrelated change")
    # Registry parses cleanly and does not (yet) affect drift correlation.
    assert doc_drift.run(repo, Config(), base="main") == 0


def test_cannot_drift_missing_reason_rejected(repo):
    set_map(repo, 'cannot_drift:\n  - doc: "docs/skills.mdx"\n')
    with pytest.raises(ConfigError, match="missing a non-empty 'reason'"):
        doc_drift.run(repo, Config(), base="main")


def test_cannot_drift_empty_reason_rejected(repo):
    set_map(
        repo,
        'cannot_drift:\n  - doc: "docs/skills.mdx"\n    reason: "   "\n',
    )
    with pytest.raises(ConfigError, match="missing a non-empty 'reason'"):
        doc_drift.run(repo, Config(), base="main")


def test_cannot_drift_missing_doc_rejected(repo):
    set_map(repo, 'cannot_drift:\n  - reason: "prose overview"\n')
    with pytest.raises(ConfigError, match="missing a non-empty string 'doc'"):
        doc_drift.run(repo, Config(), base="main")


def test_cannot_drift_invalid_entry_cli_exit_2(repo, capsys):
    # Slice criterion: a malformed entry surfaces as `config error: ...` on
    # stderr with exit 2, not a KeyError traceback.
    set_map(repo, 'cannot_drift:\n  - doc: "docs/skills.mdx"\n')
    rc = cli.main(["doc-drift", "--root", str(repo), "--base", "main"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "config error:" in err
    assert "reason" in err
