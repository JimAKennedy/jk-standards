---
name: architecture-definition
description: Author and maintain an ARCHITECTURE.md that conforms to the jk-standards architecture standard — the four required sections (components, boundaries, data flow, invariants+enforcement) and the bidirectional rule that no invariant may be listed without a named mechanism and no mechanism should run without a stated invariant. Use when creating or editing an architecture document, adding an architectural invariant, or wiring a boundary into an enforceable check.
---

# Architecture definition discipline

An architecture document is a set of promises about how a system is shaped
and how it stays that way. Most such documents rot: they state invariants
nobody enforces, so the code drifts out from under the prose and the document
becomes a confident lie. This discipline is the authoring half of the
`docs/architecture-standard.md` standard — the standard says what a conforming
document must contain; this skill teaches an agent how to write one that stays
true.

## The governing rule

> No invariant without a mechanism; no mechanism without a stated invariant.

The rule is bidirectional, and both directions matter:

- **No invariant without a mechanism.** Never write an architectural invariant
  without naming the concrete thing that enforces it — a check name, a test, a
  CI job, a lint rule, or a type-system constraint. If you cannot name an
  enforcer, you have not stated an invariant; you have stated a hope. Move it
  to a non-normative "goals" note, or give it a mechanism before you list it.
- **No mechanism without a stated invariant.** When a repository runs a gate
  that protects its architecture, trace it back to an invariant the document
  states. A check that guards a property nobody wrote down teaches a reader
  *that* a gate exists but never *why*. Surface the property as an invariant so
  the reason is legible.

The forward direction kills prose that lies. The reverse direction kills
enforcement that hides. Write the document so it reads as a two-column
contract: each invariant on the left, the mechanism that makes it true on the
right.

## The four required sections

A conforming document has exactly these four `##` sections (any order,
additional sections allowed):

1. **Components** — a finite, enumerated list of the parts the system
   decomposes into, each with a one-line responsibility and a pointer to where
   it lives. "Everything under `src/`" is not a component set; name the parts.
2. **Boundaries** — which components may depend on which, and — the part that
   earns its keep — which must not. Phrase each boundary as a *forbidden
   reference* ("a check must not import the CLI"), because that shape maps
   directly onto a grep-level mechanism like the `boundaries` check.
3. **Data flow** — how information moves at runtime: what enters, what
   transforms it, what leaves, in which direction. A reader should be able to
   trace one representative request or job end to end from this section plus
   the component list. Call out cycles, fan-out, and shared mutable state
   explicitly — that is where data-flow assumptions break.
4. **Invariants and enforcement** — the properties that must hold, each bound
   to its mechanism per the governing rule. Use a table with an *Invariant*
   column and an *Enforced by* column; the pairing must be unambiguous.

## What counts as a mechanism

A mechanism is something a reader can run or point to and watch fail when the
invariant is violated:

- a named check (`jk-standards boundaries`, `jk-standards doc-taxonomy`)
- a specific test or suite (cite it the way the behavioral-claims check
  expects: `[verified: stem::test_name]`)
- a CI job by name
- a lint rule or a type-system constraint that makes the violation
  unexpressible

These are **not** mechanisms, and an *Enforced by* cell that names one does not
conform:

- "code review"
- "by convention"
- "developer discipline"

They are hopes wearing a mechanism's clothes. If the only thing standing
between the invariant and its violation is someone remembering, the invariant
is unenforced — say so honestly or build the gate.

## Turning a boundary into a check

The most common and most accidentally-violated invariant is a boundary. To
make one enforceable:

1. State it as a forbidden cross-directory reference in the Boundaries section.
2. Add it to the `boundaries` check config (forbidden `from` → `to` directory
   pairs) so `jk-standards boundaries` greps for the violation and reports
   `file:line`.
3. In the Invariants table, the *Enforced by* cell for that boundary names the
   `boundaries` check.
4. When a violation is genuinely intentional, suppress it in-band with a
   reasoned marker (`# boundary-ok: <reason>`), never by loosening the rule —
   see the [[escape-hatch-discipline]] skill.

## Conformance checklist

Before considering an architecture document done:

- [ ] `class: gated` front-matter (so doc-taxonomy governs it and status-prose
      lints it — see [[doc-anti-drift]]).
- [ ] A `Status:` line with a `(YYYY-MM-DD)` date anchor.
- [ ] All four required sections present.
- [ ] Every invariant names a concrete mechanism a reader can run.
- [ ] Every architecture-guarding gate the repo runs traces back to a listed
      invariant.
- [ ] Boundary invariants are wired into the `boundaries` check, not left as
      prose.

A document that passes this checklist gates itself with itself: the same
discipline it demands of the system it describes is applied to the document,
one level up.
