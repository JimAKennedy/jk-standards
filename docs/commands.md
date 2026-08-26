---
class: gated
---

# Workflow commands index

Status: current (2026-08-26)

Slash commands shipped by this repo, under `commands/<name>.md`, vendored into
a consuming project with `jk-standards install-commands`. They are the
procedural half of the discipline: the skills teach an agent how to write
within the conventions, the checks enforce them, and these commands drive the
delivery loop that produces the work in the first place.

Commands install to `.claude/commands/jk` by default. A project command in a
subdirectory is namespaced by it, so a vendored command is invoked as
`/jk:<name>` and never claims a bare name a consuming repo may want for itself.

| Command | Does |
|---|---|
| status | Reads a delivery ledger and reports milestone/slice state, the next actionable slice, and any disagreement between the ledger and the working tree. Read-only: it never writes a file, and reports anything that would change state as something for the user to run |

The commands operate on the ledger format defined in the
[ledger standard](ledger-standard.md) and gated by the `ledger` check. A
command may assume a conforming ledger, because the check is what guarantees
one.

## Consuming

Add a `commands` block to the same `skills-lock.json` that pins vendored
skills:

```json
{
  "version": 1,
  "commands": {
    "status": {
      "source": "JimAKennedy/jk-standards",
      "sourceType": "github",
      "commandPath": "commands/status.md",
      "computedHash": "<sha256 of the command file>"
    }
  }
}
```

Then install, and verify the pinned hashes on demand:

```bash
jk-standards install-commands
jk-standards install-commands --check
```

One lock file, one hash discipline, two kinds of vendored asset.
