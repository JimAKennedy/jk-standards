---
name: sdlc-retro
description: Use when asked to measure, reconstruct, or periodically report how a portfolio's AI-assisted development workflow evolved — which tools/models were in use when, what guardrails appeared, how productivity and quality trended — or when updating an existing retrospective snapshot ledger.
---

# SDLC retrospective

A workflow retrospective is reconstructed from evidence, not memory. Git
records enough to date every tooling transition after the fact — but only if
each run collects the same way, into the same ledger, so runs stay comparable
and cheap. The failure this skill prevents is re-archaeology: every run
re-mining history with ad-hoc commands, producing numbers that don't reconcile
with last month's.

## The four evidence classes

1. **Trailer variants.** `Co-Authored-By:` model names fingerprint tool eras:
   the exact variant text ("Claude Opus 4.6", "Claude Opus 5 (1M context)")
   dates which assistant generation was in use, per week, per repo.
2. **Marker first-appearances.** The date a tooling file entered history
   (`git log --diff-filter=A`) dates a workflow change: CLAUDE.md, `.mcp.json`,
   pre-commit config, CI workflows, `jk-standards.yaml`, and friends.
3. **Weekly volumes.** Commits and line churn per ISO week, for throughput
   trends and dormancy detection.
4. **Environment state.** Plugin manifests, per-repo MCP server configs,
   install dates. This class is *ephemeral* — a machine rebuild or an
   uninstall destroys it — which is why collection must not be skipped just
   because git feels sufficient. Bank it while it exists.

## Collecting

`collect.py` beside this file extracts all four classes into one dated JSON
snapshot. It is the only collector; the snapshot directory is its output, and
nothing else's.

```sh
# baseline (first ever run — full history):
python collect.py --root <parent-of-repos> --out <ledger>/snapshots

# every later run — incremental:
python collect.py --root <parent-of-repos> --out <ledger>/snapshots --since auto
```

`--since auto` windows volumes and trailers from the previous snapshot's date;
marker first-appearances stay full-history so they never shift with the
window. Both window edges are enforced with `--since`/`--until`, so two
snapshots of the same window cannot disagree.

Rules that keep the ledger trustworthy:

- **Never write another collector.** A second script — even a better one —
  forks the schema and the numbers stop reconciling across runs. Improve
  `collect.py` itself, with its tests (`tests/test_sdlc_retro_collect.py` in
  jk-standards), and bump its `SCHEMA` when the shape changes.
- **Snapshots are append-only data.** One file per run, named by date. No
  hand edits, no regeneration of old snapshots, and no prose: interpretation
  goes in the report, not beside the evidence.
- **Investigate `unreadable` entries** in the snapshot rather than deleting
  the directories they name — a broken gitdir pointer is itself evidence (an
  orphaned worktree marks an abandoned workflow).

## Interpreting

Read the newest snapshot against the previous one and answer, in this order:

1. **Era check.** Did any trailer variant, MCP server version, or plugin
   change? A new variant or package version usually marks a tool/model
   transition — date it and say what it replaced.
2. **Guardrail check.** New marker first-appearances since last run = new
   guardrails or process adoption. Removals (a marker present last run whose
   file is gone) matter as much as additions.
3. **Throughput and survival.** Compare weekly volumes; flag repos going
   dormant and new repos appearing. Raw commit counts stop being comparable
   across workflow generations — prefer era-appropriate units (milestones,
   releases, PR-merged slices) when narrating trends, and say which unit you
   used.
4. **Recollection vs evidence.** When the human describes what they remember
   happening, check it against the dated artifacts and report differences
   plainly — sharpening dates is the main value of the exercise.

Write the interpretation into the standing report (for this portfolio: the
artifact linked from `retro/README.md`, updated in place so the URL is
stable), never into the snapshot directory.

## Cadence

Monthly is enough resolution to date transitions; run it after any machine
rebuild or tool migration *before* old state is cleaned up — the environment
evidence class only exists until then.
