---
class: gated
---

# C++ language standard

Status: current (2026-07-27)

This is a *standard*, not a reference. A reference describes what this
toolkit's own surface does; a standard is a normative specification that a
consuming repository follows. It fixes the ISO C++ language revision a
consuming repository targets, how that revision is selected so the choice is
uniform and enforceable, and the discipline that keeps a codebase from
silently depending on a newer revision than it declares.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as in
RFC 2119.

## The governing rule

> Declare one language revision, select it per target, and forbid the
> extensions that let a build outrun the declaration.

A language-standard choice is a promise: every translation unit compiles
under the same revision, and no source relies on a feature the revision does
not guarantee. That promise breaks the moment a build permits compiler
extensions or lets the standard float per translation unit, because then the
code that compiles on one toolchain quietly stops being portable to another.
This standard makes the promise binding in three directions: a single
declared revision, a per-target selection mechanism, and an extensions-off
posture that turns "compiles here" into "conforms everywhere".

## The declared revision

A consuming repository **MUST** target **ISO C++20** as its language
revision. C++20 is the floor and the ceiling: source **MUST NOT** rely on a
feature standardized only in a later revision, and a consuming repository
**MUST NOT** compile any target under an earlier revision such that two
targets in the same repository disagree on the revision they accept.

A consuming repository **MAY** raise its declared revision to a later ISO
standard, but only by changing the declaration in one place (see *Selection*)
so every target moves together. Raising the revision for a single target
while the rest of the repository stays behind is forbidden, because it
reintroduces the per-target disagreement this standard exists to prevent.

The revision is a property of the repository, not of a file. A source file
**MUST NOT** carry a per-file pragma, comment directive, or build-system
override that selects a different revision than the repository declares.

## Selection

The declared revision **MUST** be selected per target through the build
system's standard-selection mechanism, not through a raw `-std=` flag spliced
into compile options. For a CMake consuming repository this means each target
sets its standard through `target_compile_features` (for example
`target_compile_features(<target> PUBLIC cxx_std_20)`) or through the
`CXX_STANDARD` target property, and never by appending `-std=c++20` to
`target_compile_options` or `CMAKE_CXX_FLAGS`.

Two properties **MUST** accompany the selection:

- **`CXX_STANDARD_REQUIRED` is on.** The declared revision is a requirement,
  not a preference. A build **MUST** fail — rather than silently fall back to
  an older revision — when the active compiler cannot provide the declared
  standard.
- **`CXX_EXTENSIONS` is off.** Targets **MUST** compile against the ISO
  dialect (for example `-std=c++20`), never a vendor extension dialect (for
  example `-std=gnu++20` or `/std:c++20` paired with Microsoft extensions
  left enabled). Extensions-on is the single most common way a codebase
  accumulates non-portable source without any diagnostic firing.

Selecting the revision globally (a repository-wide `CMAKE_CXX_STANDARD`
without per-target features) is discouraged: it works until a dependency is
added as a subdirectory and inherits a standard it did not ask for. Per-target
selection **SHOULD** be preferred so the language contract travels with the
target that owns it.

## Feature discipline

Targeting a revision is necessary but not sufficient; a consuming repository
**MUST** also constrain which features of that revision it uses to the subset
the supported toolchain floor actually implements.

- A consuming repository **MUST** state its supported toolchain floor — the
  oldest version of each compiler it commits to build under — and source
  **MUST NOT** use a C++20 feature that any compiler at that floor does not
  implement. A feature that is standardized but unimplemented on a supported
  compiler is not available to the repository, regardless of what the revision
  permits.
- Compiler-specific extensions, intrinsics, and non-standard built-ins
  **MUST NOT** appear in portable source outside a mechanism that isolates
  them behind a capability check or a documented per-platform boundary. This
  standard governs the *language* dialect; the sibling MSVC-portability
  standard governs the *toolchain*-specific hazards that survive an
  extensions-off build.
- Deprecated language and library features the declared revision removes or
  marks deprecated **SHOULD NOT** be introduced in new source, even where a
  transitional compiler still accepts them.

## Conformance

A consuming repository conforms to this standard when all of the following
hold:

1. Every C++ target declares the same ISO C++ revision, and that revision is
   C++20 or a later revision selected uniformly across all targets.
2. The revision is selected through the build system's standard-selection
   mechanism per target, never through a raw `-std=` compile flag.
3. `CXX_STANDARD_REQUIRED` is on and `CXX_EXTENSIONS` is off, so a build
   fails rather than downgrading and compiles the ISO dialect rather than a
   vendor extension dialect.
4. No source uses a feature the declared revision omits, and no source uses a
   C++20 feature unimplemented at the repository's stated toolchain floor.

The first three conditions are mechanically checkable from the build
definition — a reviewer, a lint rule, or a CI step can read the target
properties and assert them. The fourth is enforced by building the repository
under every compiler at its stated floor: a feature that is unavailable on a
supported toolchain surfaces as a build failure on that toolchain, which is
exactly the signal a language-standard policy is meant to produce.

## Why gated

This document is `class: gated`: it makes normative claims that other
repositories depend on, so it is held to the same dated-`Status` and
progress-free-prose discipline it asks of the documents it governs. A
language-standard policy that drifts is worse than none, because readers keep
compiling against a revision the prose no longer describes. Gating the
standard keeps the declaration and the discipline in the same governed
lifecycle as the code that obeys it.
