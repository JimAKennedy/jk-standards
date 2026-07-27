#!/usr/bin/env bash
# verify.sh — run the locally-reproducible half of the CI conformance gate.
#
# `jk-standards all` alone only runs the doc-conformance checks (the CI
# `dogfood` job). Real conformance is what `ci-complete` requires in
# .github/workflows/ci.yml — a superset. This script runs every CI job that
# can run on a laptop, in the same order, and reports one pass/fail summary.
#
# It always runs from the repo root (resolved from this script's location), so
# it behaves the same whether you invoke it from root or a subdirectory.
#
# CI jobs intentionally NOT reproduced here (they need CI-only inputs):
#   - secrets-scan             (gitleaks: needs full history + GITHUB_TOKEN)
#   - reusable-workflow-smoke  (smoke-tests doc-discipline.yml's shape in Actions)
#   - sanitizer-nightly-smoke  (smoke-tests sanitizer-nightly.yml's shape in Actions)
#
# Usage:
#   scripts/verify.sh              # full gate (installs nothing; assumes deps present)
#   scripts/verify.sh --no-site    # skip the Node/site-build step
#   scripts/verify.sh --base REF   # run doc-drift against REF (default: main)
#
# Exit code: 0 if every step passed, 1 if any step failed.

set -uo pipefail

# --- resolve repo root from this script's location, then cd there ------------
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT" || { echo "cannot cd to repo root $REPO_ROOT" >&2; exit 1; }

# --- args --------------------------------------------------------------------
RUN_SITE=1
BASE_REF="main"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-site) RUN_SITE=0; shift ;;
    --base)    BASE_REF="${2:?--base needs a ref}"; shift 2 ;;
    -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

# --- pretty output + step runner ---------------------------------------------
if [[ -t 1 ]]; then BOLD=$'\033[1m'; GREEN=$'\033[32m'; RED=$'\033[31m'; DIM=$'\033[2m'; RST=$'\033[0m'
else BOLD=; GREEN=; RED=; DIM=; RST=; fi

PASSED=(); FAILED=(); SKIPPED=()

run() {
  # run "Label" cmd args...
  local label="$1"; shift
  printf '%s\n' "${BOLD}▶ ${label}${RST}"
  printf '%s\n' "${DIM}\$ $*${RST}"
  if "$@"; then
    PASSED+=("$label")
    printf '%s\n\n' "${GREEN}✓ ${label}${RST}"
  else
    local code=$?
    FAILED+=("$label (exit $code)")
    printf '%s\n\n' "${RED}✗ ${label} (exit $code)${RST}"
  fi
}

skip() { SKIPPED+=("$1"); printf '%s\n\n' "${DIM}— skipped: $1${RST}"; }

echo "${BOLD}jk-standards local conformance gate${RST}  (root: $REPO_ROOT)"
echo

# --- CI job: test ------------------------------------------------------------
run "ruff check"          ruff check src/ tests/
run "ruff format --check" ruff format --check src/ tests/
run "pytest"              python -m pytest tests/

# --- CI job: coverage (80% floor via coverage.py fail_under) ------------------
run "coverage (80% floor)" bash -c 'coverage run -m pytest tests/ && coverage report'

# --- CI job: dogfood ---------------------------------------------------------
run "jk-standards all"            jk-standards all
run "jk-standards action-pinning" jk-standards action-pinning
run "jk-standards snippet-regions" jk-standards snippet-regions

# doc-drift is base-gated: it needs a git base ref to diff against (CI supplies
# GITHUB_BASE_REF). Run it explicitly here against $BASE_REF when that ref exists.
if git rev-parse --verify --quiet "$BASE_REF" >/dev/null; then
  run "doc-drift (--base $BASE_REF)" jk-standards doc-drift --base "$BASE_REF"
else
  skip "doc-drift (base ref '$BASE_REF' not found — pass --base <ref>)"
fi

# --- CI job: emit-check (fixture drift) --------------------------------------
run "emit all --check" jk-standards emit all --check

# --- CI job: package ---------------------------------------------------------
run "python -m build"  python -m build
run "twine check"      bash -c 'python -m twine check dist/*'

# --- CI job: site-build ------------------------------------------------------
if [[ "$RUN_SITE" -eq 1 ]]; then
  if command -v npm >/dev/null 2>&1; then
    run "site: npm ci"          bash -c 'cd site && npm ci'
    run "site: build"           bash -c 'cd site && npm run build'
    run "site: claim tests"     bash -c 'cd site && node --test tests/*.test.mjs'
  else
    skip "site-build (npm not found)"
  fi
else
  skip "site-build (--no-site)"
fi

# --- CI-only jobs (cannot run locally) ---------------------------------------
skip "secrets-scan (gitleaks — CI-only: needs full history + token)"
skip "reusable-workflow-smoke (doc-discipline shape smoke — CI-only)"
skip "sanitizer-nightly-smoke (sanitizer-nightly shape smoke — CI-only)"

# --- summary -----------------------------------------------------------------
echo "${BOLD}── summary ──${RST}"
printf '%s%d passed%s' "$GREEN" "${#PASSED[@]}" "$RST"
printf '  %s%d failed%s' "$RED" "${#FAILED[@]}" "$RST"
printf '  %s%d skipped%s\n' "$DIM" "${#SKIPPED[@]}" "$RST"

if [[ ${#FAILED[@]} -gt 0 ]]; then
  echo
  echo "${RED}${BOLD}FAILED:${RST}"
  for f in "${FAILED[@]}"; do echo "  ${RED}✗${RST} $f"; done
  echo
  echo "${DIM}Skipped (informational): ${SKIPPED[*]}${RST}"
  exit 1
fi

echo
echo "${GREEN}${BOLD}All locally-runnable conformance gates passed.${RST}"
echo "${DIM}Not run here (CI-only): ${SKIPPED[*]}${RST}"
exit 0
