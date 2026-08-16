"""Fixture-repo tests for the two workflow-composition checks.

Both checks reason about the relationship *between* workflow files, so every
test here builds a small `.github/workflows` tree rather than exercising a
parser in isolation — the composition is the thing under test.
"""

from pathlib import Path

import pytest

from jk_standards.checks import workflow_concurrency, workflow_permissions
from jk_standards.config import Config, ConfigError, load_config

_CALLER = ".github/workflows/caller.yml"
_CALLEE = ".github/workflows/callee.yml"


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def callee(permissions: str = "", job_permissions: str = "") -> str:
    """A minimal reusable workflow, optionally declaring permissions."""
    perms = f"permissions:\n{permissions}" if permissions else ""
    job_perms = f"    permissions:\n{job_permissions}" if job_permissions else ""
    return (
        "name: Callee\non:\n  workflow_call:\n"
        f"{perms}"
        "jobs:\n  build:\n    runs-on: ubuntu-latest\n"
        f"{job_perms}"
        "    steps:\n      - run: echo hi\n"
    )


def caller(permissions: str = "", job_extra: str = "", uses: str = "./" + _CALLEE) -> str:
    perms = f"permissions:\n{permissions}" if permissions else ""
    return f"name: Caller\non: [push]\n{perms}jobs:\n  call:\n{job_extra}    uses: {uses}\n"


# --------------------------------------------------------------------------
# workflow-permissions
# --------------------------------------------------------------------------


def test_permissions_caller_missing_scope_flagged(tmp_path):
    write(tmp_path, _CALLEE, callee("  pages: write\n"))
    write(tmp_path, _CALLER, caller("  contents: read\n"))
    assert workflow_permissions.run(tmp_path, Config()) == 1


def test_permissions_caller_superset_passes(tmp_path):
    write(tmp_path, _CALLEE, callee("  pages: write\n"))
    write(tmp_path, _CALLER, caller("  contents: read\n  pages: write\n"))
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_callee_job_level_scope_counted(tmp_path):
    """A job-level block inside the callee is bound by the same ceiling."""
    write(tmp_path, _CALLEE, callee(job_permissions="      issues: write\n"))
    write(tmp_path, _CALLER, caller("  contents: read\n"))
    assert workflow_permissions.run(tmp_path, Config()) == 1


def test_permissions_undeclared_caller_grant_skipped(tmp_path):
    """No caller block means the repo default applies — unknowable, so unjudged."""
    write(tmp_path, _CALLEE, callee("  pages: write\n"))
    write(tmp_path, _CALLER, caller())
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_callee_declaring_nothing_passes(tmp_path):
    write(tmp_path, _CALLEE, callee())
    write(tmp_path, _CALLER, caller("  contents: read\n"))
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_calling_job_block_overrides_workflow_level(tmp_path):
    """A grant on the calling job itself is the ceiling, not the file's."""
    write(tmp_path, _CALLEE, callee("  pages: write\n"))
    write(
        tmp_path,
        _CALLER,
        caller("  contents: read\n", job_extra="    permissions:\n      pages: write\n"),
    )
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_write_all_caller_satisfies_everything(tmp_path):
    write(tmp_path, _CALLEE, callee("  pages: write\n  issues: write\n"))
    write(
        tmp_path,
        _CALLER,
        f"name: C\non: [push]\npermissions: write-all\njobs:\n  call:\n    uses: ./{_CALLEE}\n",
    )
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_read_all_caller_fails_a_write_requirement(tmp_path):
    write(tmp_path, _CALLEE, callee("  pages: write\n"))
    write(
        tmp_path,
        _CALLER,
        f"name: C\non: [push]\npermissions: read-all\njobs:\n  call:\n    uses: ./{_CALLEE}\n",
    )
    assert workflow_permissions.run(tmp_path, Config()) == 1


def test_permissions_empty_caller_block_grants_nothing(tmp_path):
    """`permissions: {}` is an explicit denial, not an absent declaration."""
    write(tmp_path, _CALLEE, callee("  contents: read\n"))
    write(
        tmp_path,
        _CALLER,
        f"name: C\non: [push]\npermissions: {{}}\njobs:\n  call:\n    uses: ./{_CALLEE}\n",
    )
    assert workflow_permissions.run(tmp_path, Config()) == 1


def test_permissions_marker_same_line_exempts(tmp_path):
    write(tmp_path, _CALLEE, callee("  pages: write\n"))
    write(
        tmp_path,
        _CALLER,
        "name: C\non: [push]\npermissions:\n  contents: read\n"
        f"jobs:\n  call:\n    uses: ./{_CALLEE}  # workflow-permissions-ok: smoke\n",
    )
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_marker_line_above_exempts(tmp_path):
    write(tmp_path, _CALLEE, callee("  pages: write\n"))
    write(
        tmp_path,
        _CALLER,
        "name: C\non: [push]\npermissions:\n  contents: read\n"
        "jobs:\n  call:\n    # workflow-permissions-ok: smoke\n"
        f"    uses: ./{_CALLEE}\n",
    )
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_missing_callee_file_not_flagged(tmp_path):
    write(tmp_path, _CALLER, caller("  contents: read\n", uses="./.github/workflows/nope.yml"))
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_remote_callee_ignored(tmp_path):
    """A pinned `owner/repo@sha` callee lives outside the tree and is unreadable."""
    write(
        tmp_path,
        _CALLER,
        caller("  contents: read\n", uses=f"owner/repo/.github/workflows/x.yml@{'a' * 40}"),
    )
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_missing_workflows_dir_skipped(tmp_path):
    assert workflow_permissions.run(tmp_path, Config()) == 0


def test_permissions_one_finding_per_edge_not_per_scope(tmp_path):
    """Several missing scopes on one call are a single reviewable finding."""
    write(tmp_path, _CALLEE, callee("  pages: write\n  issues: write\n  id-token: write\n"))
    write(tmp_path, _CALLER, caller("  contents: read\n"))
    assert workflow_permissions.run(tmp_path, Config()) == 1


def test_permissions_unparseable_workflow_skipped(tmp_path):
    write(tmp_path, _CALLER, "name: [unclosed\n")
    assert workflow_permissions.run(tmp_path, Config()) == 0


# --------------------------------------------------------------------------
# workflow-concurrency
# --------------------------------------------------------------------------


def wf(concurrency: str) -> str:
    return f"name: W\non: [push]\n{concurrency}jobs:\n  b:\n    runs-on: ubuntu-latest\n"


def test_concurrency_unscoped_group_flagged(tmp_path):
    write(tmp_path, _CALLER, wf("concurrency:\n  group: build\n"))
    assert workflow_concurrency.run(tmp_path, Config()) == 1


def test_concurrency_ref_scoped_group_passes(tmp_path):
    write(tmp_path, _CALLER, wf("concurrency:\n  group: build-${{ github.ref }}\n"))
    assert workflow_concurrency.run(tmp_path, Config()) == 0


def test_concurrency_declared_global_lock_passes(tmp_path):
    write(tmp_path, _CALLER, wf("concurrency:\n  group: pages\n"))
    cfg = Config()
    cfg.workflow_concurrency_global_locks = ["pages"]
    assert workflow_concurrency.run(tmp_path, cfg) == 0


def test_concurrency_undeclared_lock_still_flagged(tmp_path):
    """Declaring one lock does not bless every other unscoped group."""
    write(tmp_path, _CALLER, wf("concurrency:\n  group: other\n"))
    cfg = Config()
    cfg.workflow_concurrency_global_locks = ["pages"]
    assert workflow_concurrency.run(tmp_path, cfg) == 1


def test_concurrency_job_level_group_flagged(tmp_path):
    write(
        tmp_path,
        _CALLER,
        "name: W\non: [push]\njobs:\n  b:\n    runs-on: ubuntu-latest\n"
        "    concurrency:\n      group: build\n",
    )
    assert workflow_concurrency.run(tmp_path, Config()) == 1


def test_concurrency_shorthand_string_form_flagged(tmp_path):
    """`concurrency: name` is the shorthand for `{group: name}` and is checked too."""
    write(tmp_path, _CALLER, wf("concurrency: build\n"))
    assert workflow_concurrency.run(tmp_path, Config()) == 1


def test_concurrency_expression_containing_ref_passes(tmp_path):
    """A ternary whose smoke branch is ref-scoped is the intended shape."""
    group = "${{ inputs.deploy && 'pages' || format('smoke-{0}', github.ref) }}"
    write(tmp_path, _CALLER, wf(f'concurrency:\n  group: "{group}"\n'))
    assert workflow_concurrency.run(tmp_path, Config()) == 0


def test_concurrency_marker_same_line_exempts(tmp_path):
    write(
        tmp_path,
        _CALLER,
        wf("concurrency:\n  group: build  # concurrency-scope-ok: deliberate\n"),
    )
    assert workflow_concurrency.run(tmp_path, Config()) == 0


def test_concurrency_marker_line_above_exempts(tmp_path):
    write(
        tmp_path,
        _CALLER,
        wf("concurrency:\n  # concurrency-scope-ok: deliberate\n  group: build\n"),
    )
    assert workflow_concurrency.run(tmp_path, Config()) == 0


def test_concurrency_block_without_group_ignored(tmp_path):
    write(tmp_path, _CALLER, wf("concurrency:\n  cancel-in-progress: true\n"))
    assert workflow_concurrency.run(tmp_path, Config()) == 0


def test_concurrency_custom_ref_tokens_respected(tmp_path):
    write(tmp_path, _CALLER, wf("concurrency:\n  group: build-${{ env.SLOT }}\n"))
    cfg = Config()
    cfg.workflow_concurrency_ref_tokens = ["env.SLOT"]
    assert workflow_concurrency.run(tmp_path, cfg) == 0


def test_concurrency_missing_workflows_dir_skipped(tmp_path):
    assert workflow_concurrency.run(tmp_path, Config()) == 0


def test_concurrency_unparseable_workflow_skipped(tmp_path):
    write(tmp_path, _CALLER, "name: [unclosed\n")
    assert workflow_concurrency.run(tmp_path, Config()) == 0


def test_concurrency_catches_the_deploy_site_regression(tmp_path):
    """The exact group that serialised this repo's PRs must not pass.

    `pages-deploy-${{ inputs.deploy }}` carries no ref token, so every branch
    shared one lock and concurrent pull requests cancelled each other's jobs.
    """
    write(tmp_path, _CALLER, wf("concurrency:\n  group: pages-deploy-${{ inputs.deploy }}\n"))
    assert workflow_concurrency.run(tmp_path, Config()) == 1


# --------------------------------------------------------------------------
# config validation
# --------------------------------------------------------------------------


def test_global_locks_absent_yields_empty(tmp_path):
    (tmp_path / "jk-standards.yaml").write_text("version: 1\n", encoding="utf-8")
    assert load_config(tmp_path).workflow_concurrency_global_locks == []


def test_global_locks_non_list_raises(tmp_path):
    (tmp_path / "jk-standards.yaml").write_text(
        "version: 1\nworkflow_concurrency:\n  global_locks: pages\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_global_locks_non_string_entry_raises(tmp_path):
    """Coercing `[5]` to `["5"]` would declare a lock nobody wrote."""
    (tmp_path / "jk-standards.yaml").write_text(
        "version: 1\nworkflow_concurrency:\n  global_locks:\n    - 5\n", encoding="utf-8"
    )
    with pytest.raises(ConfigError):
        load_config(tmp_path)


def test_workflow_dirs_configurable(tmp_path):
    (tmp_path / "jk-standards.yaml").write_text(
        "version: 1\n"
        "workflow_permissions:\n  workflow_dir: ci/flows\n"
        "workflow_concurrency:\n  workflow_dir: ci/flows\n",
        encoding="utf-8",
    )
    cfg = load_config(tmp_path)
    assert cfg.workflow_perm_dir == "ci/flows"
    assert cfg.workflow_concurrency_dir == "ci/flows"
