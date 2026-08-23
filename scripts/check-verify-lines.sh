#!/usr/bin/env bash
# Validate candidate GSD task `Verify` lines against the LIVE gsd-pi
# verification gate, before they are written into a slice plan.
#
# A Verify line rejected by this gate blocks the whole slice at pre-exec, and
# auto-mode's finalize-retry re-runs the same static validation with unchanged
# inputs — so it fails identically twice and trips the liveness backstop.
# See .gsd/KNOWLEDGE.md rules 1-4.
#
# Usage:
#   scripts/check-verify-lines.sh 'git diff --exit-code' '.venv/bin/pytest -q'
#   printf '%s\n' 'cmd one' 'cmd two' | scripts/check-verify-lines.sh
#
# Exit 0 when every line validates; 1 when any line is rejected; 2 on setup error.
set -euo pipefail

shim="$(command -v gsd)" || { echo "gsd not on PATH" >&2; exit 2; }
target="$(grep '^# cmd-shim-target=' "$shim" | cut -d= -f2-)"
[ -n "$target" ] || { echo "cannot resolve gsd shim target from $shim" >&2; exit 2; }
GSD_PKG="$(dirname "$(dirname "$target")")"
GSD_GATE="$GSD_PKG/dist/resources/extensions/gsd/verification-gate.js"
[ -f "$GSD_GATE" ] || { echo "verification gate not found at $GSD_GATE" >&2; exit 2; }
export GSD_PKG GSD_GATE

runner='
import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
const { validateVerificationCommand } = await import(pathToFileURL(process.env.GSD_GATE).href);
const version = JSON.parse(readFileSync(process.env.GSD_PKG + "/package.json", "utf8")).version;
const lines = readFileSync(0, "utf8").split(/\r?\n/).map(s => s.trim()).filter(Boolean);
console.error(`gsd-pi ${version} — ${lines.length} line(s)`);
let bad = 0;
for (const line of lines) {
  const r = validateVerificationCommand(line);
  if (r.ok) console.log(`  ok   ${line}`);
  else { bad++; console.log(`  FAIL ${line}\n       reason: ${r.reason}`); }
}
process.exit(bad ? 1 : 0);
'

if [ "$#" -gt 0 ]; then
  printf '%s\n' "$@" | node --input-type=module -e "$runner"
else
  node --input-type=module -e "$runner"
fi
