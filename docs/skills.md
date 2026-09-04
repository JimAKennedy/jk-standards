---
class: gated
---

# Skills index

Status: current (2026-09-03)

Agent skills shipped by this repo, under `skills/<name>/SKILL.md`. They are
the authoring-time half of the discipline: the checks enforce the
conventions; the skills teach coding agents to write within them in the
first place.

| Skill | Teaches |
|---|---|
| architecture-definition | Authoring an ARCHITECTURE.md that conforms to the architecture standard: the four required sections (components, boundaries, data flow, invariants+enforcement) and the bidirectional rule that no invariant is listed without a named mechanism and no mechanism runs without a stated invariant, including turning a boundary into an enforceable `boundaries`-check rule |
| branch-discipline | Keeping milestone work landable: one branch per milestone, never stacking the next milestone on an unmerged one (the squash-merge conflict-replay rationale), and re-running `pre-commit run --all-files` after every rebase |
| ci-hygiene | Structuring CI for correctness and cost: layered cost-ordered gates, SHA-pinned actions on a weekly dependabot cadence, a single aggregation gate for branch protection, and artifact-retention conventions (the generic layer beneath sanitizer-ci-setup) |
| determinism-testing | Making DSP output reproducible so golden tests catch regressions: the identical `(patch, seed, transport)` → byte-identical output contract, deriving oscillator/LFO phase from absolute transport time rather than per-block accumulation, and wiring a checked-in golden/snapshot suite into CI as a required gate |
| doc-anti-drift | Writing and maintaining docs under the anti-drift discipline: lifecycle classes, drift-map upkeep, dated status claims, symbol-based references, test-cited behavioral claims |
| escape-hatch-discipline | Designing and using suppressions: in-band, greppable, reasoned; narrowest-scope-first; ratchet baselines |
| research-provenance | The provenance discipline for documentation that summarises external research or scholarship: every substantive claim is a sourced claim (inline citation), a practical distillation (flagged in the page's Attribution note), or a project-specific value (declared as the project's own); bibliography entries carry stable HTML anchors, terminology credits its coiner, organising frameworks are declared as arrangement rather than discovery, and cultural material claims fidelity to cited scholarship only — mechanically gated by the `research-provenance` check |
| realtime-audio-safety | Keeping the audio callback thread real-time-safe — no heap allocation, locks, blocking syscalls, exceptions, or unbounded container growth — and gating it with the greppable `check-realtime-safety.sh` scanner honoring an in-band `RT-SAFE-OK: <reason>` waiver with a live suppression count, with RealtimeSanitizer as the dynamic backstop |
| sanitizer-ci-setup | Layered quality gates for native projects: ASan/UBSan/TSan matrices, sanitizer-aware tests, fuzzer wiring, notification paths that can't be ignored |
| sdlc-retro | Reconstructing and periodically measuring a portfolio's AI-assisted workflow evolution from evidence rather than memory: the five evidence classes (trailer variants, marker first-appearances, weekly volumes with a guardrail-vs-product churn split, ephemeral environment state, retention-limited weekly token usage), the append-only snapshot ledger its bundled `collect.py` maintains incrementally, and the interpretation order (era check, guardrail check, throughput/survival, recollection vs evidence), and the standing-report contract: each run updates one stable-location report in place per the ledger README's report brief (audience, framing rules, exclusions, baseline constants), answering what happened, what the major moves were, and what the quantified benefits were |
| versioned-state-serialization | Serializing persistent state so old data still loads after the format changes: write a version tag first, branch on it when reading, and never reinterpret unversioned bytes, illustrated with JUCE/VST3 plugin preset/patch state and the "preset compatibility time bomb" anti-pattern |

## Consuming

Vendor skills into a project with a `skills-lock.json` entry pointing at
this repo, and install with the lock-file installer:

```json
{
  "version": 1,
  "jkStandardsVersion": "<the release this lock is pinned against>",
  "skills": {
    "doc-anti-drift": {
      "source": "JimAKennedy/jk-standards",
      "sourceType": "github",
      "skillPath": "skills/doc-anti-drift/SKILL.md",
      "computedHash": "<sha256 of SKILL.md>"
    }
  }
}
```

`jkStandardsVersion` is load-bearing, not a label: the installer fetches the
tag matching it, so the lock names both *which* content it wants and *what
that content hashes to*. Omit it and the installer falls back to the default
branch, where the next upstream commit invalidates every hash in the file at
once. `install-skills --update-lock` writes the field for you.

```
jk-standards install-skills                      # → .agents/skills/
jk-standards install-skills --dest .claude/skills # Claude Code layout
```

The installer verifies each skill's SHA-256 against the lock file, so a
consuming repo pins skill content the same way it pins hook and workflow
versions. Vendored skill directories are gitignored in consumers;
project-authored skills stay tracked alongside them.
