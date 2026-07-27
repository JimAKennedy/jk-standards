---
name: realtime-audio-safety
description: Keep the audio callback thread real-time-safe — no heap allocation, locks, blocking syscalls, exceptions, or unbounded container growth — and gate it with a greppable check honoring an RT-SAFE-OK waiver. Use when writing or reviewing audio-callback / DSP render code, or wiring an RT-safety check into CI for a C/C++ audio project.
---

# Real-time audio-thread safety

The audio callback runs under a hard deadline: it must fill a block of samples
before the driver's buffer underruns, and it hands control to no code with
unbounded latency. A single heap allocation, mutex acquisition, blocking
syscall, thrown exception, or unbounded container growth on that thread can
stall past the deadline and produce an audible glitch. The rule is absolute
because the failure is: "usually fast" is not real-time. Everything the callback
touches must be pre-allocated, lock-free, and bounded before the first sample.

## What is forbidden on the audio thread

These are the forms `check-realtime-safety.sh` flags, and the reasons they're
banned:

- **Heap alloc/free** — `malloc`/`calloc`/`realloc`/`free`, `new`/`delete`. The
  allocator can take a lock or a syscall under contention; latency is
  unbounded. Pre-allocate in `prepareToPlay` (or your engine's equivalent) and
  reuse.
- **Locks** — `std::mutex`, `lock_guard`/`unique_lock`/`scoped_lock`, `.lock()`.
  A priority inversion against a lower-priority thread holding the lock will
  miss the deadline. Hand data across the boundary with a lock-free
  SPSC queue or an atomic double-buffer swap instead.
- **Blocking I/O / syscalls** — `printf`/`fprintf`/`fopen`/`fwrite`/`fread`,
  `sleep`/`usleep`/`nanosleep`, stream I/O (`std::cout`/`std::cerr`). File and
  console I/O blocks; there is no bounded-latency logging on the audio thread.
  Push events to a lock-free ring and drain them on a non-audio thread.
- **Exceptions** — `throw`. Unwinding cost is unbounded and allocator-backed.
  Return error codes or clamp; never throw from render.
- **Unbounded container growth** — `push_back`/`emplace_back`/`resize` on a
  `std::vector` and friends. These reallocate. `reserve()` to the max block
  ahead of time and treat the container as fixed-capacity in the callback.

This is a **line-level textual gate**, not call-graph analysis: it flags the
forbidden forms visible on a line and nothing subtler — a helper that allocates
behind a clean call site is invisible to it. That is enough to keep an honest
audio thread honest and cheap enough to run on every commit. It is a first-pass
filter, not a proof.

## The check recipe

`check-realtime-safety.sh` ships in this skill directory. Point it at the
files or directories that contain audio-thread code:

```sh
# One file, or recurse a DSP directory (globs *.cpp/*.cc/*.cxx/*.h/*.hpp/*.hh):
bash check-realtime-safety.sh engine/src/voice.cpp
bash check-realtime-safety.sh engine/src/dsp/
```

Exit codes follow the house check contract: `0` clean, `1` one or more unwaived
violations, `2` usage error. Every run ends with a summary line —

```
realtime-safety: 3 file(s), 0 violation(s), 2 suppression(s) via RT-SAFE-OK
```

— so the live suppression count is visible in CI logs even when the run is
green. A rising count is the signal that the escape hatch is being overused;
an invisible count is rot. Scope the check narrowly: run it against the render
path, not the whole tree, so message-thread setup code (which legitimately
allocates and locks) doesn't drown the signal.

## The RT-SAFE-OK escape hatch

Some forbidden forms are genuinely safe in context — a container the host
pre-sizes, a `delete` that only runs on the teardown path the render function
shares. Waive those in-band with an `RT-SAFE-OK: <reason>` marker after any
comment opener (`//`, `/*`, `#`), on the offending line or the line immediately
above it:

```cpp
hostBuffer->push_back(out[0]);  // RT-SAFE-OK: host pre-reserves to maxBlock
// RT-SAFE-OK: freed on the message thread during voice teardown
delete hostBuffer;
```

The reason is written for a future reviewer and must be a claim someone could
check ("VST3 host owns this buffer; freed off-thread") — never "false
positive". `grep -rn RT-SAFE-OK` enumerates every live exemption in the repo,
and that listing *is* the audit report. If you find yourself waiving the same
rule for the same reason in many places, stop and either tune the check or
lift the pattern into a lock-free helper — see the `escape-hatch-discipline`
skill for the full doctrine (narrowest scope, reasoned, greppable, counted).

## Static gate vs. dynamic backstop

This grep is the *static* first pass. The *authoritative* check is dynamic:
RealtimeSanitizer (rtsan) with functions annotated `[[clang::nonblocking]]`,
which instruments the actual runtime and catches the allocating helper the grep
can't see. Treat them as complements — the grep runs on every commit and blocks
the obvious regressions cheaply; rtsan runs in the sanitizer matrix and proves
the render path is clean end to end. Wire rtsan in per the `sanitizer-ci-setup`
skill, which owns the ASan/UBSan/TSan/rtsan matrix and its notification path.

## Consumers

The reusable audio engine (**poly**, `engine/`) exposes a per-block
`renderBlock` entry point called straight from the driver callback; the
**drumcore** app layer drives it with host-owned buffers. Both are hard-real-time
render paths this check guards. Concrete in-repo evidence lives in the test
fixtures:

- `tests/fixtures/realtime-audio-safety/violating_callback.cpp:18` — the poly
  engine's `Voice::renderBlock` with unwaived heap alloc, a mutex, a `printf`,
  and a `push_back` on the audio thread; the check flags each and exits 1.
- `tests/fixtures/realtime-audio-safety/waived_callback.cpp:17` — the drumcore
  `Sampler::renderBlock` where each crossing carries a reasoned `RT-SAFE-OK`;
  the check exits 0 and reports the suppression count.

`tests/test_realtime_safety.py` drives the shipped script via subprocess against
both fixtures, asserting the exit codes and the suppression-count output.

## Completeness checklist

- [ ] No heap alloc/free, locks, blocking I/O, exceptions, or unbounded container growth in any audio-callback / render path
- [ ] All buffers, containers, and voices pre-allocated before the first sample (`prepareToPlay` or equivalent); containers `reserve()`d to max block
- [ ] Cross-thread data handoff is lock-free (SPSC queue / atomic swap), never a mutex on the audio thread
- [ ] Logging/telemetry from render pushed to a ring buffer drained off-thread — no `printf`/stream I/O in the callback
- [ ] `check-realtime-safety.sh` wired into CI against the render path, exit-1 blocking
- [ ] Every `RT-SAFE-OK` marker carries a checkable reason; `grep -rn RT-SAFE-OK` audited and the suppression count not creeping up
- [ ] RealtimeSanitizer (`[[clang::nonblocking]]`) runs as the dynamic backstop per the `sanitizer-ci-setup` skill
