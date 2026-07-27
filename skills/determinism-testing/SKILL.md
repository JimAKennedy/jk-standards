---
name: determinism-testing
description: Make DSP output reproducible so golden tests can catch regressions — identical (patch, seed, transport) must render byte-identical output, oscillator/LFO phase must derive from absolute transport time rather than per-block accumulation, and a checked-in golden/snapshot suite gates every DSP change in CI. Use when writing or auditing determinism/golden tests for audio DSP, synths, or any render pipeline whose output must be reproducible run-to-run.
---

# Determinism testing

A golden test is only as trustworthy as the determinism underneath it. If the
same input can render two different buffers, a snapshot comparison is noise: it
fails on runs that changed nothing and passes on changes it should have caught.
So the first work of "testing determinism" is *making the code deterministic* —
then the golden suite becomes a cheap, precise regression net for every DSP
change you ship.

This skill covers three things, each in its own section: the determinism
contract you are testing against, the phase-from-absolute-time rule that is the
usual reason a synth violates it, and how the golden suite is wired into CI as
enforcement. The generic CI-structure discipline underneath the gate — layered
cost-ordered jobs, the single aggregation gate, artifact retention — lives in
the [[ci-hygiene]] skill; set that up first, then layer the golden job onto it.

## The determinism contract

The contract is one line:

> identical `(patch, seed, transport)` → byte-identical output.

Given the same patch (every parameter value), the same RNG seed, and the same
transport state (tempo, time signature, and the absolute play position / sample
count), rendering the plugin must produce the *same bytes* every time — on this
run, the next run, and a run six months from now on the same toolchain. That is
the property a golden test asserts, so every source of run-to-run variation is a
bug that must be closed before the suite is meaningful:

- **Seed the RNG explicitly; never from wall-clock time.** Any stochastic
  element — noise oscillators, randomised unison detune, sample-and-hold — draws
  from a generator seeded by a value that is part of the test input, not from
  `std::random_device` or the system clock. A clock-seeded generator is the most
  common determinism leak: it passes on your desk and can never be golden-tested.
- **Initialise every buffer and voice before it is read.** Uninitialised DSP
  state (a delay line, a filter's `z⁻¹`, a voice reused from the pool without a
  reset) reads back whatever the allocator last left there — different bytes per
  run. Zero or explicitly seed all state on `prepareToPlay` and on voice steal.
- **Fix voice render order.** If voices render on a thread pool and sum into a
  shared bus, floating-point addition is not associative — the summed result
  depends on completion order, which is nondeterministic. Sum voices in a fixed
  index order (or reduce with a deterministic tree), not in whatever order
  threads finish.
- **Pin the float environment.** `-ffast-math` lets the compiler reorder and
  contract float ops, so the "same" expression yields different bits across
  builds; denormal-flushing (FTZ/DAZ) that is set on one path and not another
  does the same at runtime. Decide the flush mode once, set it deterministically
  at the top of the callback, and keep fast-math off the DSP translation units
  you golden-test.

A note on scope: byte-identical is achievable *within a fixed toolchain and
platform*. Across platforms, `libm` transcendentals (`sin`, `exp`, `tanh`)
differ in their last bits, so a buffer golden'd on Linux will not match on macOS
bit-for-bit. Golden per platform, or compare with a tight ULP tolerance across
platforms — but hold the byte-identical line *within* a platform, because that
is where regressions actually hide.

## Derive phase from absolute transport time

The single most common way a synth breaks the contract is **accumulating
oscillator or LFO phase per block** instead of deriving it from absolute time.

Phase accumulation looks innocent:

```cpp
// WRONG: output depends on how the host split the buffer
for (int i = 0; i < numSamples; ++i) {
    out[i] = std::sin(phase);
    phase += increment;          // carried across processBlock calls
}
```

The host is free to call `processBlock` with any block size — 64 samples one
call, 512 the next, a ragged remainder at a loop boundary — and is free to split
the *same* musical region differently on the next run or in a different host. If
phase is a running accumulator, floating-point rounding of `phase += increment`
compounds differently for different block splits, so the same musical position
renders different bytes depending on segmentation. The contract is broken and
the golden test flaps.

Derive phase from the absolute transport position instead:

```cpp
// RIGHT: phase is a pure function of absolute time, independent of block size
const double t = transport.timeInSamples / sampleRate;      // absolute origin
for (int i = 0; i < numSamples; ++i) {
    const double phase = std::fmod((t + i / sampleRate) * freqHz, 1.0);
    out[i] = std::sin(phase * juce::MathConstants<double>::twoPi);
}
```

Now the output at a given transport position is the same regardless of how the
buffer was split to reach it. This buys three things at once: **buffer-size
independence** (64-sample and 512-sample renders of the same region match),
**seek/loop correctness** (jump the transport and the phase is already right —
no warm-up artefact), and **golden-testability** (the render is a pure function
of `(patch, seed, transport)`, exactly the contract). The rule generalises
beyond oscillators to any per-sample state that should be reproducible at a
transport position: ramp generators, tempo-synced LFOs, envelope stages keyed to
song position.

The honest exception is genuinely free-running, non-tempo-synced state (an
analogue-style drift LFO with no host-relative anchor). If it truly has no
absolute origin it can't be derived from one — but then it also can't be golden'd
against transport, so give it its own deterministic seed and test it in
isolation. Don't let "it's free-running" become the excuse that quietly exempts
a synced oscillator from the rule.

## Golden tests as CI enforcement

A golden (snapshot) test renders a fixed `(patch, seed, transport)` to a buffer
and compares it against a reference checked into the repo — either the raw
buffer or, more commonly, a hash of it plus a few spot-checked samples for
debuggability. Any DSP change that alters the output byte-for-byte trips the
test. That is the point: the golden suite makes *every* unintended change to the
render visible, including the ones no hand-written assertion anticipated.

Wiring it as enforcement:

- **Render through the real processing surface**, not a hand-rolled DSP call.
  Drive `processBlock` with the actual patch and transport so the test exercises
  parameter smoothing, voice allocation, and the block loop — the code paths
  that actually ship. A golden over a private helper misses integration-level
  regressions.
- **Cover the split-independence property explicitly.** Include at least one
  case that renders the same region twice — once in one big block, once in ragged
  small blocks — and asserts the two match. That case is what catches a
  phase-accumulation regression the instant it lands, before it can rot a golden.
- **Make the golden job a required gate,** not an advisory one. It runs on every
  PR as one of the [[ci-hygiene]] cost-ordered jobs and feeds the single
  aggregation gate, so a diverging render blocks the merge instead of scrolling
  past in logs.
- **Regenerating a golden is a reviewed, greppable act.** When a DSP change is
  *intended* to move the output, the golden must be regenerated — but a
  regenerate-on-red reflex silently launders real regressions. Gate it behind an
  explicit, greppable command (e.g. `UPDATE_GOLDENS=1`) so the regeneration shows
  up as a deliberate, diffable change to the reference files in the same PR, and
  a reviewer sees both the code change and the bytes it moved. Treat that switch
  as an escape hatch under [[escape-hatch-discipline]]: in-band, greppable, and
  never the default path.

The failure signature to design for: when a golden fails, the message should say
*which* case and *how far* it diverged (first differing sample index, expected
vs actual), not just "hash mismatch". A golden that can only say "different"
sends the next agent back to bisecting by hand; one that points at sample 4096
of the ragged-block case points straight at the phase bug.

## Completeness checklist

- [ ] The contract is stated and enforced: identical `(patch, seed, transport)` → byte-identical output within a fixed toolchain
- [ ] RNG is seeded from test input, never from wall-clock time or `random_device`
- [ ] All DSP state (buffers, filter memory, pooled voices) is initialised/reset before it is read
- [ ] Voice summation uses a fixed, deterministic order — no thread-completion-order dependence
- [ ] Float environment is pinned: fast-math off the golden'd TUs, denormal mode set deterministically
- [ ] Oscillator/LFO phase is derived from absolute transport time, not accumulated per block
- [ ] A block-split-independence case (one big block vs ragged small blocks) is asserted
- [ ] Golden tests render through the real `processBlock` surface, not a private helper
- [ ] The golden job is a required CI gate feeding the aggregation gate (per `ci-hygiene`), not advisory
- [ ] Golden regeneration is behind a greppable, reviewed switch (per `escape-hatch-discipline`), never a regenerate-on-red default
- [ ] Golden failures report the diverging case and first differing sample, not just a hash mismatch
- [ ] Cross-platform goldens are per-platform or ULP-toleranced; byte-identical is held within a platform
