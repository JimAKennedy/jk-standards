---
name: escape-hatch-discipline
description: Design and use lint/check suppressions correctly — every escape hatch in-band, greppable, and carrying a written reason. Use when suppressing any finding (linter, sanitizer, review scanner, doc check) or when adding a new check that needs an exemption mechanism.
---

# Escape-hatch discipline

Every enforcement mechanism needs an escape hatch — a check with no exit
becomes a check people disable. The discipline is in how the hatch is built
and used. Three properties are non-negotiable:

1. **In-band.** The suppression lives next to the thing it suppresses — a
   trailing comment on the line, a marker on the doc line, a trailer in the
   commit that skips the doc update. Never in a separate registry that
   drifts from the code, except for a ratchet baseline (which is
   machine-maintained, not hand-edited).
2. **Greppable.** One fixed token per hatch (`RT-SAFE-OK`,
   `ownership-transfer`, `counts-ok`, `file-line-ok`, `nfr-review:skip`,
   `Docs-Not-Affected:`). `grep -rn <token>` must enumerate every active
   exemption in the repo — that listing *is* the audit report.
3. **Reasoned.** The hatch syntax carries a reason field, and the reason is
   written for a future reviewer: `<!-- counts-ok: worked example, not
   inventory -->`, `Docs-Not-Affected: comment-only change`. A hatch used
   without a real reason is a finding in itself.

## Using an escape hatch

- Suppress the *narrowest scope that works*: one line before one file, one
  file before one rule, one rule before the whole check.
- Write the reason as a claim someone could check: "VST3 factory transfers
  ownership to the host" — not "false positive".
- If you're suppressing the same rule for the same reason in many places,
  stop: either the rule needs tuning (fix the check, not the callsites) or
  the convention needs documenting once and suppressing globally with the
  reason recorded in config (one YAML comment beats twenty inline markers).
- Never suppress to make CI green under time pressure without writing the
  real state: an honest `[⚠ unverified]` beats a fabricated citation.

## Designing an escape hatch (when adding a new check)

- Pick one short, unique, greppable token. Prefix it if it might collide
  (`RT-SAFE-OK`, not `OK`).
- Support the narrowest scopes first: same-line marker, then
  preceding-line, then whole-file, then config-level skip — each with a
  reason slot.
- Make the check's error message *teach the hatch*: "either update X or add
  '<marker>: <reason>'". The error is the documentation people actually read.
- Exempt honestly-frozen content structurally (archived docs, dated review
  records) so people aren't trained to scatter markers on history.
- Count suppressions in the check's summary output. A rising count is
  signal; an invisible count is rot.

## Ratchet baselines

For adopting a check on a codebase with existing findings: record current
findings in a baseline file, fail only on *new* findings, and shrink the
baseline over time. Identity-match findings on stable keys (rule + file +
content hash), not line numbers, so unrelated edits don't resurrect known
findings. The baseline is machine-written; hand-editing it to hide a new
finding is the one forbidden move.
