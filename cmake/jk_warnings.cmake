# jk_warnings.cmake — the reference implementation of conventions/warning-flags.md
#
# This module is the shared, named warning set the standard describes: one
# roster, per-toolchain-translated, enabled on every first-party C++ target and
# made fatal. It is class:gated code — it is drift-mapped to
# conventions/warning-flags.md, and the two MUST evolve together.
#
# Public API
#   jk_target_warnings(<target>)        Apply the strict, fatal first-party set.
#   jk_suppress_sdk_warnings(<target>)  Isolate a third-party/SDK target from it.
#
# The set is equivalent in intent across toolchains (warning-flags.md
# "The set is identical across toolchains"): -Wall -Wextra + high-value
# extras on Clang/GCC, /W4 on MSVC, with warnings-as-errors (-Werror / /WX)
# on both. Spellings differ; the diagnostic goals do not.

include_guard(GLOBAL)

# --- The one shared roster --------------------------------------------------
#
# Defined once, here, rather than spelled out target by target
# (warning-flags.md "A single shared warning set"). The broad families are the
# floor; the extras are the high-value diagnostics those families omit that the
# standard names — conversion, shadowing, non-virtual-destructor.

set(JK_WARNINGS_CLANG_GCC
  -Wall
  -Wextra
  -Wpedantic
  -Wconversion            # narrowing / sign-changing implicit conversions
  -Wsign-conversion
  -Wshadow                # a declaration shadows an outer name
  -Wnon-virtual-dtor      # polymorphic base with a non-virtual destructor
  -Wold-style-cast
  -Wcast-align
  -Wunused
  -Woverloaded-virtual
  -Wdouble-promotion
  -Wformat=2
)

# MSVC's closest equivalent to the goals above. /W4 is the strict family floor;
# the explicit /w4xxxx promotions raise MSVC diagnostics that map to the
# Clang/GCC extras (e.g. C4242/C4244 ~ -Wconversion, C4263/C4265 ~
# -Wnon-virtual-dtor, C4456-C4459 ~ -Wshadow). /permissive- keeps the front end
# conformant so the set is meaningful (see conventions/msvc-portability.md).
set(JK_WARNINGS_MSVC
  /W4
  /permissive-
  /w44242 /w44254 /w44263 /w44265 /w44287
  /w44296 /w44311 /w44365 /w44388
  /w44456 /w44457 /w44458 /w44459
  /w44946
)

# --- jk_target_warnings -----------------------------------------------------
#
# Apply the strict, fatal first-party set to a target the repository OWNS.
# warnings-as-errors is on: -Werror on Clang/GCC, /WX on MSVC — a new warning
# fails the build on the change that introduced it.
#
# Scope handling: a normal target (executable / STATIC / SHARED / OBJECT lib)
# compiles its own sources, so the flags are PRIVATE — they govern this
# target's compilation and are NOT forced onto consumers. An INTERFACE_LIBRARY
# has no sources of its own to compile, so there is nothing to make fatal;
# forcing the set through its INTERFACE would push first-party warnings-as-
# errors onto every consumer, which the standard forbids. We therefore no-op on
# INTERFACE libraries and say so, rather than silently doing the wrong thing.
function(jk_target_warnings target)
  if(NOT TARGET ${target})
    message(FATAL_ERROR "jk_target_warnings: '${target}' is not a target")
  endif()

  get_target_property(_jk_type ${target} TYPE)
  if(_jk_type STREQUAL "INTERFACE_LIBRARY")
    message(STATUS
      "jk_target_warnings: '${target}' is an INTERFACE_LIBRARY (no first-party "
      "sources to compile); warning set not applied. Apply it to the concrete "
      "targets that consume this interface instead.")
    return()
  endif()

  target_compile_options(${target} PRIVATE
    $<$<CXX_COMPILER_ID:MSVC>:${JK_WARNINGS_MSVC};/WX>
    $<$<OR:$<CXX_COMPILER_ID:Clang>,$<CXX_COMPILER_ID:AppleClang>,$<CXX_COMPILER_ID:GNU>>:${JK_WARNINGS_CLANG_GCC};-Werror>
  )
endfunction()

# --- jk_suppress_sdk_warnings -----------------------------------------------
#
# Draw the first-party / third-party boundary in the BUILD SYSTEM
# (warning-flags.md "Scope: first-party code, not dependencies"): a dependency
# the repository merely builds MUST NOT be forced to satisfy the first-party
# set, because the repository cannot fix a warning inside it.
#
# This isolates such a target by (1) dropping warnings-as-errors and lowering it
# to the toolchain's own quiet default, so a noisy dependency does not fail the
# build, and (2) marking its interface include directories SYSTEM so the
# dependency's headers do not fire the first-party set when included downstream.
# The first-party posture is NOT lowered to accommodate the dependency — the
# dependency is isolated instead.
function(jk_suppress_sdk_warnings target)
  if(NOT TARGET ${target})
    message(FATAL_ERROR "jk_suppress_sdk_warnings: '${target}' is not a target")
  endif()

  get_target_property(_jk_type ${target} TYPE)

  # Demote this dependency's own compilation: no -Werror/-WX, quiet warning
  # level. INTERFACE libraries have no compilation of their own, so skip that.
  if(NOT _jk_type STREQUAL "INTERFACE_LIBRARY")
    target_compile_options(${target} PRIVATE
      $<$<CXX_COMPILER_ID:MSVC>:/W0;/WX->
      $<$<OR:$<CXX_COMPILER_ID:Clang>,$<CXX_COMPILER_ID:AppleClang>,$<CXX_COMPILER_ID:GNU>>:-w;-Wno-error>
    )
  endif()

  # Treat the dependency's exported headers as system headers so their
  # diagnostics are demoted when first-party code includes them.
  get_target_property(_jk_inc ${target} INTERFACE_INCLUDE_DIRECTORIES)
  if(_jk_inc)
    set_target_properties(${target} PROPERTIES
      INTERFACE_SYSTEM_INCLUDE_DIRECTORIES "${_jk_inc}")
  endif()
endfunction()
