"""ledger: enforce the delivery-ledger format.

A ledger (`docs/ledger-standard.md`) is the whole state of a delivery
programme in one Markdown file: milestones, the slices they decompose into,
the rows each slice closes, each slice's definition of done, and the
validation tokens that must pass before it may claim to be done. The file is
the state; git is the history. Nothing synchronises, so nothing desyncs.

What a file cannot do is enforce its own invariants — which is what this check
is for. It recovers, as a gate, the guarantees a schema would have given:

  1. Milestone and slice IDs are well-formed and unique, and a slice sits
     under the milestone whose ID it names.
  2. Milestones and slices declare their required keys, with status values
     from the declared vocabulary.
  3. `Depends` names slices that exist in the same ledger.
  4. Every slice carries a non-empty definition of done — a slice without one
     cannot be finished, only abandoned.
  5. Every validation token is declared by the consuming repository, so a typo
     is a failure rather than a silently skipped gate.
  6. A `done` slice has every DoD box checked, an evidence file on disk, and
     rows that are all `done` or `accepted`.
  7. Plan and evidence paths stay inside the ledger's own directory, so a
     programme is one movable tree.
  8. No placeholder text survives into a committed ledger.

Each finding is suppressible in place with a `<!-- ledger-ok: reason -->`
comment on the flagged line, following the toolkit's escape-hatch discipline:
in-band, greppable, and carrying a written reason.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from jk_standards import output
from jk_standards.config import Config

LEDGER_NAME = "ledger.md"

MILESTONE_STATUSES = ("planned", "in-progress", "done")
SLICE_STATUSES = ("open", "in-progress", "done", "accepted")
ROW_STATUSES = SLICE_STATUSES

MILESTONE_REQUIRED_KEYS = ("Vision", "Branch", "Status")
SLICE_REQUIRED_KEYS = ("Status", "Validation", "Evidence")
# Lower-cased so a ledger may capitalise its table headers however it likes.
ROW_REQUIRED_COLUMNS = ("id", "item", "verification", "status")

_MILESTONE_RE = re.compile(r"^##\s+Milestone\s+(M\d{3})\s*[—–-]\s*(.+?)\s*$")
_SLICE_RE = re.compile(r"^###\s+Slice\s+(M\d{3})/(S\d{2})\s*[—–-]\s*(.+?)\s*$")
_HEADING_RE = re.compile(r"^#{1,6}\s")
_KEY_RE = re.compile(r"^\*\*([A-Za-z][A-Za-z ]*):\*\*\s*(.*?)\s*$")
_DOD_RE = re.compile(r"^\*\*Definition of Done\*\*\s*$")
_CHECKBOX_RE = re.compile(r"^\s*-\s*\[([ xX])\]\s*(.*)$")
_TABLE_SEPARATOR_RE = re.compile(r"^\|[\s:|-]+\|$")
# Placeholders a plan or ledger must never ship with. Bounded by non-word
# characters so a row whose Item legitimately discusses "TODO markers" as
# subject matter is not caught by its own quotation.
_PLACEHOLDER_RE = re.compile(r"(?<![\w-])(TBD|TODO|FIXME|XXX|_pending_|\?\?\?)(?![\w-])")
# The reason is captured, not just matched: an empty `<!-- ledger-ok: -->`
# suppresses nothing, because a hatch without a written reason is exactly
# the silent suppression this discipline exists to prevent.
_HATCH_RE = re.compile(r"<!--\s*ledger-ok:\s*(.*?)\s*-->")


@dataclass
class Row:
    """One table row inside a slice: the smallest traceable unit."""

    cells: dict[str, str]
    line: int


@dataclass
class Slice:
    sid: str
    line: int
    milestone: str
    keys: dict[str, tuple[str, int]] = field(default_factory=dict)
    dod: list[tuple[bool, int]] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)
    row_header: tuple[list[str], int] | None = None


@dataclass
class Milestone:
    mid: str
    line: int
    keys: dict[str, tuple[str, int]] = field(default_factory=dict)
    slices: list[Slice] = field(default_factory=list)


def run(root: Path, cfg: Config) -> int:
    ledgers = find_ledgers(root, cfg)
    if not ledgers:
        output.summary(
            f"ledger: no {LEDGER_NAME} under {', '.join(cfg.ledger_roots)} — nothing to check"
        )
        return 0

    tokens = load_validation_tokens(root, cfg)
    if tokens is None:
        output.summary(
            f"ledger: validation-token arm skipped — no {cfg.ledger_validations} in the repo"
        )

    errors = 0
    for path in ledgers:
        errors += _check_ledger(root, path, tokens)

    if errors == 0:
        output.summary(f"ledger: {len(ledgers)} ledger(s) conform")
    return errors


def find_ledgers(root: Path, cfg: Config) -> list[Path]:
    """Every ``ledger.md`` under the configured ledger roots, sorted."""
    found: list[Path] = []
    for ledger_root in cfg.ledger_roots:
        base = root / ledger_root
        if not base.is_dir():
            continue
        found.extend(sorted(base.rglob(LEDGER_NAME)))
    return found


def load_validation_tokens(root: Path, cfg: Config) -> set[str] | None:
    """Declared validation tokens, or ``None`` when the repo declares none.

    Returning ``None`` rather than an empty set is the difference between "this
    repo declares no tokens, so every token is a typo" and "this repo has no
    validations file, so the arm cannot judge". The caller skips the arm on
    ``None`` and says so, the same fail-open shape the status-prose accuracy
    arm uses for a missing base ref.
    """
    path = root / cfg.ledger_validations
    if not path.is_file():
        return None
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    return {str(k) for k in data}


def _hatched(line: str) -> bool:
    m = _HATCH_RE.search(line)
    return bool(m and m.group(1).strip())


def _unwrap(value: str) -> str:
    """Strip the backticks a ledger may wrap a path or token in."""
    return value.strip().strip("`").strip()


def parse(text: str) -> tuple[list[Milestone], list[tuple[int, str]]]:
    """Parse a ledger into milestones, plus (line, message) structural errors.

    Structural errors are the ones that make the rest of the parse
    meaningless — a slice before any milestone, a slice claiming a milestone
    other than the section it sits in — so they are collected here rather than
    re-derived by every rule below.
    """
    milestones: list[Milestone] = []
    structural: list[tuple[int, str]] = []
    current_m: Milestone | None = None
    current_s: Slice | None = None
    in_dod = False

    for lineno, line in enumerate(text.splitlines(), start=1):
        m = _MILESTONE_RE.match(line)
        if m:
            current_m = Milestone(mid=m.group(1), line=lineno)
            milestones.append(current_m)
            current_s = None
            in_dod = False
            continue

        s = _SLICE_RE.match(line)
        if s:
            mid, snum = s.group(1), s.group(2)
            if current_m is None:
                structural.append(
                    (lineno, f"slice {mid}/{snum} appears before any milestone heading")
                )
                current_s = None
                in_dod = False
                continue
            if mid != current_m.mid:
                structural.append(
                    (
                        lineno,
                        f"slice {mid}/{snum} names milestone {mid} but sits under "
                        f"{current_m.mid} — a slice belongs to the section it is written in",
                    )
                )
            current_s = Slice(sid=f"{mid}/{snum}", line=lineno, milestone=current_m.mid)
            current_m.slices.append(current_s)
            in_dod = False
            continue

        if _HEADING_RE.match(line):
            # Any other heading closes the DoD checklist but leaves the slice
            # open, so a slice may carry sub-headings after its checklist.
            in_dod = False
            continue

        if current_s is not None and _DOD_RE.match(line):
            in_dod = True
            continue

        if in_dod and current_s is not None:
            box = _CHECKBOX_RE.match(line)
            if box:
                current_s.dod.append((box.group(1).lower() == "x", lineno))
                continue
            if line.strip():
                in_dod = False

        key = _KEY_RE.match(line)
        if key:
            name, value = key.group(1).strip(), key.group(2)
            target = (
                current_s.keys
                if current_s is not None
                else (current_m.keys if current_m is not None else None)
            )
            if target is not None:
                target[name] = (value, lineno)
            continue

        if current_s is not None and line.lstrip().startswith("|"):
            _absorb_table_line(current_s, line, lineno)

    return milestones, structural


def _absorb_table_line(sl: Slice, line: str, lineno: int) -> None:
    """Fold one pipe-table line into the slice's row table."""
    if _TABLE_SEPARATOR_RE.match(line.strip()):
        return
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    if sl.row_header is None:
        sl.row_header = ([c.lower() for c in cells], lineno)
        return
    header = sl.row_header[0]
    # strict=False deliberately: a hand-edited table can have a row with
    # more or fewer cells than its header, and that is a finding to report
    # through the missing-column and status rules, not a crash.
    sl.rows.append(Row(cells=dict(zip(header, cells, strict=False)), line=lineno))


def _check_ledger(root: Path, path: Path, tokens: set[str] | None) -> int:
    rel = path.relative_to(root).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    milestones, structural = parse(text)
    errors = 0

    def report(lineno: int, message: str) -> None:
        nonlocal errors
        if 1 <= lineno <= len(lines) and _hatched(lines[lineno - 1]):
            return
        output.error(rel, lineno, message)
        errors += 1

    for lineno, message in structural:
        report(lineno, message)

    if not milestones:
        output.error(
            rel, 1, "ledger declares no milestones — expected '## Milestone M001 — <title>'"
        )
        return errors + 1

    all_slice_ids = {sl.sid for m in milestones for sl in m.slices}
    _check_uniqueness(milestones, report)
    _check_placeholders(lines, report)

    for milestone in milestones:
        _check_keys(
            milestone.keys,
            MILESTONE_REQUIRED_KEYS,
            milestone.line,
            f"milestone {milestone.mid}",
            report,
        )
        _check_status(
            milestone.keys, MILESTONE_STATUSES, milestone.line, f"milestone {milestone.mid}", report
        )
        for sl in milestone.slices:
            _check_slice(path, sl, all_slice_ids, tokens, report)

    return errors


def _check_uniqueness(milestones: list[Milestone], report) -> None:
    seen_m: dict[str, int] = {}
    seen_s: dict[str, int] = {}
    for milestone in milestones:
        if milestone.mid in seen_m:
            report(
                milestone.line,
                f"duplicate milestone {milestone.mid} — first declared on "
                f"line {seen_m[milestone.mid]}",
            )
        else:
            seen_m[milestone.mid] = milestone.line
        for sl in milestone.slices:
            if sl.sid in seen_s:
                report(
                    sl.line, f"duplicate slice {sl.sid} — first declared on line {seen_s[sl.sid]}"
                )
            else:
                seen_s[sl.sid] = sl.line


def _check_placeholders(lines: list[str], report) -> None:
    for lineno, line in enumerate(lines, start=1):
        m = _PLACEHOLDER_RE.search(line)
        if m:
            report(
                lineno,
                f"placeholder '{m.group(1)}' in a committed ledger — state the real value "
                f"or record the row as 'open' with what is still unknown",
            )


def _check_keys(keys, required, lineno: int, subject: str, report) -> None:
    for name in required:
        if name not in keys:
            report(lineno, f"{subject} is missing its **{name}:** line")


def _check_status(keys, allowed, lineno: int, subject: str, report) -> None:
    if "Status" not in keys:
        return
    value, value_line = keys["Status"]
    if _unwrap(value) not in allowed:
        report(
            value_line,
            f"{subject} has status '{_unwrap(value)}' — expected one of {', '.join(allowed)}",
        )


def _check_slice(
    ledger_path: Path, sl: Slice, all_slice_ids: set[str], tokens: set[str] | None, report
) -> None:
    subject = f"slice {sl.sid}"
    _check_keys(sl.keys, SLICE_REQUIRED_KEYS, sl.line, subject, report)
    _check_status(sl.keys, SLICE_STATUSES, sl.line, subject, report)

    status = _unwrap(sl.keys["Status"][0]) if "Status" in sl.keys else ""

    if status and status != "open" and "Plan" not in sl.keys:
        report(
            sl.line,
            f"{subject} is '{status}' but declares no **Plan:** — work past 'open' "
            f"implements a plan, and the ledger is where its path is recorded",
        )

    _check_depends(sl, all_slice_ids, report)
    _check_dod(sl, status, report)
    _check_paths(ledger_path, sl, status, report)
    _check_validation(sl, tokens, report)
    _check_rows(sl, status, report)


def _check_depends(sl: Slice, all_slice_ids: set[str], report) -> None:
    if "Depends" not in sl.keys:
        return
    value, lineno = sl.keys["Depends"]
    for dep in _split_tokens(value):
        if dep == sl.sid:
            report(lineno, f"slice {sl.sid} depends on itself")
        elif dep not in all_slice_ids:
            report(
                lineno, f"slice {sl.sid} depends on '{dep}', which no slice in this ledger declares"
            )


def _check_dod(sl: Slice, status: str, report) -> None:
    if not sl.dod:
        report(
            sl.line,
            f"slice {sl.sid} has no definition of done — add a '**Definition of Done**' "
            f"checklist; a slice without one cannot be finished, only abandoned",
        )
        return
    if status != "done":
        return
    for checked, lineno in sl.dod:
        if not checked:
            report(lineno, f"slice {sl.sid} is 'done' with an unchecked definition-of-done item")


def _check_paths(ledger_path: Path, sl: Slice, status: str, report) -> None:
    ledger_dir = ledger_path.parent
    for name in ("Plan", "Evidence"):
        if name not in sl.keys:
            continue
        raw, lineno = sl.keys[name]
        value = _unwrap(raw)
        if not value:
            report(lineno, f"slice {sl.sid} declares an empty **{name}:** path")
            continue
        target = (ledger_dir / value).resolve()
        if Path(value).is_absolute() or ledger_dir.resolve() not in target.parents:
            report(
                lineno,
                f"slice {sl.sid} **{name}:** '{value}' resolves outside the ledger's own "
                f"directory — a programme must stay one movable tree",
            )
            continue
        # An evidence file is only owed once the slice claims to be done; a plan
        # is owed the moment its path is written down.
        if name == "Plan" and not target.is_file():
            report(lineno, f"slice {sl.sid} names plan '{value}', which does not exist")
        if name == "Evidence" and status == "done" and not target.is_file():
            report(
                lineno,
                f"slice {sl.sid} is 'done' but its evidence file '{value}' does not exist — "
                f"a completion claim needs the record of what was run",
            )


def _check_validation(sl: Slice, tokens: set[str] | None, report) -> None:
    if "Validation" not in sl.keys:
        return
    value, lineno = sl.keys["Validation"]
    declared = _split_tokens(value)
    if not declared:
        report(lineno, f"slice {sl.sid} declares an empty **Validation:** set")
        return
    if tokens is None:
        return
    for token in declared:
        if token not in tokens:
            report(
                lineno,
                f"slice {sl.sid} names validation token '{token}', which the repo's "
                f"validations file does not declare",
            )


def _check_rows(sl: Slice, status: str, report) -> None:
    if sl.row_header is None:
        return
    header, header_line = sl.row_header
    missing = [c for c in ROW_REQUIRED_COLUMNS if c not in header]
    if missing:
        report(
            header_line,
            f"slice {sl.sid} row table is missing column(s) {', '.join(missing)} — "
            f"required: {', '.join(ROW_REQUIRED_COLUMNS)}",
        )
        return
    for row in sl.rows:
        row_status = _unwrap(row.cells.get("status", ""))
        row_id = _unwrap(row.cells.get("id", "?"))
        if row_status not in ROW_STATUSES:
            report(
                row.line,
                f"row {row_id} has status '{row_status}' — expected one of "
                f"{', '.join(ROW_STATUSES)}",
            )
            continue
        if not _unwrap(row.cells.get("verification", "")):
            report(
                row.line,
                f"row {row_id} has no verification — name the test, check, or "
                f"artifact that proves it",
            )
        if status == "done" and row_status not in ("done", "accepted"):
            report(
                row.line,
                f"slice {sl.sid} is 'done' but row {row_id} is '{row_status}' — "
                f"close the row or record it as 'accepted'",
            )


def _split_tokens(value: str) -> list[str]:
    """Comma-separated cell into cleaned tokens, ignoring any trailing comment."""
    value = value.split("<!--")[0]
    return [_unwrap(part) for part in value.split(",") if _unwrap(part)]
