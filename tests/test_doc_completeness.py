"""Unit tests for the doc-completeness check.

Unlike doc-drift, this check has no git *base-ref* dependency — the working
tree and the drift map are its only inputs. So most tests build docs + a map
under ``tmp_path`` directly, with no git fixtures. The integration tests at the
bottom are the exception: they build a real repo to prove the git-aware
``iter_docs`` seam flows through — a gitignored, unregistered doc no longer
trips completeness, while a tracked one still does. Each test drives the
pass/fail semantics in isolation from jk-standards' own doc set.
"""

import subprocess
from pathlib import Path

import pytest

from jk_standards import cli
from jk_standards.checks import doc_completeness
from jk_standards.config import Config, ConfigError, DocRoot


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_map(root: Path, body: str) -> Path:
    return write(root, ".github/docs-drift-map.yml", body)


DOC = "---\nclass: gated\n---\n# Doc\n"
ARCHIVED = "---\nclass: archived\n---\n# Doc\n"


# --- mapped / declared docs pass -------------------------------------------


def test_mapped_only_passes(tmp_path):
    write(tmp_path, "docs/spec.md", DOC)
    write_map(
        tmp_path,
        "version: 1\n"
        "mappings:\n"
        "  - sources:\n"
        '      - "src/**"\n'
        '    doc: "docs/spec.md"\n'
        '    reason: "spec describes src"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 0


def test_cannot_drift_only_passes(tmp_path):
    write(tmp_path, "docs/skills.md", DOC)
    write_map(
        tmp_path,
        "version: 1\n"
        "cannot_drift:\n"
        '  - doc: "docs/skills.md"\n'
        '    reason: "prose overview, no checkable claim tied to code"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 0


def test_success_emits_summary(tmp_path, capsys):
    write(tmp_path, "docs/spec.md", DOC)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/spec.md"\n    reason: "declared un-driftable"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 0
    out = capsys.readouterr().out
    assert "doc-completeness: all 1 doc(s) mapped or declared" in out


# --- unregistered docs fail -------------------------------------------------


def test_unregistered_doc_fails_naming_it(tmp_path, capsys):
    write(tmp_path, "docs/spec.md", DOC)
    write(tmp_path, "docs/orphan.md", DOC)
    write_map(
        tmp_path,
        "version: 1\n"
        "mappings:\n"
        "  - sources:\n"
        '      - "src/**"\n'
        '    doc: "docs/spec.md"\n'
        '    reason: "spec describes src"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/orphan.md" in err
    # Actionable remediation, and it does NOT name the accounted-for doc.
    assert "mappings entry" in err
    assert "cannot_drift entry" in err
    assert "docs/spec.md" not in err


def test_empty_map_with_doc_present_fails(tmp_path):
    write(tmp_path, "docs/spec.md", DOC)
    write_map(tmp_path, "version: 1\n")
    assert doc_completeness.run(tmp_path, Config()) == 1


def test_every_unregistered_doc_is_named(tmp_path, capsys):
    write(tmp_path, "docs/a.md", DOC)
    write(tmp_path, "docs/b.md", DOC)
    write_map(tmp_path, "version: 1\n")
    assert doc_completeness.run(tmp_path, Config()) == 2
    err = capsys.readouterr().err
    assert "::error file=docs/a.md" in err
    assert "::error file=docs/b.md" in err


# --- class-exempt docs skip the mapped/declared check -----------------------


def test_unmapped_archived_doc_passes(tmp_path):
    # An archived doc that is neither mapped nor declared still passes: the
    # default exempt_classes=["archived"] skips it before the membership test.
    write(tmp_path, "docs/spec.md", DOC)
    write(tmp_path, "docs/old.md", ARCHIVED)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/spec.md"\n    reason: "prose"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 0


def test_unmapped_gated_doc_still_fails_alongside_archived(tmp_path, capsys):
    # The exemption keys off class, not registration: a gated orphan still fails
    # even when an archived orphan in the same tree is silently exempted.
    write(tmp_path, "docs/spec.md", DOC)
    write(tmp_path, "docs/old.md", ARCHIVED)
    write(tmp_path, "docs/orphan.md", DOC)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/spec.md"\n    reason: "prose"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/orphan.md" in err
    assert "docs/old.md" not in err


def test_custom_exempt_classes_exempts_named_class(tmp_path):
    # A custom exempt_classes value exempts the class it names (and only that
    # one): a draft doc is exempt, an archived doc is no longer exempt.
    write(tmp_path, "docs/draft.md", "---\nclass: draft\n---\n# Doc\n")
    write(tmp_path, "docs/old.md", ARCHIVED)
    write_map(tmp_path, "version: 1\n")
    cfg = Config(doc_completeness_exempt_classes=["draft"])
    # draft.md is exempt; old.md (archived) is now governed and unregistered.
    assert doc_completeness.run(tmp_path, cfg) == 1


def test_summary_notes_exempt_count(tmp_path, capsys):
    write(tmp_path, "docs/spec.md", DOC)
    write(tmp_path, "docs/old.md", ARCHIVED)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/spec.md"\n    reason: "prose"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 0
    out = capsys.readouterr().out
    assert "doc-completeness: all 1 doc(s) mapped or declared" in out
    assert "(1 exempt by class)" in out


# --- doc_roots / extensions / exempt_dirs -----------------------------------


def test_multiple_doc_roots_and_extensions(tmp_path):
    write(tmp_path, "docs/guide.md", DOC)
    write(tmp_path, "site/page.mdx", DOC)
    write(tmp_path, "site/ignored.txt", "not a doc\n")
    write_map(
        tmp_path,
        "version: 1\n"
        "cannot_drift:\n"
        '  - doc: "docs/guide.md"\n'
        '    reason: "prose"\n'
        '  - doc: "site/page.mdx"\n'
        '    reason: "prose"\n',
    )
    cfg = Config(
        doc_roots=[
            DocRoot("docs", [".md"]),
            DocRoot("site", [".mdx"]),
        ]
    )
    # .txt is outside the configured extensions, so it is never enumerated and
    # need not be registered.
    assert doc_completeness.run(tmp_path, cfg) == 0


def test_exempt_dirs_excluded(tmp_path):
    write(tmp_path, "docs/keep.md", DOC)
    write(tmp_path, "docs/vendor/skip.md", DOC)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/keep.md"\n    reason: "prose"\n',
    )
    cfg = Config(exempt_dirs=["docs/vendor"])
    # docs/vendor/skip.md is exempt, so its absence from the map is not a
    # completeness failure.
    assert doc_completeness.run(tmp_path, cfg) == 0


# --- config-error surfaces (exit 2 via CLI) ---------------------------------


def test_missing_drift_map_fails(tmp_path, capsys):
    write(tmp_path, "docs/spec.md", DOC)
    assert doc_completeness.run(tmp_path, Config()) == 1
    err = capsys.readouterr().err
    assert "drift map not found" in err


def test_malformed_cannot_drift_raises_config_error(tmp_path):
    write(tmp_path, "docs/spec.md", DOC)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/spec.md"\n',
    )
    with pytest.raises(ConfigError, match="missing a non-empty 'reason'"):
        doc_completeness.run(tmp_path, Config())


def test_malformed_cannot_drift_cli_exit_2(tmp_path, capsys):
    write(tmp_path, "docs/spec.md", DOC)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/spec.md"\n',
    )
    rc = cli.main(["doc-completeness", "--root", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "config error:" in err
    assert "reason" in err


def test_mapping_missing_doc_key_cli_exit_2(tmp_path, capsys):
    write(tmp_path, "docs/spec.md", DOC)
    write_map(
        tmp_path,
        'version: 1\nmappings:\n  - sources:\n      - "src/**"\n    reason: "no doc key"\n',
    )
    rc = cli.main(["doc-completeness", "--root", str(tmp_path)])
    assert rc == 2
    err = capsys.readouterr().err
    assert "config error:" in err
    assert "doc" in err


# --- reverse orphan-existence pass ------------------------------------------


def test_cannot_drift_orphan_is_reported(tmp_path, capsys):
    # A cannot_drift entry naming a path that no longer exists is an orphan:
    # the reverse pass names it, its registry, and the silent-pre-exemption
    # failure mode. No enumerated doc is needed — existence is a filesystem fact.
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/ghost.md"\n    reason: "was prose, now deleted"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/ghost.md" in err
    assert "cannot_drift entry 'docs/ghost.md'" in err
    assert "pre-exempts any future doc created at that path" in err


def test_mappings_orphan_is_reported_with_unsatisfiable_gate_framing(tmp_path, capsys):
    # A mappings entry naming a nonexistent path is an orphan with the distinct
    # unsatisfiable-gate framing, naming the Docs-Not-Affected escape hatch.
    write_map(
        tmp_path,
        "version: 1\n"
        "mappings:\n"
        "  - sources:\n"
        '      - "src/**"\n'
        '    doc: "docs/ghost.md"\n'
        '    reason: "spec that was removed"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/ghost.md" in err
    assert "mappings entry 'docs/ghost.md'" in err
    assert "unsatisfiable gate" in err
    assert "Docs-Not-Affected" in err


def test_all_entries_existing_reports_zero_orphans_and_names_checked_count(tmp_path, capsys):
    # When every registry entry names a live path, the reverse pass finds no
    # orphans and the success summary reports how many entries were
    # existence-checked, proving the pass ran even on a green run.
    write(tmp_path, "docs/spec.md", DOC)
    write(tmp_path, "docs/guide.md", DOC)
    write_map(
        tmp_path,
        "version: 1\n"
        "cannot_drift:\n"
        '  - doc: "docs/spec.md"\n'
        '    reason: "prose"\n'
        '  - doc: "docs/guide.md"\n'
        '    reason: "prose"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 0
    out = capsys.readouterr().out
    assert "2 registry entries existence-checked" in out


def test_entry_naming_file_outside_doc_roots_is_tolerated(tmp_path, capsys):
    # An entry may legitimately name a doc outside the enumerated doc_roots
    # (e.g. a top-level README). The reverse pass tests plain filesystem
    # existence, NOT iter_docs membership, so a live out-of-root path is no
    # orphan and the run passes.
    write(tmp_path, "README.md", DOC)  # exists at root, outside docs/ doc_root
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "README.md"\n    reason: "top-level readme"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 0
    captured = capsys.readouterr()
    assert "README.md" not in captured.err
    assert "1 registry entry existence-checked" in captured.out


def test_orphan_reported_when_git_tracking_fails_open(tmp_path, capsys, monkeypatch):
    # The reverse pass is a filesystem fact, independent of the #50 git
    # fail-open branch inside iter_docs. Force tracked_paths to return None and
    # the cannot_drift orphan is still reported.
    monkeypatch.setattr("jk_standards.gitutil.tracked_paths", lambda root: None)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/ghost.md"\n    reason: "deleted prose"\n',
    )
    assert doc_completeness.run(tmp_path, Config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/ghost.md" in err
    assert "cannot_drift entry 'docs/ghost.md'" in err


# --- integration: the git-aware iter_docs seam flows through ----------------


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def _init_repo(root: Path) -> None:
    _git(root, "init", "-q", "-b", "main")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    _git(root, "config", "commit.gpgsign", "false")


def test_gitignored_unmapped_doc_does_not_fail_completeness(tmp_path):
    # Integration closure: the corrected iter_docs is the shared seam, so a
    # gitignored, unregistered doc under a doc_root no longer trips
    # doc-completeness — the exact local-vs-CI divergence this slice fixes.
    # docs/spec.md is tracked and declared; docs/local-notes.md is gitignored
    # and absent from the map, yet run() still exits 0 because it is never
    # enumerated.
    _init_repo(tmp_path)
    write(tmp_path, "docs/spec.md", DOC)
    write(tmp_path, "docs/local-notes.md", DOC)
    write(tmp_path, ".gitignore", "docs/local-notes.md\n")
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/spec.md"\n    reason: "prose overview"\n',
    )
    _git(tmp_path, "add", "docs/spec.md", ".gitignore", ".github/docs-drift-map.yml")
    _git(tmp_path, "commit", "-q", "-m", "base")

    assert doc_completeness.run(tmp_path, Config()) == 0


def test_tracked_unmapped_doc_still_fails_in_repo(tmp_path, capsys):
    # The seam must not over-exclude: a tracked, unregistered doc is still a
    # completeness failure inside a real repo. Guards against the tracked-status
    # filter silently swallowing genuinely governed docs.
    _init_repo(tmp_path)
    write(tmp_path, "docs/spec.md", DOC)
    write(tmp_path, "docs/orphan.md", DOC)
    write_map(
        tmp_path,
        'version: 1\ncannot_drift:\n  - doc: "docs/spec.md"\n    reason: "prose"\n',
    )
    _git(tmp_path, "add", "docs/spec.md", "docs/orphan.md")
    _git(tmp_path, "commit", "-q", "-m", "base")

    assert doc_completeness.run(tmp_path, Config()) == 1
    err = capsys.readouterr().err
    assert "::error file=docs/orphan.md" in err
