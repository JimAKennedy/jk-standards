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
