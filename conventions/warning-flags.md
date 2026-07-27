---
class: gated
---

# Warning flags

Status: current (2026-07-27)

This is a *standard*, not a reference. A reference describes what this
toolkit's own surface does; a standard is a normative specification that a
consuming repository follows. It fixes the compiler-warning discipline a
consuming repository holds its C++ to: which diagnostics are enabled, that
they are fatal, that the set is identical across toolchains, and how a
warning is suppressed on the rare occasion suppression is warranted.

It is the third of the native-code siblings. The language-standard policy
governs the *revision* a repository targets; the MSVC-portability policy
governs the *toolchain*-specific hazards that survive an extensions-off
build; this standard governs the *diagnostics* — the warnings a conformant
build emits and whether the build tolerates them.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as in
RFC 2119.

## The governing rule

> Enable a strict warning set, make it fatal, and apply the same set on
> every toolchain — a warning that does not fail the build is a warning
> nobody reads.

A warning is the compiler reporting that source is suspect: a narrowing
conversion, an uninitialized read, a shadowed name, a switch that forgot a
case. The value of that report collapses the instant it is optional. A
non-fatal warning scrolls past in a build log, accumulates by the thousand,
and trains everyone who sees it to ignore the category — so the one warning
that marked a real defect is lost in the noise it was allowed to join. This
standard makes warnings load-bearing by requiring three things at once: that
a strict set is enabled, that the set is fatal, and that it is the same set
everywhere the repository builds.

## Warnings are errors

A consuming repository **MUST** compile its own C++ with warnings treated as
errors, so a new warning fails the build on the change that introduced it.
The mechanism is per toolchain — `-Werror` on Clang and GCC, `/WX` on
MSVC — and each toolchain the repository supports **MUST** carry it.

Warnings-as-errors is what makes the warning set a contract rather than a
suggestion. Without it the set decays: the count climbs, the log becomes
unreadable, and the discipline the other rules describe has no teeth. A
build that emits a warning and exits zero has, in practice, no warning set.

## A single shared warning set

The enabled diagnostics **MUST** be defined as one shared, named set that
every C++ target in the repository consumes, rather than being spelled out
target by target. A per-target hand-rolled flag list drifts: one target
gains a diagnostic another lacks, and "the warning set" stops being a single
thing anyone can point to.

The set **MUST** be strict. At minimum it enables the broad diagnostic
families each toolchain offers — `-Wall -Wextra` on Clang and GCC, `/W4` on
MSVC — and **SHOULD** extend them with the high-value diagnostics those
families omit (for example conversion, shadowing, and non-virtual-destructor
warnings) where the toolchain floor supports them. The exact roster is the
repository's to define; what this standard fixes is that the roster is
*one* roster, enabled everywhere, and strict enough that a real defect has a
diagnostic that can catch it.

## The set is identical across toolchains

The warning set **MUST** be equivalent across every toolchain the repository
supports. Compiler flag spellings differ — `-Wall` is not `/W4`, and a
Clang diagnostic may have no exact MSVC counterpart — so equivalence is of
*intent*, not of literal flags: each toolchain enables the strictest
reasonable expression of the same diagnostic goals, translated into that
toolchain's flag vocabulary in one place.

A repository **MUST NOT** run a strict set on one toolchain and a lax set on
another. A warning caught only under Clang, in a build matrix where the MSVC
job runs a weaker set, is a warning that ships broken to the Windows users
the MSVC job existed to protect. Combined with the MSVC-portability policy's
required conformant build, an equivalent warning set is what makes each
supported toolchain a real gate rather than a rubber stamp.

## Scope: first-party code, not dependencies

Warnings-as-errors applies to the code the repository *owns*. Third-party
code the repository merely builds — vendored sources, fetched dependencies,
generated files — **MUST NOT** be forced to satisfy the first-party warning
set, because the repository does not control that code and cannot fix a
warning inside it.

The boundary **MUST** be drawn by the build system, not by weakening the set:
external targets are built without the strict, fatal warning flags (or with
their headers treated as system headers so their diagnostics are demoted),
while first-party targets keep the full set. A repository **MUST NOT** lower
its own warning posture to accommodate a noisy dependency; it isolates the
dependency instead.

## Suppressions are local, justified, and rare

A genuine false positive — a diagnostic that is wrong for a specific,
understood reason — **MAY** be suppressed. Suppression is the escape hatch,
and this standard constrains it so the hatch does not become the door.

- A suppression **MUST** be as narrow as the toolchain allows: a single
  diagnostic, around a single expression or the smallest possible region
  (for example a scoped `#pragma` push/pop), never a translation unit and
  never the whole build.
- A suppression **MUST** carry a written justification at its site
  explaining why the diagnostic is a false positive here. An unexplained
  suppression is indistinguishable from hiding a real defect.
- A repository **MUST NOT** disable a diagnostic globally to silence one
  site, and **MUST NOT** relax warnings-as-errors as a substitute for a
  narrow, justified local suppression.

<!-- ===================================================================== -->
<!-- S05 PLACEHOLDER — do not remove or reorder. Slice S05 relocates       -->
<!-- cmake/jk_warnings.cmake into this repository and fills the section     -->
<!-- below with the concrete consumer instructions (FetchContent and       -->
<!-- copy-with-checksum vendoring) plus the accompanying                    -->
<!-- cmake/jk_warnings.cmake -> conventions/warning-flags.md drift-map      -->
<!-- entry. Keeping the heading carved here lets S05 land as a purely       -->
<!-- additive change rather than a restructure of this document.            -->
<!-- ===================================================================== -->

## Consuming the warning set

This standard defines the discipline; a consuming repository needs a concrete
warning set to adopt so it is not re-deriving the roster from scratch. This
toolkit ships one — a reusable CMake module that encodes the shared,
per-toolchain-translated set the rules above describe — and this section is
where its adoption instructions live: how a consuming repository pulls the
module in (via CMake `FetchContent`, or by vendoring a copy pinned to a
recorded checksum) and applies it to its first-party targets.

The shipped module and its adoption instructions are delivered as a distinct,
additive unit of work; this section is the fixed home that unit fills, so a
reader who lands here always finds the consumer guidance in one predictable
place rather than scattered across the build files.

## Conformance

A consuming repository conforms to this standard when all of the following
hold:

1. Every first-party C++ target compiles with warnings treated as errors
   (`-Werror` / `/WX`) on every supported toolchain, so a new warning fails
   the build.
2. The enabled diagnostics are defined as one shared, named, strict set that
   all first-party targets consume, rather than spelled out per target.
3. That set is equivalent in intent across every supported toolchain,
   translated into each toolchain's flag vocabulary in one place — no
   toolchain runs a weaker set than another.
4. Third-party code is isolated from the first-party set rather than the set
   being weakened to accommodate it.
5. Every suppression is narrow, carries a written justification at its site,
   and no diagnostic is disabled globally to silence a single location.

The first four conditions are mechanically checkable from the build
definition: a reviewer or a CI step can read the warning flags applied to
first-party versus external targets and assert them. The fifth is enforced by
review — a suppression without a justification, or one broader than its
single site, is a review defect against this standard — backed by the fact
that warnings-as-errors makes any un-suppressed regression a build failure on
the change that caused it.

## Why gated

This document is `class: gated`: it makes normative claims that other
repositories depend on, so it is held to the same dated-`Status` and
progress-free-prose discipline it asks of the documents it governs. A
warning-flags policy that drifts is worse than none, because readers keep
trusting that "the build is clean" means "the strict set passed everywhere"
long after a toolchain quietly dropped to a weaker set. Gating the standard
keeps the warning contract and the discipline in the same governed lifecycle
as the code that obeys it.
