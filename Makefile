# Thin aliases over scripts/verify.sh — the local conformance gate.
# `make check` reproduces every CI job that can run on a laptop (see ci.yml).
.PHONY: check check-fast help

## check: run the full local conformance gate (ruff, pytest, coverage, dogfood, build, site)
check:
	scripts/verify.sh

## check-fast: same gate without the Node/site-build step
check-fast:
	scripts/verify.sh --no-site

## help: list targets
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //'
