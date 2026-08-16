# Releasing jk-standards

This project ships from a green `main`. Tagging is the only out-of-band step —
CI proves the tree is release-ready; a human cuts the tag.

## Pre-tag checklist (must all be green on `main`)

Run these from the repo root; every one must exit 0:

```bash
jk-standards all --root .        # dogfood: every registered check passes against this tree
jk-standards emit all --check    # generated site fixtures are fresh (no drift)
jk-standards release-pins        # every adoption pin resolves to a real tag
ruff check .                     # lint
ruff format --check .            # format
pytest -q                        # full test suite
python -c "import jk_standards; assert jk_standards.__version__ == '0.8.0'"
```

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

- `pyproject.toml` → `version = "0.8.0"`
- `src/jk_standards/__init__.py` → `__version__ = "0.8.0"`

`CHANGELOG.md` must carry a section for the version being tagged, with each
present-tense entry mapping 1:1 to a shipped file (MEM001 invariant).

## Cutting the tag

Once `main` is green and the checklist above passes:

```bash
git tag v0.8.0
git push origin v0.8.0
git ls-remote --tags origin | grep v0.8.0    # confirm it landed
```

The confirmation matters: `0.2.0`, `0.4.0` and `0.7.0` each shipped a changelog
section and never got a tag, which turned the documented adoption pins into
dangling refs. `release-pins` now catches that, but only from the release after
the one being cut — so verify the push rather than assuming it.

The tag is immutable release provenance. Consumers pin to it via the adoption
`rev:` in their `.pre-commit-config.yaml` and the `@v0.8.0` references in the
quickstart and adopt-in-a-repo guides.

## Notes on generated fixtures

- `site/src/generated/{checks,config-schema,skills}.json` are deterministic and
  gated by `emit all --check`; regenerate with `jk-standards emit all` and commit.
- `site/src/generated/coverage.json` is non-deterministic (it reflects a real
  coverage run) and is therefore **not** gated by `--check`. Regenerate it with a
  fresh full run — `rm -f .coverage && jk-standards emit coverage` — before a
  release so the published numbers reflect the tagged tree.
