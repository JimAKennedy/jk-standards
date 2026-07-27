---
class: gated
---

# Architecture standard

Status: current (2026-07-27)

This is a *standard*, not a reference. A reference describes what this
toolkit's own surface does; a standard is a normative specification that a
consuming repository follows. It defines what an architecture document
(conventionally `ARCHITECTURE.md` at the repository root) must contain and
the one rule that keeps such a document honest as the code moves underneath
it.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as in
RFC 2119.

## The governing rule

> No invariant without a mechanism; no mechanism without a stated invariant.

An architecture document is a set of promises about how a system is shaped
and how it stays that way. A promise nobody enforces is decoration: it drifts
the moment someone edits code without reading prose. This standard makes the
two directions of that rule binding:

- **No invariant without a mechanism.** Every architectural invariant an
  architecture document states **MUST** name the concrete mechanism that
  enforces it — a named check, a test, a CI job, a lint rule, or a type-system
  constraint. An invariant with no named enforcer is aspirational and **MUST
  NOT** be listed as an invariant; move it to a non-normative "goals" note or
  give it a mechanism.
- **No mechanism without a stated invariant.** Every enforcement mechanism a
  repository runs to protect its architecture **SHOULD** trace back to an
  invariant the architecture document states. A check that guards a property
  nobody wrote down is a property nobody can reason about; surface it as an
  invariant so a reader learns *why* the gate exists, not just *that* it does.

The rule is bidirectional on purpose. The forward direction kills prose that
lies; the reverse direction kills enforcement that hides. A conforming
document reads as a two-column contract: each invariant on the left, the
mechanism that makes it true on the right.

## Required sections

A conforming architecture document **MUST** contain the four sections below,
in any order, each with a level-two (`##`) heading. Additional sections
**MAY** appear. The four are the minimum a reader needs to understand a
system's shape and trust that the shape holds.

### Components

Name the parts the system decomposes into and give each a one-line
responsibility. A component is a unit a reader can reason about in isolation:
a module, a service, a package, a layer. This section **MUST** be a finite,
enumerated list — "everything under `src/`" is not a component set. Each
entry **SHOULD** point at where the component lives (a directory or package
name), so a reader can navigate from the map to the territory.

### Boundaries

State which components **MAY** depend on which, and — more importantly —
which **MUST NOT**. A boundary is a directed constraint between components:
the CLI may call the check registry, but a check must not reach back into the
CLI. This section is where the architecture earns its keep, because a boundary
is the most common architectural invariant and the easiest to violate by
accident. Each boundary **SHOULD** be phrased as a forbidden reference so it
maps cleanly onto a mechanism that greps for the violation.

### Data flow

Describe how information moves through the components at runtime: what enters,
what transforms it, what leaves, and in which direction. A reader **MUST** be
able to trace a representative request or job from entry to exit using only
this section and the component list. Cycles, fan-out, and shared mutable state
**SHOULD** be called out explicitly, because they are where data-flow
assumptions break.

### Invariants and enforcement

List the properties that **MUST** hold for the architecture to be sound, and
bind each to its mechanism per the governing rule. This section **MUST** be
structured so the invariant/mechanism pairing is unambiguous — a table with
an *Invariant* column and an *Enforced by* column is the recommended form.
Every row's *Enforced by* cell **MUST** name a mechanism that a reader can
run or point to: a check name, a test identifier, a CI job, or an equivalent
automated gate. A row whose enforcement reads "code review", "by convention",
or "developer discipline" does not satisfy the rule — those are not
mechanisms, they are hopes.

## Conformance

An architecture document conforms to this standard when all of the following
hold:

1. It declares `class: gated` front-matter, so the doc-taxonomy check governs
   it and the status-prose check lints it.
2. It carries a `Status:` line with a `(YYYY-MM-DD)` date anchor, so a stale
   document is visible as stale rather than silently trusted.
3. It contains the four required sections above.
4. Every invariant it lists names a concrete enforcement mechanism, and every
   such mechanism is one a reader can actually run or reference.

The first two conditions are mechanically enforced for any `class: gated`
doc by this toolkit's own doc-taxonomy and status-prose checks. The last two
are enforced by review against this standard and, where the invariants are
about source-tree references, by the boundaries check that turns a stated
boundary into a grep-level gate.

## Why gated

This document is itself `class: gated`: it makes normative claims that other
repositories depend on, so it is held to the same dated-Status and
progress-free-prose discipline it asks of the documents it governs. A standard
that drifts is worse than no standard, because readers still trust it. Gating
the standard is the toolkit gating itself with itself — the same principle the
governing rule states, applied one level up.
