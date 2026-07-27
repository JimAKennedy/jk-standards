#!/usr/bin/env bash
# check-realtime-safety.sh — a grep-level gate for real-time audio-thread safety.
#
# The audio callback thread runs under a hard deadline: it must produce a block
# of samples before the driver's buffer underruns, and it cannot afford to
# block, wait, or hand control to code with unbounded latency. A single
# heap allocation, mutex acquisition, syscall, thrown exception, or unbounded
# container growth on that thread can cause an audible glitch. These operations
# are almost never legitimate inside an audio callback, so a cheap textual grep
# for their call forms is a high-signal first-pass gate — the static complement
# to a dynamic tool like RealtimeSanitizer / [[clang::nonblocking]].
#
# This is a LINE-LEVEL TEXTUAL gate, not a call-graph analysis: it flags the
# forbidden forms you can see on a line and nothing subtler (a helper that
# allocates is invisible to it). That is enough to keep an honest audio thread
# honest and cheap enough to run on every commit. Treat rtsan as the
# authoritative dynamic backstop.
#
# Escape hatch: an `RT-SAFE-OK: <reason>` marker after any language-appropriate
# comment opener (`//`, `/*`, `#`), on the offending line or the line
# immediately above it, suppresses the finding. The reason is written for a
# future reviewer ("VST3 host owns this buffer; freed off-thread"), not "false
# positive". The summary always reports how many suppressions are live, so
# rising escape-hatch usage is visible in CI logs rather than silent.
#
# Usage:   check-realtime-safety.sh <file-or-dir> [<file-or-dir> ...]
# Exit:    0 = clean, 1 = one or more unwaived violations, 2 = usage error.

set -uo pipefail

if [[ $# -eq 0 ]]; then
  echo "usage: $(basename "$0") <file-or-dir> [<file-or-dir> ...]" >&2
  exit 2
fi

# `RT-SAFE-OK` after any common comment opener. Requiring an opener keeps the
# marker from matching a forbidden pattern that literally contains the word.
MARKER_RE='(//|/\*|#|;|--|<!--)[[:space:]]*RT-SAFE-OK'

# Forbidden operation patterns: "<ERE>\t<human label>". Word-guarded with
# explicit character classes (portable across BSD and GNU regex — no \b) so a
# bare `new` fires but `renew`/`new_size` do not. Narrow and high-signal on
# purpose: a noisy grep trains users to scatter RT-SAFE-OK, which the
# escape-hatch discipline explicitly warns against. Broaden reluctantly.
G='(^|[^A-Za-z0-9_])'   # left word guard
PATTERNS=(
  "${G}(malloc|calloc|realloc|free)[[:space:]]*\("$'\t'"heap alloc/free"
  "${G}(new|delete)[[:space:]]"$'\t'"new/delete"
  "(std::mutex|${G}(lock_guard|unique_lock|scoped_lock)|\.lock[[:space:]]*\()"$'\t'"mutex/lock"
  "${G}(printf|fprintf|fopen|fwrite|fread|puts|sleep|usleep|nanosleep)[[:space:]]*\("$'\t'"blocking I/O / syscall"
  "(std::cout|std::cerr)"$'\t'"stream I/O"
  "${G}throw[[:space:]]"$'\t'"exception"
  "\.(push_back|emplace_back|resize)[[:space:]]*\("$'\t'"unbounded container growth"
)

# Collect the files to scan (recurse into directories for C/C++ sources).
files=()
for target in "$@"; do
  if [[ -d "$target" ]]; then
    while IFS= read -r f; do files+=("$f"); done < <(
      find "$target" -type f \
        \( -name '*.cpp' -o -name '*.cc' -o -name '*.cxx' \
           -o -name '*.h' -o -name '*.hpp' -o -name '*.hh' \) | sort
    )
  elif [[ -f "$target" ]]; then
    files+=("$target")
  else
    echo "check-realtime-safety: no such file or directory: $target" >&2
    exit 2
  fi
done

violations=0
suppressions=0

for file in "${files[@]}"; do
  lineno=0
  prev=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    lineno=$((lineno + 1))
    label=""
    for entry in "${PATTERNS[@]}"; do
      pat="${entry%%$'\t'*}"
      if [[ "$line" =~ $pat ]]; then
        label="${entry#*$'\t'}"
        break
      fi
    done
    if [[ -z "$label" ]]; then
      prev="$line"
      continue
    fi
    # A forbidden form was found. Is it waived on this line or the one above?
    if [[ "$line" =~ $MARKER_RE ]] || [[ "$prev" =~ $MARKER_RE ]]; then
      suppressions=$((suppressions + 1))
    else
      echo "${file}:${lineno}: RT-unsafe on audio thread: ${label} (or add '// RT-SAFE-OK: <reason>')" >&2
      violations=$((violations + 1))
    fi
    prev="$line"
  done < "$file"
done

# Always emit the suppression count so rising escape-hatch usage is visible in
# CI logs even when the run is otherwise green.
echo "realtime-safety: ${#files[@]} file(s), ${violations} violation(s), ${suppressions} suppression(s) via RT-SAFE-OK"

[[ "$violations" -eq 0 ]]
