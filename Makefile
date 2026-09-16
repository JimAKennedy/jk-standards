# Thin aliases over scripts/verify.sh — the local conformance gate.
# `make check` reproduces every CI job that can run on a laptop (see ci.yml).
.PHONY: check check-fast eval help

## check: run the full local conformance gate (ruff, pytest, coverage, dogfood, build, site)
check:
	scripts/verify.sh

## check-fast: same gate without the Node/site-build step
check-fast:
	scripts/verify.sh --no-site

## eval: LLM-judged skill evaluations (paid; needs ANTHROPIC_API_KEY or .env)
eval:
	@if [ -f .env ]; then set -a; . ./.env; set +a; fi; \
	if [ -z "$$ANTHROPIC_API_KEY" ]; then \
		echo "make eval: ANTHROPIC_API_KEY is not set — export it or put it in a gitignored .env (see evals/README.md)"; \
		exit 2; \
	fi; \
	ANTHROPIC_API_KEY="$$ANTHROPIC_API_KEY" .venv/bin/python -m pytest evals/ -q

## help: list targets
help:
	@grep -E '^## ' $(MAKEFILE_LIST) | sed 's/## //'
