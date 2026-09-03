# SDLC retrospective ledger — snapshots and report brief

Dated evidence snapshots of the `~/dev` portfolio's AI-assisted workflow
evolution, produced by the `sdlc-retro` skill's collector:

```sh
python skills/sdlc-retro/collect.py --root ~/dev --out retro/snapshots --since auto
```

The method — evidence classes, ledger rules, interpretation order, and the
standing-report update contract — is `skills/sdlc-retro/SKILL.md`. Snapshots
are append-only: one JSON file per run, named by collection date, never
rewritten or annotated. This directory sits outside the governed `doc_roots`
deliberately: it is a data ledger about the developer's portfolio, not
toolkit documentation.

## Report brief

The skill reads this section before interpreting; it overrides the skill's
defaults.

- **Standing report**: the "Workflow Archaeology" artifact at
  <https://claude.ai/code/artifact/ddcad0cb-524c-44ce-8164-f46612fcd144>.
  Update it in place — the URL is what gets shared; never publish a new
  artifact for a periodic run.
- **Audience**: people other than Jim. The report exists so Jim can show
  objectively *what happened, what the major moves were, and what the
  productivity/quality benefits were*. Write for a reader with none of the
  project context.
- **Framing rules**: a repo with no recent commits is a **working product in
  active use whose development is paused** — never "dead", "abandoned", or
  "died". Short-cycle projects are measured by product delivery (a finished
  tool per burst); process-managed projects by sustained evolution.
- **Exclusions**: `~/dev/microservices-demo` (upstream Google clone, scan
  fodder for nfr-review) is excluded from all analysis. Repos listed under
  `unreadable` in a snapshot are investigated, not dropped silently.
- **Baseline constants** (manual + Copilot-autocomplete era, DrumGenerator,
  2025-11-30 → 2025-12-17): **3.6 commits/week, ~1,000 lines/week, zero
  tests/CI/releases**. Quantified productivity claims are measured against
  these; the established reference points are ≈17× commits and ≈28× lines
  in the same repo's first Claude Code month, ≈13× sustained portfolio
  throughput (a floor — later commits are validated PR slices). State the
  caveats whenever quoting the multiples.
- **Era numbering**: eras 0–7 as established in the report (manual → API
  automation → Claude Code → scaffolds → GSD 1.x → GSD 2.0 → GSD-Pi →
  post-GSD). A new workflow generation appends era 8, and so on — never
  renumber existing eras.
- **Ledger tracking**: `retro/snapshots/` is **gitignored** — this repo is
  public and snapshots carry private telemetry (local paths, environment
  manifests, per-repo activity). Never commit a snapshot; they live only on
  the owner's machine. This README (the brief) is tracked and reusable.
