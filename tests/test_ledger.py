"""Unit tests for the ledger check.

The check's only inputs are the working tree — the ledgers under the
configured roots, the plan and evidence files they name, and the repo's
validations file — so every test builds a complete little programme under
``tmp_path`` rather than leaning on jk-standards' own docs.

``ledger()`` composes a conforming ledger from parts; each test perturbs one
part and asserts the single rule that governs it, so a failure names the rule
that broke rather than "the fixture no longer parses".
"""

from pathlib import Path

from jk_standards.checks import ledger
from jk_standards.config import Config

VALIDATIONS = "unit: pytest\ndoc-conformance: bash check-docs.sh\ngate: bash gate.sh\n"

HEADER = """---
class: gated
---

# Demo Ledger

Status: current (2026-08-26)

"""

MILESTONE = """## Milestone M001 — Theory Corrections

**Vision:** Every wrong claim is corrected and locked by a test.
**Branch:** milestone/M001-theory-corrections
**Status:** in-progress

"""

SLICE = """### Slice M001/S05 — Chapter 2 hedges

**Status:** open
**Validation:** doc-conformance, gate
**Evidence:** evidence/M001-S05.md
**Plan:** M001-S05-plan.md

**Definition of Done**

- [ ] The opening no longer asserts multi-century continuity

| ID | Item | Verification | Status |
|---|---|---|---|
| F07 | Unsourced centuries claim | Case `S05-F07` | `open` |
"""


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def programme(
    root: Path,
    body: str | None = None,
    *,
    validations: str | None = VALIDATIONS,
    plan: bool = True,
    evidence: bool = True,
) -> Path:
    """Build a complete programme under ``root`` and return the ledger path."""
    if validations is not None:
        write(root, ".jk/validations.yml", validations)
    if plan:
        write(root, "docs/plans/demo/M001-S05-plan.md", "# plan\n")
    if evidence:
        write(root, "docs/plans/demo/evidence/M001-S05.md", "# evidence\n")
    text = HEADER + MILESTONE + (SLICE if body is None else body)
    return write(root, "docs/plans/demo/ledger.md", text)


def run(root: Path) -> int:
    return ledger.run(root, Config())


# --- a conforming ledger passes ---------------------------------------------


def test_conforming_ledger_passes(tmp_path):
    programme(tmp_path)
    assert run(tmp_path) == 0


def test_no_ledger_is_not_a_violation(tmp_path):
    assert run(tmp_path) == 0


def test_ledger_outside_configured_roots_is_ignored(tmp_path):
    programme(tmp_path)
    cfg = Config()
    cfg.ledger_roots = ["docs/elsewhere"]
    assert ledger.run(tmp_path, cfg) == 0


# --- structure ---------------------------------------------------------------


def test_ledger_with_no_milestones_flagged(tmp_path):
    write(tmp_path, "docs/plans/demo/ledger.md", HEADER + "Nothing here.\n")
    assert run(tmp_path) == 1


def test_slice_before_any_milestone_flagged(tmp_path):
    write(tmp_path, "docs/plans/demo/ledger.md", HEADER + SLICE)
    assert run(tmp_path) >= 1


def test_slice_naming_a_different_milestone_flagged(tmp_path):
    programme(tmp_path, SLICE.replace("### Slice M001/S05", "### Slice M002/S05"))
    assert run(tmp_path) >= 1


def test_duplicate_slice_id_flagged(tmp_path):
    programme(tmp_path, SLICE + "\n" + SLICE)
    assert run(tmp_path) >= 1


def test_milestone_missing_required_key_flagged(tmp_path):
    write(tmp_path, ".jk/validations.yml", VALIDATIONS)
    write(tmp_path, "docs/plans/demo/M001-S05-plan.md", "# plan\n")
    write(tmp_path, "docs/plans/demo/evidence/M001-S05.md", "# evidence\n")
    write(
        tmp_path,
        "docs/plans/demo/ledger.md",
        HEADER + MILESTONE.replace("**Branch:** milestone/M001-theory-corrections\n", "") + SLICE,
    )
    assert run(tmp_path) == 1


# --- status vocabulary -------------------------------------------------------


def test_invalid_slice_status_flagged(tmp_path):
    programme(tmp_path, SLICE.replace("**Status:** open", "**Status:** started"))
    assert run(tmp_path) >= 1


def test_invalid_row_status_flagged(tmp_path):
    programme(tmp_path, SLICE.replace("| `open` |", "| `wip` |"))
    assert run(tmp_path) == 1


def test_accepted_is_a_valid_slice_status(tmp_path):
    body = SLICE.replace("**Status:** open", "**Status:** accepted").replace(
        "| `open` |", "| `accepted` |"
    )
    programme(tmp_path, body)
    assert run(tmp_path) == 0


# --- dependencies ------------------------------------------------------------


def test_depends_on_unknown_slice_flagged(tmp_path):
    programme(
        tmp_path, SLICE.replace("**Status:** open", "**Depends:** M001/S09\n**Status:** open")
    )
    assert run(tmp_path) == 1


def test_depends_on_declared_slice_passes(tmp_path):
    programme(
        tmp_path, SLICE.replace("**Status:** open", "**Depends:** M001/S05\n**Status:** open")
    )
    # Self-dependency is its own violation; the point here is that a declared
    # ID resolves rather than being reported as unknown.
    assert run(tmp_path) == 1


# --- definition of done ------------------------------------------------------


def test_slice_without_definition_of_done_flagged(tmp_path):
    body = SLICE.replace(
        "**Definition of Done**\n\n- [ ] The opening no longer asserts multi-century continuity\n",
        "",
    )
    programme(tmp_path, body)
    assert run(tmp_path) == 1


def test_done_slice_with_unchecked_item_flagged(tmp_path):
    programme(tmp_path, SLICE.replace("**Status:** open", "**Status:** done"))
    # Unchecked DoD item, plus the open row a done slice may not carry.
    assert run(tmp_path) == 2


def test_done_slice_fully_closed_passes(tmp_path):
    body = (
        SLICE.replace("**Status:** open", "**Status:** done")
        .replace("- [ ] The opening", "- [x] The opening")
        .replace("| `open` |", "| `done` |")
    )
    programme(tmp_path, body)
    assert run(tmp_path) == 0


# --- plan, evidence, and containment ----------------------------------------


def test_slice_past_open_without_plan_flagged(tmp_path):
    body = SLICE.replace("**Status:** open", "**Status:** in-progress").replace(
        "**Plan:** M001-S05-plan.md\n", ""
    )
    programme(tmp_path, body)
    assert run(tmp_path) == 1


def test_named_plan_that_does_not_exist_flagged(tmp_path):
    programme(tmp_path, plan=False)
    assert run(tmp_path) == 1


def test_done_slice_without_evidence_file_flagged(tmp_path):
    body = (
        SLICE.replace("**Status:** open", "**Status:** done")
        .replace("- [ ] The opening", "- [x] The opening")
        .replace("| `open` |", "| `done` |")
    )
    programme(tmp_path, body, evidence=False)
    assert run(tmp_path) == 1


def test_open_slice_without_evidence_file_passes(tmp_path):
    programme(tmp_path, evidence=False)
    assert run(tmp_path) == 0


def test_path_outside_the_ledger_directory_flagged(tmp_path):
    write(tmp_path, "elsewhere/plan.md", "# plan\n")
    programme(
        tmp_path, SLICE.replace("**Plan:** M001-S05-plan.md", "**Plan:** ../../elsewhere/plan.md")
    )
    assert run(tmp_path) == 1


# --- validation tokens -------------------------------------------------------


def test_undeclared_validation_token_flagged(tmp_path):
    programme(
        tmp_path, SLICE.replace("**Validation:** doc-conformance, gate", "**Validation:** e2e")
    )
    assert run(tmp_path) == 1


def test_token_arm_skips_without_a_validations_file(tmp_path):
    programme(
        tmp_path,
        SLICE.replace("**Validation:** doc-conformance, gate", "**Validation:** e2e"),
        validations=None,
    )
    assert run(tmp_path) == 0


def test_empty_validation_set_flagged(tmp_path):
    programme(tmp_path, SLICE.replace("**Validation:** doc-conformance, gate", "**Validation:**"))
    assert run(tmp_path) == 1


# --- rows --------------------------------------------------------------------


def test_row_table_missing_required_column_flagged(tmp_path):
    body = SLICE.replace("| ID | Item | Verification | Status |", "| ID | Item | Status |").replace(
        "|---|---|---|---|", "|---|---|---|"
    )
    programme(tmp_path, body)
    assert run(tmp_path) == 1


def test_row_without_verification_flagged(tmp_path):
    programme(tmp_path, SLICE.replace("| Case `S05-F07` |", "|  |"))
    assert run(tmp_path) == 1


def test_slice_without_a_row_table_passes(tmp_path):
    body = SLICE.split("| ID |")[0]
    programme(tmp_path, body)
    assert run(tmp_path) == 0


# --- placeholders and the escape hatch --------------------------------------


def test_placeholder_flagged(tmp_path):
    programme(tmp_path, SLICE.replace("Case `S05-F07`", "TBD"))
    assert run(tmp_path) == 1


def test_escape_hatch_suppresses_the_line_it_sits_on(tmp_path):
    body = SLICE.replace(
        "**Validation:** doc-conformance, gate",
        "**Validation:** manual-uat  <!-- ledger-ok: no automatable gate; UAT script in the plan -->",
    )
    programme(tmp_path, body)
    assert run(tmp_path) == 0


def test_escape_hatch_without_a_reason_does_not_suppress(tmp_path):
    body = SLICE.replace(
        "**Validation:** doc-conformance, gate",
        "**Validation:** manual-uat  <!-- ledger-ok: -->",
    )
    programme(tmp_path, body)
    assert run(tmp_path) == 1


# --- sections after the last slice -------------------------------------------


TRAILING_TABLE = """## Related issues

| Issue | Row | Relationship |
|---|---|---|
| #91 | F07 | Closed by F07. |
"""

# A slice whose row table sits below a sub-heading: the heading must close the
# definition-of-done checklist without closing the slice, or the rows below it
# belong to nothing.
SLICE_WITH_SUBHEADING = """### Slice M001/S05 — Chapter 2 hedges

**Status:** open
**Validation:** doc-conformance, gate
**Evidence:** evidence/M001-S05.md
**Plan:** M001-S05-plan.md

**Definition of Done**

- [ ] The opening no longer asserts multi-century continuity

#### Rows

| ID | Item | Verification | Status |
|---|---|---|---|
| F07 | Unsourced centuries claim | Case `S05-F07` | `open` |
"""


def test_milestone_level_section_after_the_last_slice_is_not_absorbed(tmp_path):
    """A trailing `## ...` section's table is a sibling, not the slice's rows.

    Without this, every pipe table below the last slice is folded into that
    slice's row table, so a ledger carrying a "Related issues" table fails
    with a row whose Status cell is empty — a violation the author cannot act
    on, because the table is not a row table at all.
    """
    programme(tmp_path, body=SLICE + "\n" + TRAILING_TABLE)
    assert run(tmp_path) == 0


def test_sub_heading_inside_a_slice_keeps_the_slice_open(tmp_path):
    """Headings deeper than a milestone stay inside the slice they sit in.

    The guard above must not over-correct: a slice may carry sub-headings
    after its checklist, and rows below one still belong to it.
    """
    programme(tmp_path, body=SLICE_WITH_SUBHEADING)
    assert run(tmp_path) == 0


# --- commit SHAs named by evidence files ------------------------------------


def git_repo(root: Path) -> str:
    """Init a repo under ``root`` with one commit; return its short SHA."""
    import subprocess

    def git(*args):
        return subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout.strip()

    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "T")
    git("add", "-A")
    git("commit", "-qm", "fixture")
    return git("rev-parse", "--short", "HEAD")


def test_evidence_naming_an_unresolvable_commit_flagged(tmp_path):
    """A SHA that resolves to nothing is a fabrication, and reads as a fact.

    Evidence is the difference between an asserted completion and a
    demonstrated one, so an invented SHA does more damage than an omitted
    one: `TBD` is greppable, `6ec18b6` is indistinguishable from a real
    commit and will be trusted.
    """
    programme(tmp_path)
    git_repo(tmp_path)
    write(
        tmp_path,
        "docs/plans/demo/evidence/M001-S05.md",
        "## M001/S05 — task 1\n\n- `unit` → exit 0\n- commit `6ec18b6`\n- 2026-08-28\n",
    )
    assert run(tmp_path) == 1


def test_evidence_naming_a_real_commit_passes(tmp_path):
    programme(tmp_path)
    sha = git_repo(tmp_path)
    write(
        tmp_path,
        "docs/plans/demo/evidence/M001-S05.md",
        f"## M001/S05 — task 1\n\n- `unit` → exit 0\n- commit `{sha}`\n- 2026-08-28\n",
    )
    assert run(tmp_path) == 0


def test_evidence_without_a_commit_line_passes(tmp_path):
    """Omitting the SHA is the normal case for evidence written as work lands."""
    programme(tmp_path)
    git_repo(tmp_path)
    write(
        tmp_path,
        "docs/plans/demo/evidence/M001-S05.md",
        "## M001/S05 — task 1\n\n- `unit` → exit 0\n- 2026-08-28\n",
    )
    assert run(tmp_path) == 0


def test_evidence_shas_unchecked_outside_a_git_repo(tmp_path):
    """No object database, no opinion — the same posture doc-drift takes.

    A shallow CI clone cannot resolve an old SHA, and failing there would
    punish a correct ledger for its checkout depth.
    """
    programme(tmp_path)
    write(
        tmp_path,
        "docs/plans/demo/evidence/M001-S05.md",
        "## M001/S05 — task 1\n\n- `unit` → exit 0\n- commit `6ec18b6`\n- 2026-08-28\n",
    )
    assert run(tmp_path) == 0


def shallow_clone(src: Path, dest: Path) -> None:
    """Clone ``src`` into ``dest`` with a truncated history.

    ``file://`` is deliberate: git optimises a plain local-path clone into
    hardlinks and ignores ``--depth`` entirely, so a test that omits the
    protocol silently builds a *complete* clone and proves nothing.
    """
    import subprocess

    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", f"file://{src}", str(dest)],
        capture_output=True,
        text=True,
        check=True,
    )


def test_evidence_shas_unchecked_in_a_shallow_clone(tmp_path):
    """A commit absent because history was truncated is not a fabrication.

    This is the case that reaches CI: pre-commit.ci and any
    ``fetch-depth: 1`` checkout hold one commit, so a SHA recorded from a
    merge months ago cannot be resolved there. Reporting it would fail a
    truthful record on the strength of a thin checkout, and the whole point
    of the tri-state return is to refuse that.
    """
    origin = tmp_path / "origin"
    origin.mkdir()
    programme(origin)
    sha = git_repo(origin)

    # A second commit, so the shallow clone's single commit is not the one
    # the evidence names.
    import subprocess

    write(origin, "docs/plans/demo/evidence/M001-S05.md", f"- commit `{sha}`\n")
    for args in (["add", "-A"], ["commit", "-qm", "second"]):
        subprocess.run(["git", *args], cwd=origin, capture_output=True, check=True)

    clone = tmp_path / "clone"
    shallow_clone(origin, clone)
    import subprocess as sp

    assert (
        sp.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            cwd=clone,
            capture_output=True,
            text=True,
        ).stdout.strip()
        == "true"
    ), "fixture did not produce a shallow clone"

    assert run(clone) == 0
