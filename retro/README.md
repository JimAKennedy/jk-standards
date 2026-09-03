# SDLC retrospective snapshots

Dated evidence snapshots of the `~/dev` portfolio's AI-assisted workflow
evolution, produced by the `sdlc-retro` skill's collector:

```sh
python skills/sdlc-retro/collect.py --root ~/dev --out retro/snapshots --since auto
```

The method — what the evidence classes are, how to run a baseline vs an
incremental update, and how to interpret a snapshot into a report — is
`skills/sdlc-retro/SKILL.md`.

Snapshots are append-only: one JSON file per run, named by collection date.
Never rewrite an old snapshot — each one banks evidence (install manifests,
MCP configs, environment state) that may no longer exist by the next run.
The full-history narrative report built from the 2026-09-03 baseline lives at
<https://claude.ai/code/artifact/ddcad0cb-524c-44ce-8164-f46612fcd144>.

This directory sits outside the governed `doc_roots` deliberately: it is a
data ledger about the developer's portfolio, not toolkit documentation.
