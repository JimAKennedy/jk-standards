"""In-process tests for jk_standards.cli.main across every dispatch branch."""

from pathlib import Path

import pytest

from jk_standards.checks import CHECKS, STATIC_CHECKS
from jk_standards.cli import main
from jk_standards.gitutil import GitError


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- list + single-check dispatch (T01) -------------------------------------


def test_list_prints_check_names(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for name in CHECKS:
        assert name in out


def test_single_check_success(tmp_path):
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\n# Doc\n")
    assert main(["doc-taxonomy", "--root", str(tmp_path)]) == 0


def test_single_check_violations_exit_1(tmp_path, capsys):
    write(tmp_path, "docs/a.md", "# No front matter\n")
    assert main(["doc-taxonomy", "--root", str(tmp_path)]) == 1
    assert "violation(s) found" in capsys.readouterr().err


# --- error exit codes (T02) -------------------------------------------------


def test_config_error_exit_2(tmp_path, capsys):
    # Top-level must be a mapping; a YAML list triggers ConfigError deterministically.
    write(tmp_path, "jk-standards.yaml", "- one\n- two\n")
    assert main(["doc-taxonomy", "--root", str(tmp_path)]) == 2
    assert "config error:" in capsys.readouterr().err


def test_git_error_exit_2(tmp_path, capsys, monkeypatch):
    def raise_git(*args, **kwargs):
        raise GitError("no base ref")

    monkeypatch.setitem(CHECKS, "doc-drift", raise_git)
    assert main(["doc-drift", "--root", str(tmp_path), "--base", "nonexistent"]) == 2
    assert "git error:" in capsys.readouterr().err


# --- `all` dispatch + doc-drift env/flag (T03) ------------------------------


@pytest.fixture
def spy_checks(monkeypatch):
    """Replace every CHECKS entry with a spy; return the call log."""
    calls: list[tuple[str, tuple, dict]] = []

    def make_spy(name: str):
        def spy(root, cfg, **kwargs):
            calls.append((name, (root, cfg), kwargs))
            return 0

        return spy

    for name in CHECKS:
        monkeypatch.setitem(CHECKS, name, make_spy(name))
    return calls


def test_all_invokes_every_static_check(tmp_path, capsys, monkeypatch, spy_checks):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    assert main(["all", "--root", str(tmp_path)]) == 0
    names_called = [c[0] for c in spy_checks]
    for name in STATIC_CHECKS:
        assert names_called.count(name) == 1
    assert "doc-drift" not in names_called
    assert "doc-drift: no --base or GITHUB_BASE_REF" in capsys.readouterr().out


def test_all_runs_doc_drift_with_base_flag(tmp_path, monkeypatch, spy_checks):
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    assert main(["all", "--root", str(tmp_path), "--base", "main"]) == 0
    doc_drift_calls = [c for c in spy_checks if c[0] == "doc-drift"]
    assert len(doc_drift_calls) == 1
    assert doc_drift_calls[0][2] == {"base": "main"}


def test_all_runs_doc_drift_with_env_var(tmp_path, monkeypatch, spy_checks):
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    assert main(["all", "--root", str(tmp_path)]) == 0
    doc_drift_calls = [c for c in spy_checks if c[0] == "doc-drift"]
    assert len(doc_drift_calls) == 1
    # env-var branch passes args.base which is None
    assert doc_drift_calls[0][2] == {"base": None}


# --- emit dispatch ---------------------------------------------------------


def test_emit_verb_after_root_flag(tmp_path, capsys):
    """`jk-standards --root DIR emit checks` must find `emit` past the flag."""
    from jk_standards import emit as emit_mod

    fixture_dir = tmp_path / "site" / "src" / "generated"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "checks.json").write_bytes(emit_mod.emit_checks(tmp_path))
    # Would previously fail with argparse error: `--root: expected one argument`.
    assert main(["--root", str(tmp_path), "emit", "checks", "--check"]) == 0


def test_emit_verb_with_root_after_verb(tmp_path):
    """`jk-standards emit checks --root DIR` still works (existing shape)."""
    from jk_standards import emit as emit_mod

    fixture_dir = tmp_path / "site" / "src" / "generated"
    fixture_dir.mkdir(parents=True)
    (fixture_dir / "checks.json").write_bytes(emit_mod.emit_checks(tmp_path))
    assert main(["emit", "checks", "--root", str(tmp_path), "--check"]) == 0
