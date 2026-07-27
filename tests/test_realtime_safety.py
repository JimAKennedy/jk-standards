"""Subprocess-driven tests for skills/realtime-audio-safety/check-realtime-safety.sh.

This is the shell analog of the boundaries grep-gate (tests/test_checks.py):
a line-level textual scanner with an in-band `RT-SAFE-OK: <reason>` waiver and
a live suppression count. No existing test shells out to a repo-shipped script,
so this drives the script through `subprocess` against committed C++ fixtures
and asserts on its exit code and stdout/stderr contract.
"""

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "skills" / "realtime-audio-safety" / "check-realtime-safety.sh"
FIXTURES = REPO_ROOT / "tests" / "fixtures" / "realtime-audio-safety"
VIOLATING = FIXTURES / "violating_callback.cpp"
WAIVED = FIXTURES / "waived_callback.cpp"


def run_check(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )


def test_script_is_present_and_executable():
    assert SCRIPT.is_file(), f"scanner missing at {SCRIPT}"


def test_violating_callback_is_flagged_and_exits_1():
    result = run_check(str(VIOLATING))
    assert result.returncode == 1
    # Each forbidden family the fixture exercises is named on stderr.
    assert "mutex/lock" in result.stderr
    assert "new/delete" in result.stderr
    assert "blocking I/O / syscall" in result.stderr
    assert "unbounded container growth" in result.stderr
    # The error teaches the escape hatch (escape-hatch-discipline).
    assert "RT-SAFE-OK" in result.stderr
    # Nothing was waived, so the live count is zero.
    assert "0 suppression(s) via RT-SAFE-OK" in result.stdout


def test_waived_callback_passes_and_reports_suppression_count():
    result = run_check(str(WAIVED))
    assert result.returncode == 0, result.stderr
    # Both the same-line and preceding-line waivers are counted and reported.
    assert "2 suppression(s) via RT-SAFE-OK" in result.stdout


def test_directory_target_recurses_and_flags(tmp_path):
    # Directory targets recurse into C/C++ sources; a bad file anywhere fails.
    (tmp_path / "voice.cpp").write_text(
        "void cb(int n) { float* p = new float[n]; }\n"
    )
    result = run_check(str(tmp_path))
    assert result.returncode == 1
    assert "new/delete" in result.stderr


def test_clean_callback_passes_with_zero_counts(tmp_path):
    clean = tmp_path / "clean.cpp"
    clean.write_text(
        "void renderBlock(float* out, int frames) {\n"
        "  for (int i = 0; i < frames; ++i) out[i] *= 0.5f;\n"
        "}\n"
    )
    result = run_check(str(clean))
    assert result.returncode == 0, result.stderr
    assert "0 violation(s)" in result.stdout
    assert "0 suppression(s)" in result.stdout


def test_no_arguments_is_a_usage_error():
    result = run_check()
    assert result.returncode == 2
    assert "usage:" in result.stderr


def test_missing_path_is_a_usage_error():
    result = run_check(str(FIXTURES / "does_not_exist.cpp"))
    assert result.returncode == 2
    assert "no such file or directory" in result.stderr
