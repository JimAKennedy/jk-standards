---
class: gated
---

# MSVC portability

Status: current (2026-07-27)

This is a *standard*, not a reference. A reference describes what this
toolkit's own surface does; a standard is a normative specification that a
consuming repository follows. It fixes the discipline that keeps C++ which
compiles cleanly under Clang and GCC from silently failing — or, worse,
silently miscompiling — under the Microsoft Visual C++ toolchain, so a
repository that claims to support Windows actually builds there.

It is the sibling of the C++ language-standard policy: that standard governs
the *language* revision a repository targets; this one governs the
*toolchain*-specific hazards that survive an extensions-off, standard-conformant
build and only surface when MSVC compiles the source.

The key words **MUST**, **MUST NOT**, **SHOULD**, and **MAY** are used as in
RFC 2119.

## The governing rule

> Compile on every toolchain you claim to support, in that toolchain's
> conformance mode — never to one compiler's tolerance.

Portability is a promise that the same source conforms everywhere, not a hope
that it happens to. That promise breaks in two ways under MSVC. The first is
silence: a repository that only ever builds under Clang or GCC accumulates
Windows-hostile source with no diagnostic firing, because the compiler that
would object never runs. The second is permissiveness: MSVC in its default,
non-conformant mode accepts constructs the ISO standard forbids, so even a
Windows build can pass while the source is not actually standard C++. This
standard makes the promise binding by requiring both that MSVC runs and that
it runs strictly.

## MSVC is a required build

A consuming repository that supports Windows **MUST** build under MSVC in
continuous integration, on every change, as a required check — not as an
occasional manual smoke test and not only when a Windows user reports a break.
A supported toolchain that never runs in CI is, in practice, an unsupported
toolchain: the source will drift away from it between the rare times someone
compiles it.

The MSVC build **MUST** cover the same targets, warning posture, and language
revision the other toolchains build, so a divergence surfaces as a build
failure on the change that introduced it rather than as an archaeological dig
weeks later. The supported MSVC floor — the oldest Visual Studio / MSVC
toolset version the repository commits to — **MUST** be stated alongside the
compiler floor the language-standard policy already requires, and the CI build
**MUST** exercise that floor.

## Conformance mode

MSVC **MUST** be invoked in its standards-conformant mode. This is the MSVC
analog of the extensions-off posture the language-standard policy requires of
every toolchain, and without it the required MSVC build proves far less than
it appears to.

- **`/permissive-` is on.** The conformant mode enables two-phase name lookup
  in templates, correct `typename`/`template` disambiguation, and rejection of
  the non-standard constructs MSVC's default mode silently accepts. Source that
  compiles only without `/permissive-` is not portable C++, and a build
  **MUST NOT** rely on the permissive default to accept it.
- **`/utf-8` is set.** The source and execution character sets **MUST** be
  UTF-8, so a string literal or an identifier means the same thing under MSVC
  as it does under a toolchain that already defaults to UTF-8. A repository
  **MUST NOT** depend on the host's active code page to interpret its own
  source.
- **The relevant `/Zc:` conformance switches are on.** Where the toolset's
  default for a `/Zc:` (conformance) switch is the non-conforming setting,
  the build **MUST** select the conforming one, so MSVC's interpretation of
  the standard matches the other toolchains' rather than a legacy default.

## Portable source rules

Beyond the compiler invocation, portable source **MUST** avoid the
Windows-and-MSVC-specific hazards that an extensions-off, conformant build does
not, on its own, catch:

- **Integer widths follow LLP64.** On 64-bit Windows `long` is 32 bits, unlike
  the LP64 model of 64-bit Linux and macOS where it is 64 bits. Source **MUST
  NOT** assume `long` can hold a pointer or a 64-bit value; it **MUST** use the
  fixed-width types (`<cstdint>`) or `std::size_t`/`std::ptrdiff_t` where an
  exact or pointer-sized width matters, and **MUST NOT** assume `sizeof(long)
  == sizeof(void*)`.
- **`<windows.h>` is quarantined.** Including `<windows.h>` defines the
  function-like macros `min` and `max` and a raft of other unqualified names
  that collide with standard-library and user identifiers. Source that must
  include it **MUST** define `NOMINMAX` (and `WIN32_LEAN_AND_MEAN` where it
  suffices) before the include, and **MUST NOT** let Windows headers leak into
  otherwise portable translation units.
- **No unguarded POSIX-only assumptions.** Portable source **MUST NOT** assume
  POSIX-only headers, functions, path separators, or filesystem semantics are
  present. Filesystem work **SHOULD** go through `<filesystem>` rather than
  POSIX calls, and any genuinely platform-specific system call **MUST** sit
  behind the isolation boundary below.
- **No reliance on non-standard extensions or built-ins.** Compiler-specific
  intrinsics, `__attribute__`/`__declspec` spellings, non-standard implicit
  conversions, and other vendor extensions **MUST NOT** appear in portable
  source except behind the isolation boundary below; the conformant-mode
  requirement makes many of these hard errors under MSVC, but not all.

## Isolating platform-specific code

Some code is irreducibly platform-specific: a Windows API call, a
symbol-export directive, an intrinsic with no portable equivalent. This
standard does not forbid such code — it forbids such code from contaminating
portable translation units.

Platform-specific constructs **MUST** be confined behind an explicit boundary:
a per-platform source file selected by the build system, an internal
abstraction with one implementation per platform, or a narrowly scoped
capability check — never an inline `#ifdef _MSC_VER` sprinkled through
otherwise portable logic. Symbol-visibility and export macros in particular
(`__declspec(dllexport)`/`dllimport` on MSVC versus
`__attribute__((visibility(...)))` on Clang and GCC) **MUST** be expressed
through a single per-target export macro, defined in one place, rather than
spelled out at each use site.

## Conformance

A consuming repository conforms to this standard when all of the following
hold:

1. It builds under MSVC in CI as a required check on every change, covering the
   same targets, language revision, and warning posture as its other
   toolchains, and it states and exercises a supported MSVC floor.
2. The MSVC build compiles in conformant mode: `/permissive-` on, `/utf-8`
   set, and the relevant `/Zc:` conformance switches selected wherever the
   toolset default is non-conforming.
3. No portable source assumes an LP64 integer model, lets `<windows.h>` leak
   its macros, or depends on POSIX-only facilities or vendor extensions outside
   the isolation boundary.
4. All irreducibly platform-specific code — system calls, export directives,
   intrinsics — sits behind an explicit per-platform boundary rather than
   inline conditionals in portable translation units.

The first two conditions are mechanically checkable from the CI configuration
and the MSVC compile flags: a reviewer or a CI step can read them and assert
them. The last two are enforced primarily by the required MSVC build itself —
a non-portable assumption surfaces as a compile error or warning on the MSVC
toolchain — and secondarily by review against this standard for the hazards
(such as macro leakage) that compile cleanly yet remain fragile.

## Why gated

This document is `class: gated`: it makes normative claims that other
repositories depend on, so it is held to the same dated-`Status` and
progress-free-prose discipline it asks of the documents it governs. A
portability policy that drifts is worse than none, because readers keep
trusting that "it builds on Clang" means "it builds on Windows" long after that
stopped being true. Gating the standard keeps the portability contract and the
discipline in the same governed lifecycle as the code that obeys it.
