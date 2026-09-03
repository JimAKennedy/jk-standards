---
description: Run the periodic SDLC retrospective — collect an incremental evidence snapshot and interpret it against the previous one
argument-hint: "[repos-root] [snapshots-dir]"
---

Run one cycle of the portfolio retrospective: bank this period's evidence,
read it against the last snapshot, and update the standing report. The method
lives in the `sdlc-retro` skill; this command drives it and stops.

## 1. Locate the skill and its collector

Find `sdlc-retro/SKILL.md` with `collect.py` beside it — in a consuming repo
under the installed skills directory (`.agents/skills/sdlc-retro/`), in
jk-standards itself under `skills/sdlc-retro/`. Read the SKILL.md now; it, not
this command, defines the evidence classes, the ledger rules, and the
interpretation order. Refuse, and say so, if the skill is not installed —
do not improvise a collector; that is the exact failure the skill exists to
prevent.

## 2. Resolve the arguments

- **repos-root** — the directory whose immediate subdirectories are the
  portfolio's repos. Default: the parent directory of the current repo.
- **snapshots-dir** — the snapshot ledger. Default: `retro/snapshots` in the
  current repo, created by the collector on first run.

Say what both resolved to before collecting.

## 3. Collect

```sh
python <collector> --root <repos-root> --out <snapshots-dir> --since auto
```

`--since auto` makes the first-ever run a full-history baseline and every
later run an incremental window from the previous snapshot — say which of the
two this run was. Do not pass `--today`: backdating a routine run makes the
ledger lie about when evidence was banked.

## 4. Interpret

Follow the skill's interpretation order (era check, guardrail check,
throughput and survival, recollection vs evidence), reading the new snapshot
against the previous one. On a baseline run there is no previous snapshot —
interpretation is the full-history reconstruction instead, and it is not
quick; offer it as its own piece of work rather than rushing it inside the
routine.

## 5. Record and stop

Write the interpretation into the standing report the snapshot directory's
README points at — never into the snapshot directory itself. Commit what the
run changed in tracked files as one commit; include the snapshot only where
the brief says the ledger is tracked (in a public repo it is normally
gitignored — then say where the snapshot landed instead). Report the
window covered, the headline changes in one or two sentences each, and
anything the skill's rules flagged (`unreadable` entries, a marker removal,
an empty environment scan), then stop.
