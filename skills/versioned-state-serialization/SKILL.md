---
name: versioned-state-serialization
description: Serialize persistent state so old data still loads after the format changes — write a version tag first, branch on it when reading, and never reinterpret unversioned bytes. Use when designing or changing any serialized-state format that outlives its writer — plugin preset/patch state, save files, on-disk caches, or wire formats a future build must still read.
---

# Versioned state serialization

Any state you persist will be read back by a *different* build of your code
than the one that wrote it. A user saves a preset today; they load it in the
version you ship next year. The format you serialize is a contract with every
future version of yourself, and the only way to keep that contract cheaply is
to make the version explicit in the bytes.

The discipline is three rules, each covered in its own section below:

1. **Write the version first.** The first field you serialize is a format
   version number — before any payload.
2. **Branch on the version when reading.** Read the version, then dispatch to
   the loader for that version. New code reads old data by keeping the old
   read path alive.
3. **Never reinterpret unversioned bytes.** State written before you added a
   version tag is legacy; detect it and route it to a legacy path, don't
   guess.

## Write the version first

The first thing written into any serialized blob is a format version — a
plain integer you bump by hand whenever the layout changes. It goes *before*
the payload so the reader learns how to interpret the rest before it consumes
any of it.

In poly (a JUCE/VST3 synth), plugin state is flattened through
`AudioProcessor::getStateInformation`. The version leads:

```cpp
void PolyProcessor::getStateInformation(juce::MemoryBlock& dest)
{
    juce::ValueTree state{"PolyState"};
    state.setProperty("stateVersion", kCurrentStateVersion, nullptr); // 3
    state.setProperty("cutoff",   params.cutoff.get(),   nullptr);
    state.setProperty("resonance", params.resonance.get(), nullptr);
    // ... remaining params ...

    juce::MemoryOutputStream stream{dest, false};
    state.writeToStream(stream);
}
```

`kCurrentStateVersion` is a single named constant. When you change what gets
written — rename a param, split one control into two, change units — you bump
that constant and add a branch to the reader (next section). The constant and
the reader's `switch` are the two ends of the contract; keep them in the same
file so a future edit can't move one without seeing the other.

Two rules make the version field trustworthy:

- **Bump on every layout change, never reuse a number.** A version number
  that maps to two different layouts is worse than no version at all — the
  reader can't disambiguate. If you shipped a build, its layout owns its
  number forever.
- **The version is data, not a build flag.** Don't derive "what version is
  this" from the plugin's semantic version or a compile-time macro. The blob
  carries its own version so a binary built from any source tree can read it.

## Branch on the version when reading

The reader is the mirror of the writer: read the version field first, then
dispatch to the loader that understands *that* layout. New code reads old data
because the old read paths stay alive — you never delete a branch for a version
that a user's preset might still be sitting in.

In poly, state comes back through `AudioProcessor::setStateInformation`. The
version leads the dispatch:

```cpp
void PolyProcessor::setStateInformation(const void* data, int size)
{
    auto state = juce::ValueTree::readFromData(data, (size_t) size);
    if (!state.isValid())
        return; // not our format; keep current params

    const int version = state.getProperty("stateVersion", 0); // 0 == unversioned

    switch (version)
    {
        case 3: loadV3(state); break;
        case 2: loadV3(migrateV2toV3(state)); break;
        case 1: loadV3(migrateV1toV3(state)); break;
        default: loadLegacy(state); break; // version 0: see next section
    }
}
```

Two properties make this survive a decade of format churn:

- **Migrate forward through a chain, load once.** Each `migrateVNtoVN+1` is a
  small, pure transform: a v1 preset stored `cutoff` in raw Hz; v2 stored it
  normalised 0–1; the migration rescales one field and returns a v2 tree. Chain
  the migrations (`v1 -> v2 -> v3`) so the *loader* only ever has to understand
  the current layout. You write one new migration per bump, not a fresh full
  loader.
- **A missing or newer version is a decision, not a crash.** An unknown *lower*
  version routes to a legacy path (below). An unknown *higher* version — a
  preset saved by a build newer than the one reading it — should load what it
  can and drop what it can't, never abort. A user who round-trips a preset
  through an old build should not lose their patch.

The `switch` and `kCurrentStateVersion` live in the same file for a reason: a
future edit that bumps the constant is forced to look at the branch it must add.

## The preset compatibility time bomb

The **preset compatibility time bomb** is what you ship when you add a field to
the serialized layout *without* bumping the version. It passes every test on
your machine and detonates later, in a build you no longer control.

Concretely, in poly: v3 writes a new `subOscMix` param but the author leaves
`kCurrentStateVersion` at 3 instead of moving to 4. Now two different layouts
both claim to be "version 3":

- The **old build in the field** loads a new v3 preset, sees `stateVersion == 3`,
  runs `loadV3` — the loader that predates `subOscMix` — and silently ignores
  the field. The user's sub-oscillator setting is gone with no error.
- Worse, if the new field was inserted *before* an existing one in a
  position-dependent format, `loadV3` reads every subsequent field at the wrong
  offset. The preset doesn't fail to load; it loads *wrong* — a filter sweep
  becomes an LFO rate. The corruption is silent and looks like a synth bug, not
  a serialization bug, so it costs days to trace.

The bomb is armed at write time and goes off at read time in a different binary,
which is exactly why it evades local testing: the writer and the mis-reader are
never the same process on your desk. The defusal is the discipline in this
skill — **every layout change bumps the version and adds a read branch**, with
no exceptions. If you genuinely must accept a preset from a version you can't
fully migrate, do it as a named, greppable, reasoned exemption rather than a
silent skip; see [[escape-hatch-discipline]] for the doctrine.

The unversioned case (`stateVersion == 0`) is the original bomb: state written
before you ever added a version tag. Detect it explicitly — a missing property
reads as `0` above — and route it to `loadLegacy`, which knows the one
historical shape those bytes can have. Never reinterpret unversioned bytes as if
they were your current layout; if you can't recognise them, restore defaults
rather than load garbage.

## Completeness checklist

- [ ] The first field serialized is a format version — a plain integer, before any payload
- [ ] `kCurrentStateVersion` is a single named constant, bumped on every layout change, never reused for two layouts
- [ ] The reader reads the version first and dispatches (`switch`) to a per-version loader; the constant and the switch live in the same file
- [ ] Every shipped version keeps its read path alive; format changes add a migration + branch rather than editing an existing loader in place
- [ ] Migrations chain forward (`vN -> vN+1`) so only the current-layout loader is fully maintained
- [ ] An unknown *higher* version loads what it can and never aborts; an unknown *lower* / missing version (`0`) routes to an explicit legacy path
- [ ] No field is added to the layout without bumping the version — the "preset compatibility time bomb" is closed by construction
- [ ] Unversioned bytes are detected and routed to a legacy loader or defaults, never reinterpreted as the current layout
