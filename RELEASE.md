# Releasing jk-standards

This project ships from a green `main`. Tagging is the only out-of-band step —
CI proves the tree is release-ready, a human cuts the tag, and the tag cuts the
GitHub Release.

## Pre-tag checklist (must all be green on `main`)

**Precondition — regenerate first.** A version bump stales every deterministic
fixture, so run `jk-standards emit all` and commit the result *before* you work
through this checklist. Skipping it makes the `emit all --check` line below fail
by construction rather than by fault; see
[Notes on generated fixtures](#notes-on-generated-fixtures) for why one `emit
all` pass is now sufficient.

Run these from the repo root; every one must exit 0. Set `VERSION` once — the
commands below read it rather than repeating a literal, which is how the
literals in this file went a release out of date.

```bash
VERSION=$(python -c "import jk_standards; print(jk_standards.__version__)")
echo "releasing $VERSION"

jk-standards all --root .        # dogfood: every registered check passes against this tree
jk-standards emit all --check    # generated site fixtures are fresh (no drift)
jk-standards release-pins        # every adoption pin resolves to a real tag
ruff check .                     # lint
ruff format --check .            # format
pytest -q                        # full test suite
grep -q "^version = \"$VERSION\"$" pyproject.toml   # the two version sites agree
```

`release.yml` re-runs the equivalent of this checklist on the tagged tree
before it publishes anything, so a slip here fails loudly rather than shipping.
Running it first still matters: it fails on a branch you can amend, whereas the
workflow fails after the tag is already immutable.

`release-pins` runs under `jk-standards all` too; it is listed separately
because it is the one check whose subject is the release itself. It needs tags
present — it skips rather than guesses when they are absent, so run it in a
checkout with tags fetched, and read its summary line rather than trusting a
silent pass.

The newest changelog section is exempt from the tag rule while the release is
in flight, since this checklist necessarily runs before the tag exists. That
exemption is reported as `N awaiting its tag`, and it lapses the moment the
next release is dated — so skipping the tag below is caught, one release late.

Version lives in exactly two source-of-truth sites and must agree:

- `pyproject.toml` → `version = "$VERSION"`
- `src/jk_standards/__init__.py` → `__version__ = "$VERSION"`

`release.yml`'s first step asserts both against the tag, so a disagreement
blocks the Release rather than surfacing after it.

`CHANGELOG.md` must carry a section for the version being tagged, with each
present-tense entry mapping 1:1 to a shipped file (MEM001 invariant).

## Cutting the tag

Once `main` is green and the checklist above passes:

```bash
git tag "v$VERSION"
git push origin "v$VERSION"
git ls-remote --tags origin | grep "v$VERSION"    # confirm it landed
```

The confirmation matters: `0.2.0`, `0.4.0` and `0.7.0` each shipped a changelog
section and never got a tag, which turned the documented adoption pins into
dangling refs. `release-pins` now catches that, but only from the release after
the one being cut — so verify the push rather than assuming it.

The tag is immutable release provenance. Consumers pin to it via the adoption
`rev:` in their `.pre-commit-config.yaml` and the `@v0.10.0` references in the
quickstart and adopt-in-a-repo guides.

## The tag cuts the Release automatically

Pushing the tag triggers `.github/workflows/release.yml`, which publishes the
GitHub Release. Nothing further is required by hand; watch the run rather than
performing it.

The workflow re-proves the tagged tree before publishing — the tag, the
`pyproject.toml` version and `__version__` must agree, `CHANGELOG.md` must carry
a section for the version, and lint, tests, `jk-standards all` and
`emit all --check` must pass. It then builds the sdist and wheel, and creates
the Release with that changelog section as its body and the artifacts attached.

The tag is already immutable by the time the workflow runs, so `verify` cannot
prevent a bad tag — it decides whether a Release is published on top of one. A
tag cut from a tree whose version constants disagree fails red with no Release,
which is recoverable; a published Release naming a version the code does not
carry is not.

This closes the gap that `release-pins` does not cover. That check gates the
*tag*; nothing gated the *Release*, which is why `v0.10.0` sat tagged for a day
with no Release, and why `v0.1.0`, `v0.3.0`, `v0.5.0` and `v0.6.0` have tags and
no Release at all. Those four are left alone deliberately: backfilling them now
would stamp today's date on releases that shipped months ago, which is worse
provenance than their absence.

If the workflow fails after the tag is pushed, fix `main`, then delete and
re-push the tag to re-run it — the Release is created only on a green `verify`,
so a failed run leaves nothing published to clean up.

## After the tag: bump the adoption pins

The pins in `README.md`, the quickstart, the adopt-in-a-repo guide, both
configuration references, `.pre-commit-hooks.yaml`, and each reusable
workflow's header example still name the *previous* tag. Move them to the new
one in a follow-up pull request.

This is a separate step by necessity, not by preference: `release-pins`
requires every pin to resolve to a tag that exists, so bumping them in the
release pull request itself would fail the check — the tag is not pushed until
after that merges. Bumping them before the release is likewise wrong, and
leaving them is how they fell seven releases behind and started naming tags
that had never been cut.

Do **not** bump `MIGRATION-poly.md` or `MIGRATION-nfr-review.md`: their pins
record what those projects actually adopted at the time, and rewriting them
would falsify the record. They are in `release_pins.exclude` for that reason.

## Notes on generated fixtures

- `site/src/generated/{checks,config-schema,skills,doc-coverage}.json` are the
  four deterministic fixtures gated by `emit all --check`. They are the exact
  set declared in `jk-standards.yaml` under `region:generated-fixtures` — if you
  add or remove an entry there, update this list too.
- `site/src/generated/coverage.json` is non-deterministic (it reflects a real
  coverage run) and is therefore **not** gated by `--check`. It still needs a
  fresh full run before a release so the published numbers reflect the tagged
  tree.
- Regenerate everything with a single pass, from the repo root:

  ```bash
  rm -f .coverage && jk-standards emit all
  ```

  `rm -f .coverage` forces the coverage emitter to do a full run rather than
  reuse a stale data file. One `emit all` covers both the deterministic
  fixtures and `coverage.json`; do not split the coverage emitter out into a
  separate command.
- The order inside `emit all` is load-bearing: `coverage` runs **last** because
  it shells out to the pytest suite, and that suite asserts the four
  deterministic fixtures are already fresh. Run `emit coverage` on its own at a
  bumped version and it dies inside the subprocess — its output is captured and
  discarded, so all you see is a bare `CalledProcessError` naming `pytest`, with
  no hint that fixture staleness is the cause. If you hit that, re-run
  `pytest -q` directly against the same tree to see the real failures.
- `--check` is only meaningful *after* regeneration. Between a version bump and
  `emit all` it reports the fixtures as stale, which is correct and expected —
  it is not a signal that anything is broken.
