"""Check registry.

Each check module exposes `run(root, cfg, **kwargs) -> int` returning the
number of errors found. `CHECKS` maps CLI/hook names to those callables.
"""

from __future__ import annotations

# This package __init__ re-exports every check module, so it imports
# doc_completeness/doc_coverage while those modules import `doc_drift` *through*
# this package (`from jk_standards.checks import doc_drift`) — a real but benign
# import-time SCC {checks, doc_completeness, doc_coverage}. The re-export hub is
# the intended toplevel and cannot be broken without hiding the registry, so the
# cycle is waived in place (mirrors the boundary-ok hatch on the line below):
# import-cycle-ok: benign re-export SCC {checks, doc_completeness, doc_coverage}
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
    import_cycle,
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
    "import-cycle": import_cycle.run,
}

# Checks that need only the working tree; `all` runs these unconditionally.
# doc-drift additionally needs a git base ref and runs when one is available.
STATIC_CHECKS = [name for name in CHECKS if name != "doc-drift"]
