"""In-process tests for jk_standards.cli.main across every dispatch branch."""

import json
from pathlib import Path

import pytest

from jk_standards.checks import CHECKS, STATIC_CHECKS
from jk_standards.cli import main
from jk_standards.gitutil import GitError

_REPO_ROOT = Path(__file__).resolve().parents[1]


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


# --- import-cycle: registration, CLI exit codes, skip, escape hatch, exit-2 (S02) --
#
# The detector core is proven in tests/test_import_cycle.py; these tests prove the
# CLI wiring — registry membership (so `jk-standards import-cycle` and
# `jk-standards all` come free), the exit-code contract through main(), the
# skip-when-unconfigured path, the escape-hatch suppression + live count, and the
# out-of-shape config → exit 2 mapping — plus that the live repo self-hosts green.


def _cycle_repo(root: Path, *, marker: bool = False, configured: bool = True) -> None:
    """A repo with a synthetic 2-module import cycle in package ``pkg``.

    ``configured`` writes the ``import_cycle.packages: [pkg]`` config that selects
    the package (omit it to exercise skip-when-unconfigured). ``marker`` places an
    inline ``# import-cycle-ok:`` waiver on one of the two in-cycle imports.
    """
    if configured:
        write(root, "jk-standards.yaml", "import_cycle:\n  packages:\n    - pkg\n")
    write(root, "pkg/__init__.py", "")
    a = "from pkg import b  # import-cycle-ok: intentional\n" if marker else "from pkg import b\n"
    write(root, "pkg/a.py", a)
    write(root, "pkg/b.py", "from pkg import a\n")


def test_import_cycle_registered_in_checks_and_static_checks():
    """Membership is what auto-exposes `jk-standards import-cycle` and `all`."""
    assert "import-cycle" in CHECKS
    assert "import-cycle" in STATIC_CHECKS


def test_import_cycle_skips_and_exits_zero_when_unconfigured(tmp_path, capsys):
    """No `import_cycle` config → skip summary, exit 0 (mirrors boundaries)."""
    _cycle_repo(tmp_path, configured=False)  # cycle present but not selected
    assert main(["import-cycle", "--root", str(tmp_path)]) == 0
    assert "no packages configured" in capsys.readouterr().out


def test_import_cycle_reports_unsuppressed_cycle_exit_1(tmp_path, capsys):
    """A configured, unwaived cycle exits 1 and names both members."""
    _cycle_repo(tmp_path)
    assert main(["import-cycle", "--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "pkg.a" in captured.err and "pkg.b" in captured.err
    assert "violation(s) found" in captured.err


def test_import_cycle_escape_hatch_suppresses_and_counts(tmp_path, capsys):
    """An `# import-cycle-ok:` marker suppresses the finding and bumps the count."""
    _cycle_repo(tmp_path, marker=True)
    assert main(["import-cycle", "--root", str(tmp_path)]) == 0
    captured = capsys.readouterr()
    assert "::error" not in captured.err
    assert "1 suppression(s) via import-cycle-ok" in captured.out


def test_import_cycle_out_of_shape_config_exits_2(tmp_path, capsys):
    """An out-of-shape `import_cycle` value is a ConfigError → exit 2, not 1."""
    write(tmp_path, "jk-standards.yaml", "import_cycle: 5\n")
    assert main(["import-cycle", "--root", str(tmp_path)]) == 2
    assert "config error:" in capsys.readouterr().err


def test_import_cycle_non_string_package_entry_exits_2(tmp_path, capsys):
    """A non-string `packages` entry is out of shape → exit 2."""
    write(tmp_path, "jk-standards.yaml", "import_cycle:\n  packages:\n    - 5\n")
    assert main(["import-cycle", "--root", str(tmp_path)]) == 2
    assert "config error:" in capsys.readouterr().err


def test_all_includes_import_cycle(tmp_path, monkeypatch, spy_checks):
    """`jk-standards all` runs import-cycle exactly once (it is a static check)."""
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    assert main(["all", "--root", str(tmp_path)]) == 0
    assert [c[0] for c in spy_checks].count("import-cycle") == 1


def test_import_cycle_self_host_is_green(capsys):
    """The live repo self-hosts green: its real self-cycle is waived in place."""
    assert main(["import-cycle", "--root", str(_REPO_ROOT)]) == 0
    assert "0 cycle(s)" in capsys.readouterr().out
