---
name: doc-anti-drift
description: Write and maintain documentation under the jk-standards anti-drift discipline — doc lifecycle classes, drift maps, dated status claims, symbol-based references, test-cited behavioral claims. Use whenever creating or editing docs in a repo that has a jk-standards.yaml.
---

# Documentation anti-drift discipline

Documentation drifts because prose restates facts that live in code. This
discipline makes every restatement either machine-checked, machine-generated,
or explicitly declared exempt — so CI catches drift instead of readers.

## The doc taxonomy

Every doc carries YAML front-matter declaring its lifecycle class:

```yaml
---
class: gated        # or: generated | archived
---
```

- **generated** — produced by a build step. Never hand-edit; edit the source
  of truth and rerun the generator. CI diffs the doc against a fresh
  generator run.
- **gated** — living prose describing a real surface (an API, a workflow, an
  algorithm). Gated docs are what the rest of this discipline protects.
- **archived** — frozen historical record. Give it a reader-facing banner
  saying so. Archived docs are exempt from the other checks — the archive
  banner is what signals staleness honestly.

When you create a doc, pick the class deliberately. If you can't, the doc
probably mixes a living contract with historical narrative — split it.

## The drift map

A YAML map pairs source globs with the doc that describes them. When a
change touches mapped sources, the same PR must touch the doc — or a commit
must carry a `Docs-Not-Affected: <reason>` git trailer, which records the
bypass justification in history right next to the change.

Rules for maintaining the map:

- **Add a mapping** when a new gated doc lands that describes a specific
  source surface.
- **Never map** archived docs (frozen by definition), generated docs
  (freshness-checked instead), or speculative future pairs — only real,
  current, checkable claims.
- **Tune against false positives.** If a mapping fires on every routine PR
  (e.g. adding one test file to an existing suite), narrow its globs to the
  files that actually reshape the documented surface, and record the
  reasoning in the map entry's `reason` field.
- **Never write a throwaway trailer.** `Docs-Not-Affected: rename only, no
  contract change` is a real reason; `Docs-Not-Affected: n/a` defeats the
  audit trail.

## Writing rules for gated docs

1. **Date every status claim.** `Status: adopted (2026-07-25)` — never an
   undated `Status:` line. Undated status is a permanent lie in waiting.
2. **No progress-tracking prose.** "Not yet implemented", phase tracking,
   TODO counts — that state belongs in the changelog, issues, or generated
   dashboards. Gated docs describe current contracts and rationale.
3. **Cite symbols, never line numbers.** `renderRange()` or the
   `region:snippet-walk` marker, not `engine.cpp:429` — line numbers rot on
   the next edit. If a line ref is legitimately pinned (a commit-SHA
   permalink), mark the line `[file-line-ok]`.
4. **Never restate inventory counts.** "N presets", "N chapters" —
   interpolate from the generated source of truth (`{counts.x}`), or mark
   the line `<!-- counts-ok: reason -->` if the numeral is genuinely local
   (a worked example, a time signature).
5. **Mark behavioral claims.** Where prose asserts what the implementation
   does and being wrong would mislead, cite the test that proves it:
   `[verified: Suite.TestName]` (gtest), `[verified: stem/slug]` (js),
   `[verified: stem::test_name]` (pytest). CI fails on citations that don't
   resolve. If no test exists yet, write `[⚠ unverified]` — it's counted
   and surfaced, which is the honest state. Marking is opt-in and
   deliberate: mark claims where machine-verified truth matters, not every
   sentence with a verb.

## When checks fire on your change

- **doc-drift**: update the mapped doc in the same PR (preferred), or add a
  `Docs-Not-Affected:` trailer with a real reason.
- **generated-freshness**: run the generator command from the error message
  and commit the result. Never hand-edit the generated file.
- **behavioral-claims**: fix the citation, add the test, or downgrade to
  `[⚠ unverified]`.
- Choosing an exemption marker over a fix is sometimes right — but the
  marker's reason text is the audit trail, so write it for the reviewer.
