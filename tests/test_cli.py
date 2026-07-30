"""In-process tests for jk_standards.cli.main across every dispatch branch."""

import json
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


# --- doc-coverage --update-baseline / --allow-regression dispatch (T03) ------


def _doc_coverage_repo(root: Path) -> Path:
    """Config + one fully-documented module so the writer records a real floor."""
    write(
        root,
        "jk-standards.yaml",
        'doc_coverage:\n  source_roots:\n    - path: src\n      extensions: [".py"]\n',
    )
    write(root, "src/mod.py", '"""Module doc."""\n')
    return root / "baselines" / "doc-coverage.json"


def test_update_baseline_writes_via_writer(tmp_path):
    """`--update-baseline` routes to the writer and records the floor map."""
    baseline = _doc_coverage_repo(tmp_path)
    assert not baseline.exists()
    assert main(["doc-coverage", "--update-baseline", "--root", str(tmp_path)]) == 0
    data = json.loads(baseline.read_text(encoding="utf-8"))
    assert data == {"modules": {"src/mod.py": {"documented": 1, "total": 1}}}


def test_plain_doc_coverage_run_never_writes_baseline(tmp_path):
    """A plain check run must never mutate the floor map — read-only path."""
    baseline = _doc_coverage_repo(tmp_path)
    assert main(["doc-coverage", "--root", str(tmp_path)]) == 0
    assert not baseline.exists()


def test_update_baseline_rejects_non_doc_coverage(tmp_path, capsys):
    """`--update-baseline` is a doc-coverage-only action, else a usage error."""
    write(tmp_path, "docs/a.md", "---\nclass: gated\n---\n# Doc\n")
    assert main(["doc-taxonomy", "--update-baseline", "--root", str(tmp_path)]) == 2
    assert "only valid for doc-coverage" in capsys.readouterr().err


def test_allow_regression_requires_update_baseline(tmp_path, capsys):
    """`--allow-regression` alone is a no-op flag — reject it as a usage error."""
    _doc_coverage_repo(tmp_path)
    assert main(["doc-coverage", "--allow-regression", "--root", str(tmp_path)]) == 2
    assert "requires --update-baseline" in capsys.readouterr().err


def test_update_baseline_refuses_lower_without_allow_regression(tmp_path, capsys):
    """Ratchet-up default: lowering a floor is refused (non-zero, file intact)."""
    baseline = _doc_coverage_repo(tmp_path)
    assert main(["doc-coverage", "--update-baseline", "--root", str(tmp_path)]) == 0
    before = baseline.read_text(encoding="utf-8")
    # Drop the docstring so the live fraction falls below the recorded floor.
    write(tmp_path, "src/mod.py", "x = 1\n")
    assert main(["doc-coverage", "--update-baseline", "--root", str(tmp_path)]) == 1
    assert "--allow-regression" in capsys.readouterr().err
    assert baseline.read_text(encoding="utf-8") == before  # untouched


def test_update_baseline_allow_regression_lowers_floor(tmp_path):
    """`--allow-regression` threads through and records the lower floor."""
    baseline = _doc_coverage_repo(tmp_path)
    assert main(["doc-coverage", "--update-baseline", "--root", str(tmp_path)]) == 0
    write(tmp_path, "src/mod.py", "x = 1\n")
    assert (
        main(
            [
                "doc-coverage",
                "--update-baseline",
                "--allow-regression",
                "--root",
                str(tmp_path),
            ]
        )
        == 0
    )
    data = json.loads(baseline.read_text(encoding="utf-8"))
    assert data == {"modules": {"src/mod.py": {"documented": 0, "total": 1}}}


# --- doc_coverage.module_min_percent advisory end-to-end (T02) ---------------


def test_module_min_percent_out_of_range_is_config_error_exit_2(tmp_path, capsys):
    """An out-of-range floor is a config error (exit 2), not a traceback."""
    write(
        tmp_path,
        "jk-standards.yaml",
        "doc_coverage:\n"
        "  source_roots:\n"
        '    - path: src\n      extensions: [".py"]\n'
        "  module_min_percent: 101\n",
    )
    write(tmp_path, "src/mod.py", '"""Module doc."""\n')
    assert main(["doc-coverage", "--root", str(tmp_path)]) == 2
    assert "config error" in capsys.readouterr().err


def test_module_min_percent_below_floor_module_still_exits_0(tmp_path, capsys):
    """A below-floor module warns but the advisory alone yields exit 0."""
    write(
        tmp_path,
        "jk-standards.yaml",
        "doc_coverage:\n"
        "  source_roots:\n"
        '    - path: src\n      extensions: [".py"]\n'
        "  module_min_percent: 80\n",
    )
    # module docstring + one bare fn → 1/2 = 50%, below the 80% floor.
    write(tmp_path, "src/mod.py", '"""Doc."""\n\n\ndef f():\n    pass\n')
    assert main(["doc-coverage", "--root", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "::warning file=src/mod.py,line=1::" in out
    assert "advisory: 1 module(s) below 80% floor" in out
