"""Check registry.

Each check module exposes `run(root, cfg, **kwargs) -> int` returning the
number of errors found. `CHECKS` maps CLI/hook names to those callables.
"""

from __future__ import annotations

from jk_standards.checks import (
    action_pinning,
    behavioral_claims,
    boundaries,
    count_drift,
    doc_completeness,
    doc_coverage,
    doc_drift,
    doc_taxonomy,
    file_line_refs,
    generated_freshness,
    research_provenance,
    snippet_regions,
    status_prose,
)

CHECKS = {
    "doc-taxonomy": doc_taxonomy.run,
    "status-prose": status_prose.run,
    "file-line-refs": file_line_refs.run,
    "count-drift": count_drift.run,
    "behavioral-claims": behavioral_claims.run,
    "generated-freshness": generated_freshness.run,
    "action-pinning": action_pinning.run,
    "snippet-regions": snippet_regions.run,
    "boundaries": boundaries.run,
    "doc-completeness": doc_completeness.run,
    "doc-coverage": doc_coverage.run,
    "research-provenance": research_provenance.run,
    "doc-drift": doc_drift.run,
}

# Checks that need only the working tree; `all` runs these unconditionally.
# doc-drift additionally needs a git base ref and runs when one is available.
STATIC_CHECKS = [name for name in CHECKS if name != "doc-drift"]
