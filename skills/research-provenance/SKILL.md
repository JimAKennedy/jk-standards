---
name: research-provenance
description: Discipline for documentation that summarises external research, scholarship, or practitioner knowledge — make provenance explicit, credit precisely, verify that every citation names a work that exists and says what you claim, and never let summarised prior work read as original research. Use whenever documentation states claims derived from published sources.
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

## The citation must name the work it points at

The rules above govern how a claim is *framed* against its source. They all
assume the citation itself is correct. That assumption fails in a specific,
recurring way, and no rule above catches it.

**The shape of the defect: real author, real venue, resolving URL, invented
title.** Every individual guard is satisfied. A link checker sees 200. A tier
or venue check sees a respectable journal. The anchor check sees a defined id.
None of them sees the *pairing* — that the thing at the end of the link is not
the thing the entry describes.

This is the characteristic failure of documentation drafted with a language
model, and of citation lists carried forward without anyone re-opening the
sources. It does not announce itself: a fabricated citation looks more
plausible than a real one, because nothing about it is inconvenient.

- **Verify against the source, never against your own entry.** The entry is the
  thing under test. Re-reading it tells you only that it is internally
  consistent, which fabricated citations reliably are.
- **A link to the work is not a link *about* the work.** A review, a catalogue
  record, a "cited by" page, a bookseller listing and an abstract are each a
  different artefact from the work itself. Cite the work; if only a surrogate is
  reachable, say which one the link goes to.
- **Confirm title, author and year, and enough of the subject to know it can
  support the claim.** Subject is the half that gets skipped and the half that
  catches the worst errors — a source can be real, obtainable, correctly titled,
  and about a different discipline than the claim citing it.
- **Plausibility is not verification.** "This looks like a real paper" is the
  condition the defect is designed to produce, not evidence against it.
- **"Unverified" is a legitimate recorded state.** It is cheaper than a wrong
  "verified" and far cheaper than discovering the error downstream. Record which
  entries nobody has opened, rather than letting silence imply they were checked.
- **Availability and accuracy are separate verdicts.** A source can be freely
  downloadable and still not be the work the citation names. Classifying one
  says nothing about the other.

**Automating this is mostly a trap.** Confirming a title exists means fetching,
and scholarly hosts routinely return 403 to anything that is not a browser — so
a hard gate on liveness or title-matching fails for reasons unrelated to the
citation, and a gate that cries wolf gets switched off. Prefer a scheduled
advisory report over a blocking check, and prefer a recorded human verdict over
either.

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

**What it does not verify**, and cannot cheaply: that the cited work exists,
that the entry's title and author match it, that the URL resolves, or that the
work is about what the citing claim needs. Those are the rules in *The citation
must name the work it points at*, and they are human verdicts. A green
`research-provenance` run means the citation graph is well-formed, not that the
citations are true.

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

*The citation must name the work it points at* was added later, from the same
project, after the defect it describes was found three times in one
bibliography. Each was a different shape of the same error, and each had passed
every mechanical check the project had:

- A reference printed a title that exists nowhere, over a real author, a real
  journal and a URL that resolved — to a different paper by that author.
- A reference to a 1959 book linked to a journal **review** of the book.
- A reference printed as being about West African drumming was a dissertation
  about African pianism. Freely downloadable, correctly attributed to its
  author, and one discipline away from the claim citing it.

The third is why *subject* is named explicitly in the rules: title-and-author
checking would have passed it.
