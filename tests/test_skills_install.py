"""In-process tests for the install-skills subcommand.

Exercises the network-free branches only: cli.main dispatch routing, --check
hash verification (OK / MISSING / HASH MISMATCH), and the version-pinned
--update-lock path. No download branch is touched, so these run offline.
"""

from __future__ import annotations

import hashlib
import io
import json
import tarfile
import urllib.error
from pathlib import Path
from typing import Self

import pytest

from jk_standards import __version__, skills_install
from jk_standards.cli import main as cli_main
from jk_standards.skills_install import compute_hash


def _make_skill(root: Path, dest_rel: str, name: str, body: str) -> str:
    """Write a SKILL.md under <root>/<dest_rel>/<name>/ and return its hash."""
    skill_md = root / dest_rel / name / "SKILL.md"
    skill_md.parent.mkdir(parents=True, exist_ok=True)
    skill_md.write_text(body, encoding="utf-8")
    return compute_hash(skill_md)


def _write_lock(root: Path, skills: dict, *, version: str | None = None) -> Path:
    lock: dict = {"skills": skills}
    if version is not None:
        lock["jkStandardsVersion"] = version
    lock_path = root / "skills-lock.json"
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    return lock_path


def _entry(source: str, name: str, computed_hash: str) -> dict:
    return {
        "source": source,
        "skillPath": f"skills/{name}/SKILL.md",
        "computedHash": computed_hash,
    }


# --- CLI dispatch routing ---------------------------------------------------


def test_cli_routes_install_skills_to_module(tmp_path, capsys):
    """`jk-standards install-skills --check` reaches skills_install, not a check."""
    h = _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha\n")
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", h)})

    rc = cli_main(["install-skills", "--check", "--root", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha: OK" in out


def test_cli_dispatch_preserves_exit_code(tmp_path):
    """A --check mismatch surfaces exit code 1 through cli.main."""
    _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha\n")
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", "deadbeef" * 8)})

    rc = cli_main(["install-skills", "--check", "--root", str(tmp_path)])

    assert rc == 1


# --- --check: OK / MISSING / HASH MISMATCH ----------------------------------


def test_check_all_ok_returns_zero(tmp_path, capsys):
    h1 = _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha\n")
    h2 = _make_skill(tmp_path, ".agents/skills", "beta", "# Beta\n")
    _write_lock(
        tmp_path,
        {
            "alpha": _entry("owner/repo", "alpha", h1),
            "beta": _entry("owner/repo", "beta", h2),
        },
    )

    rc = skills_install.main(["--check", "--root", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha: OK" in out
    assert "beta: OK" in out
    assert "2 ok, 0 mismatch, 0 missing" in out


def test_check_missing_reports_and_exits_1(tmp_path, capsys):
    _write_lock(tmp_path, {"ghost": _entry("owner/repo", "ghost", "a" * 64)})

    rc = skills_install.main(["--check", "--root", str(tmp_path)])

    assert rc == 1
    out = capsys.readouterr().out
    assert "ghost: MISSING" in out
    assert "0 ok, 0 mismatch, 1 missing" in out


def test_check_hash_mismatch_reports_and_exits_1(tmp_path, capsys):
    _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha real\n")
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", "b" * 64)})

    rc = skills_install.main(["--check", "--root", str(tmp_path)])

    assert rc == 1
    out = capsys.readouterr().out
    assert "alpha: HASH MISMATCH" in out
    assert "0 ok, 1 mismatch, 0 missing" in out


def test_check_respects_dest_flag(tmp_path, capsys):
    """--dest points --check at a non-default skills directory."""
    h = _make_skill(tmp_path, ".claude/skills", "alpha", "# Alpha\n")
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", h)})

    rc = skills_install.main(["--check", "--dest", ".claude/skills", "--root", str(tmp_path)])

    assert rc == 0
    assert "alpha: OK" in capsys.readouterr().out


# --- --update-lock: version pin + hash refresh ------------------------------


def test_update_lock_pins_version_when_missing(tmp_path, capsys):
    """A lock with no jkStandardsVersion gets the toolkit version pinned in."""
    h = _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha\n")
    lock_path = _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", h)})

    rc = skills_install.main(["--update-lock", "--root", str(tmp_path)])

    assert rc == 0
    lock = json.loads(lock_path.read_text())
    assert lock["jkStandardsVersion"] == __version__
    assert f"jkStandardsVersion pinned to {__version__}" in capsys.readouterr().out


def test_update_lock_refreshes_hash_and_pins_version(tmp_path, capsys):
    """A stale hash is rewritten to the on-disk value and the version pinned."""
    _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha changed\n")
    lock_path = _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", "0" * 64)})
    expected = compute_hash(tmp_path / ".agents/skills/alpha/SKILL.md")

    rc = skills_install.main(["--update-lock", "--root", str(tmp_path)])

    assert rc == 0
    lock = json.loads(lock_path.read_text())
    assert lock["skills"]["alpha"]["computedHash"] == expected
    assert lock["jkStandardsVersion"] == __version__
    assert "alpha: hash updated" in capsys.readouterr().out


def test_update_lock_rewrites_when_only_version_stale(tmp_path):
    """Even with all hashes current, a stale version pin forces a rewrite."""
    h = _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha\n")
    lock_path = _write_lock(
        tmp_path,
        {"alpha": _entry("owner/repo", "alpha", h)},
        version="0.0.0-old",
    )

    rc = skills_install.main(["--update-lock", "--root", str(tmp_path)])

    assert rc == 0
    lock = json.loads(lock_path.read_text())
    assert lock["jkStandardsVersion"] == __version__


def test_update_lock_noop_when_current(tmp_path, capsys):
    """Current hashes + current version pin => no rewrite, 'already current'."""
    h = _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha\n")
    _write_lock(
        tmp_path,
        {"alpha": _entry("owner/repo", "alpha", h)},
        version=__version__,
    )

    rc = skills_install.main(["--update-lock", "--root", str(tmp_path)])

    assert rc == 0
    assert "All hashes already current" in capsys.readouterr().out


def test_update_lock_skips_uninstalled_skill(tmp_path, capsys):
    """A skill with no SKILL.md on disk is skipped, not crashed on."""
    _write_lock(tmp_path, {"ghost": _entry("owner/repo", "ghost", "c" * 64)})

    rc = skills_install.main(["--update-lock", "--root", str(tmp_path)])

    assert rc == 0
    assert "ghost: not installed, skipping" in capsys.readouterr().out


# --- LockError -> exit 2 ----------------------------------------------------


def test_missing_lockfile_exits_2(tmp_path, capsys):
    """No skills-lock.json under an explicit root => usage/config exit code 2."""
    rc = skills_install.main(["--check", "--root", str(tmp_path)])

    assert rc == 2
    assert "not found" in capsys.readouterr().err


def test_cli_missing_lockfile_exits_2(tmp_path):
    """The LockError -> exit 2 contract holds through cli.main dispatch too."""
    rc = cli_main(["install-skills", "--update-lock", "--root", str(tmp_path)])

    assert rc == 2


def test_empty_skills_lock_returns_zero(tmp_path, capsys):
    """A lock with an empty skills map installs nothing and exits clean."""
    _write_lock(tmp_path, {})

    rc = skills_install.main(["--root", str(tmp_path)])

    assert rc == 0
    assert "No skills in lock file." in capsys.readouterr().out


# --- Stubbed-transport helpers ----------------------------------------------


def _sha(body: str) -> str:
    """sha256 of a UTF-8 string, matching compute_hash's read_bytes digest."""
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _make_archive(prefix: str, files: dict[str, str]) -> bytes:
    """Build a GitHub-style tar.gz: files keyed by path relative to the repo root.

    Members are named ``<prefix>/<relpath>`` to mimic GitHub's archive layout
    (a single top-level ``<repo>-<branch>/`` directory).
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for relpath, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=f"{prefix}/{relpath}")
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


class _FakeResp:
    """Minimal urlopen return value: a context manager exposing .read()."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> bool:
        return False


def _http_error(url: str, code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url, code, "err", {}, None)


def _stub_urlopen(monkeypatch, handler) -> list:
    """Route skills_install's urlopen through ``handler(req) -> bytes``.

    Returns a list that accumulates each Request object seen, so tests can
    assert on headers / URLs. ``handler`` may raise to simulate failures.
    """
    seen: list = []

    def fake_urlopen(req, *args, **kwargs):
        seen.append(req)
        return _FakeResp(handler(req))

    monkeypatch.setattr(skills_install.urllib.request, "urlopen", fake_urlopen)
    return seen


# --- install_skills: successful download + extract + hash-verify ------------


def test_install_downloads_and_installs_skill(tmp_path, capsys, monkeypatch):
    body = "# Alpha\nreal skill body\n"
    archive = _make_archive("repo-main", {"skills/alpha/SKILL.md": body})
    _stub_urlopen(monkeypatch, lambda req: archive)
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", _sha(body))})

    rc = skills_install.main(["--root", str(tmp_path)])

    assert rc == 0
    installed = tmp_path / ".agents/skills/alpha/SKILL.md"
    assert installed.read_text(encoding="utf-8") == body
    out = capsys.readouterr().out
    assert "alpha: installed" in out and "hash verified" in out
    assert "1 installed, 0 up-to-date, 0 failed" in out


def test_install_up_to_date_skips_without_download(tmp_path, capsys, monkeypatch):
    """A matching on-disk SKILL.md short-circuits before any network call."""
    body = "# Alpha\n"
    h = _make_skill(tmp_path, ".agents/skills", "alpha", body)
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", h)})

    def explode(req):  # pragma: no cover - asserts it is never reached
        raise AssertionError("urlopen should not be called for an up-to-date skill")

    _stub_urlopen(monkeypatch, explode)

    rc = skills_install.main(["--root", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha: up to date (skipped)" in out
    assert "0 installed, 1 up-to-date, 0 failed" in out


def test_install_hash_mismatch_reinstalls(tmp_path, capsys, monkeypatch):
    """A stale local SKILL.md is redownloaded and replaced."""
    _make_skill(tmp_path, ".agents/skills", "alpha", "# Alpha OLD\n")
    new_body = "# Alpha NEW\n"
    archive = _make_archive("repo-main", {"skills/alpha/SKILL.md": new_body})
    _stub_urlopen(monkeypatch, lambda req: archive)
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", _sha(new_body))})

    rc = skills_install.main(["--root", str(tmp_path)])

    assert rc == 0
    out = capsys.readouterr().out
    assert "alpha: hash mismatch, reinstalling" in out
    installed = tmp_path / ".agents/skills/alpha/SKILL.md"
    assert installed.read_text(encoding="utf-8") == new_body


def test_install_hash_verify_failure_installs_anyway(tmp_path, capsys, monkeypatch):
    """Downloaded SKILL.md not matching the pinned hash installs with a warning."""
    body = "# Alpha drifted upstream\n"
    archive = _make_archive("repo-main", {"skills/alpha/SKILL.md": body})
    _stub_urlopen(monkeypatch, lambda req: archive)
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", "f" * 64)})

    rc = skills_install.main(["--root", str(tmp_path)])

    assert rc == 0  # installed-anyway path does not count as a failure
    err = capsys.readouterr().err
    assert "hash verification failed" in err


def test_install_missing_skill_md_after_extract_fails(tmp_path, capsys, monkeypatch):
    """Archive lacking the skill's SKILL.md yields a per-skill failure, exit 1."""
    archive = _make_archive("repo-main", {"skills/alpha/README.md": "no skill here\n"})
    _stub_urlopen(monkeypatch, lambda req: archive)
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", "a" * 64)})

    rc = skills_install.main(["--root", str(tmp_path)])

    assert rc == 1
    err = capsys.readouterr().err
    assert "SKILL.md not found after extraction" in err


def test_install_download_failure_counts_failed(tmp_path, capsys, monkeypatch):
    """A URLError while downloading increments failed and exits 1."""

    def boom(req):
        raise urllib.error.URLError("no network")

    _stub_urlopen(monkeypatch, boom)
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", "a" * 64)})

    rc = skills_install.main(["--root", str(tmp_path)])

    assert rc == 1
    captured = capsys.readouterr()
    assert "1 failed" in captured.out
    assert "Failed to download owner/repo" in captured.err


def test_install_force_reinstalls_up_to_date_skill(tmp_path, capsys, monkeypatch):
    """--force downloads even when the on-disk hash already matches."""
    body = "# Alpha\n"
    h = _make_skill(tmp_path, ".agents/skills", "alpha", body)
    archive = _make_archive("repo-main", {"skills/alpha/SKILL.md": body})
    seen = _stub_urlopen(monkeypatch, lambda req: archive)
    _write_lock(tmp_path, {"alpha": _entry("owner/repo", "alpha", h)})

    rc = skills_install.main(["--force", "--root", str(tmp_path)])

    assert rc == 0
    assert len(seen) == 1  # download happened despite matching hash


# --- download_archive: 404 fallback + token injection -----------------------


def test_download_archive_falls_back_to_master(monkeypatch):
    """A 404 on main.tar.gz retries master before giving up."""
    body = "# X\n"
    archive = _make_archive("repo-master", {"skills/x/SKILL.md": body})

    def handler(req):
        if req.full_url.endswith("/main.tar.gz"):
            raise _http_error(req.full_url, 404)
        return archive

    seen = _stub_urlopen(monkeypatch, handler)

    tar = skills_install.download_archive("owner/repo")

    assert isinstance(tar, tarfile.TarFile)
    tar.close()
    assert [r.full_url.rsplit("/", 1)[-1] for r in seen] == ["main.tar.gz", "master.tar.gz"]


def test_download_archive_gives_up_after_all_branches(monkeypatch, capsys):
    """404 on main, master, and HEAD re-raises the HTTPError."""

    def handler(req):
        raise _http_error(req.full_url, 404)

    _stub_urlopen(monkeypatch, handler)

    with pytest.raises(urllib.error.HTTPError):
        skills_install.download_archive("owner/repo")
    assert "tried main/master/HEAD" in capsys.readouterr().err


def test_download_archive_reraises_non_404(monkeypatch):
    """A non-404 HTTP error is not retried and propagates immediately."""

    def handler(req):
        raise _http_error(req.full_url, 500)

    seen = _stub_urlopen(monkeypatch, handler)

    with pytest.raises(urllib.error.HTTPError):
        skills_install.download_archive("owner/repo")
    assert len(seen) == 1  # no fallback attempts on a 500


def test_download_archive_injects_github_token(monkeypatch):
    """GITHUB_TOKEN is sent as an Authorization header, never printed."""
    monkeypatch.setenv("GITHUB_TOKEN", "s3cr3t")
    archive = _make_archive("repo-main", {"skills/x/SKILL.md": "# X\n"})
    seen = _stub_urlopen(monkeypatch, lambda req: archive)

    skills_install.download_archive("owner/repo").close()

    assert seen[0].get_header("Authorization") == "token s3cr3t"


# --- extract_skill: direct unit ---------------------------------------------


def test_extract_skill_pulls_only_target_dir(tmp_path):
    archive = _make_archive(
        "repo-main",
        {
            "skills/alpha/SKILL.md": "# Alpha\n",
            "skills/alpha/ref.md": "ref\n",
            "skills/beta/SKILL.md": "# Beta\n",
            "README.md": "top-level\n",
        },
    )
    dest = tmp_path / "out"
    dest.mkdir()

    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as tar:
        count = skills_install.extract_skill(tar, "skills/alpha", dest)

    assert count == 2
    assert (dest / "SKILL.md").read_text(encoding="utf-8") == "# Alpha\n"
    assert (dest / "ref.md").exists()
    assert not (dest / "SKILL.md").is_dir()
    # beta and the top-level README must not leak into the alpha extraction
    assert not (dest / "beta").exists()


# --- find_project_root: walk-up discovery -----------------------------------


def test_find_project_root_walks_up_to_lockfile(tmp_path, monkeypatch):
    (tmp_path / "skills-lock.json").write_text("{}", encoding="utf-8")
    nested = tmp_path / "a" / "b" / "c"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    assert skills_install.find_project_root() == tmp_path


def test_find_project_root_defaults_to_cwd_when_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    assert skills_install.find_project_root() == tmp_path
