---
name: research-provenance
description: Discipline for documentation that summarises external research, scholarship, or practitioner knowledge — make provenance explicit, credit precisely, and never let summarised prior work read as original research. Use whenever documentation states claims derived from published sources.
---

# Research provenance discipline

Documentation that compresses other people's scholarship into usable rules
is one careless sentence away from claiming that scholarship as its own.
This discipline makes every claim's provenance explicit and mechanically
checkable, so summarised prior work can never be mistaken for original
research.

## When to use

Trigger on any documentation work that states claims derived from published
sources — theory guides, design rationale citing papers, tutorial content
built on other people's analysis. Not needed for docs that only describe
the project's own code and decisions.

## The three claim classes

Every substantive claim in research-derived documentation belongs to
exactly one class, and the class must be visible to the reader:

1. **Sourced claim** — restates something a citable source says. Requires
   an inline citation linking to the bibliography.
2. **Practical distillation** — compresses documented practice into a rule
   of thumb no single source states. Must be flagged in the page's
   Attribution note ("Rules X and Y are this guide's practical
   distillations of …").
3. **Project-specific value** — parameter mappings, calibrations, defaults.
   Declared as the project's own ("All parameter values are ours").

## Rules

- **Stable citation anchors.** Bibliography entries carry explicit HTML ids
  (`<span id="ref-...">`). Content cites by link to the anchor — never by
  restating the reference inline — and entries are never renumbered.
- **Provenance statements at two levels.** The bibliography (or section
  landing page) carries a "nothing here is original research" declaration;
  each research-derived page carries a standard one-line provenance
  sentence near the top.
- **Attribution note per page.** Research-derived pages end their Sources
  section with an `**Attribution:**` note assigning every rule/claim to one
  of the three classes.
- **Credit the coiner.** Terminology is attributed to its originator, not
  only to the study that popularised it in your context (in the reference
  implementation: Keil 1987 for "participatory discrepancies", not just
  Prögler 1995).
- **Frameworks are organising devices.** If the doc arranges sourced ideas
  into a synthesis (a taxonomy, a rule format, a comparison frame), say the
  synthesis is arrangement, not discovery, and cite the origin of each
  load-bearing concept in it.
- **Cultural material: idiom-aware, never "authentic".** Content modelling
  a living tradition claims fidelity to cited scholarship only,
  acknowledges regional/era variation, and points readers at the
  tradition's own carriers.
- **Honest approximation notes.** Where the project cannot reproduce what
  the research describes, say so rather than silently implying fidelity.

## Verification (mechanical)

The `research-provenance` check (CLI subcommand and pre-commit hook id of
the same name) enforces the checkable subset. Opt in by configuring the
bibliography in `jk-standards.yaml`:

```yaml
research_provenance:
  bib_file: site/src/content/docs/appendix-references.mdx
  anchor_pattern: '(ref|fr)-[A-Za-z0-9-]+'     # default
  phrase: 'not original (research|theory)'      # default
```

It then verifies:

1. Every citation link (`#ref-*` / `#fr-*`, or whatever `anchor_pattern`
   matches) resolves to a defined id in the bibliography file.
2. Bibliography ids are unique.
3. Every page opted in via `provenance: research` front-matter contains a
   provenance sentence matching the configured phrase.
4. Every such page contains an `**Attribution:**` note.

Escape hatch: `# provenance-ok: <reason>` on the citing line or the line
above, for links that legitimately point outside the project's
bibliography. Pages that shouldn't carry the sentence/Attribution
requirements simply don't declare `provenance: research`.

## Origin

Extracted from the crediting pass on Poly's Theory Deep Dives section
([JimAKennedy/poly PR #159](https://github.com/JimAKennedy/poly/pull/159)),
where the discipline was first applied end to end. Poly is the reference
implementation: `site/src/content/docs/theory-*.mdx` and
`appendix-references.mdx` there show worked examples of every rule, and
`theory-counterpoint-overview.mdx` is the canonical example of the
section-level declaration ("None of this is original research…") and of
declaring an organising framework as arrangement rather than discovery.
