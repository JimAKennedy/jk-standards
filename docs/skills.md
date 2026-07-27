---
class: gated
---

# Skills index

Status: current (2026-07-27)

Agent skills shipped by this repo, under `skills/<name>/SKILL.md`. They are
the authoring-time half of the discipline: the checks enforce the
conventions; the skills teach coding agents to write within them in the
first place.

| Skill | Teaches |
|---|---|
| architecture-definition | Authoring an ARCHITECTURE.md that conforms to the architecture standard: the four required sections (components, boundaries, data flow, invariants+enforcement) and the bidirectional rule that no invariant is listed without a named mechanism and no mechanism runs without a stated invariant, including turning a boundary into an enforceable `boundaries`-check rule |
| branch-discipline | Keeping milestone work landable: one branch per milestone, never stacking the next milestone on an unmerged one (the squash-merge conflict-replay rationale), and re-running `pre-commit run --all-files` after every rebase |
| ci-hygiene | Structuring CI for correctness and cost: layered cost-ordered gates, SHA-pinned actions on a weekly dependabot cadence, a single aggregation gate for branch protection, and artifact-retention conventions (the generic layer beneath sanitizer-ci-setup) |
| doc-anti-drift | Writing and maintaining docs under the anti-drift discipline: lifecycle classes, drift-map upkeep, dated status claims, symbol-based references, test-cited behavioral claims |
| escape-hatch-discipline | Designing and using suppressions: in-band, greppable, reasoned; narrowest-scope-first; ratchet baselines |
| realtime-audio-safety | Keeping the audio callback thread real-time-safe — no heap allocation, locks, blocking syscalls, exceptions, or unbounded container growth — and gating it with the greppable `check-realtime-safety.sh` scanner honoring an in-band `RT-SAFE-OK: <reason>` waiver with a live suppression count, with RealtimeSanitizer as the dynamic backstop |
| sanitizer-ci-setup | Layered quality gates for native projects: ASan/UBSan/TSan matrices, sanitizer-aware tests, fuzzer wiring, notification paths that can't be ignored |

## Consuming

Vendor skills into a project with a `skills-lock.json` entry pointing at
this repo, and install with the lock-file installer:

```json
{
  "version": 1,
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

```
jk-standards install-skills                      # → .agents/skills/
jk-standards install-skills --dest .claude/skills # Claude Code layout
```

The installer verifies each skill's SHA-256 against the lock file, so a
consuming repo pins skill content the same way it pins hook and workflow
versions. Vendored skill directories are gitignored in consumers;
project-authored skills stay tracked alongside them.
