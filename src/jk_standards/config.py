"""Configuration model for jk-standards.yaml.

One config file supplies everything project-specific: doc roots, class
vocabulary, drift-map path, count trigger phrases, test-index sources.
Every field has a default so an empty (or absent) config still yields a
usable — if minimal — configuration.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_CONFIG_NAME = "jk-standards.yaml"


class ConfigError(Exception):
    pass


@dataclass
class DocRoot:
    path: str
    extensions: list[str] = field(default_factory=lambda: [".md"])


@dataclass
class SourceRoot:
    path: str
    extensions: list[str] = field(default_factory=list)


@dataclass
class GeneratedDoc:
    doc: str
    command: str


@dataclass
class ForbiddenPhrase:
    pattern: str
    hint: str


@dataclass
class ClaimSource:
    type: str  # gtest | js | pytest
    path: str


@dataclass
class BoundaryRule:
    """One forbidden-reference rule for the `boundaries` check.

    Files under ``from_dir`` (optionally filtered to ``extensions``) MUST NOT
    contain a line matching the ``forbid`` regex — a directed dependency
    constraint between components (e.g. a check must not reference the CLI).
    ``hint`` is the human-facing reason surfaced on each violation.
    """

    from_dir: str
    forbid: str
    name: str = ""
    extensions: list[str] = field(default_factory=list)
    hint: str = ""


@dataclass
class SnippetMarkerSyntax:
    """Per-file-type override of the region marker comment prefixes.

    `extensions` are matched against a source file's suffix (e.g. ``.sh``);
    `prefixes` are the comment tokens a `region:<name>` marker may follow —
    ``#``, ``//``, or the block form ``<!--`` (paired with ``-->``).
    """

    extensions: list[str]
    prefixes: list[str]


@dataclass
class Config:
    doc_roots: list[DocRoot] = field(default_factory=lambda: [DocRoot("docs")])
    exempt_dirs: list[str] = field(default_factory=list)
    taxonomy_classes: list[str] = field(default_factory=lambda: ["generated", "gated", "archived"])
    taxonomy_extra_files: list[str] = field(default_factory=list)
    status_forbidden_extra: list[ForbiddenPhrase] = field(default_factory=list)
    file_line_extensions: list[str] = field(
        default_factory=lambda: [
            "c",
            "cc",
            "cpp",
            "h",
            "hpp",
            "py",
            "js",
            "mjs",
            "ts",
            "tsx",
            "astro",
            "md",
            "mdx",
            "sh",
            "yml",
            "yaml",
        ]
    )
    file_line_source_roots: list[SourceRoot] = field(default_factory=list)
    count_triggers: list[str] = field(default_factory=list)
    drift_map: str = ".github/docs-drift-map.yml"
    deps_only_manifests: list[str] = field(default_factory=list)
    generated: list[GeneratedDoc] = field(default_factory=list)
    claim_sources: list[ClaimSource] = field(default_factory=list)
    action_pin_workflow_dir: str = ".github/workflows"
    action_pin_extensions: list[str] = field(default_factory=lambda: [".yml", ".yaml"])
    # snippet-regions: doc roots default to the top-level doc_roots (falls back
    # at run time); source_roots supply the tree searched for prose mentions;
    # markers override the default `//`/`#`/`<!--` prefixes per file type.
    snippet_doc_roots: list[DocRoot] = field(default_factory=list)
    snippet_source_roots: list[SourceRoot] = field(default_factory=list)
    snippet_markers: list[SnippetMarkerSyntax] = field(default_factory=list)
    # boundaries: directed forbidden-reference rules between component dirs.
    boundaries: list[BoundaryRule] = field(default_factory=list)
    # doc-coverage: Python source roots the ast enumerator walks, and the doc
    # scopes scanned for the "mention" OR-signal. An absent section yields empty
    # source_roots, so the check trivially passes (nothing to enumerate).
    doc_coverage_source_roots: list[SourceRoot] = field(default_factory=list)
    doc_coverage_doc_scopes: list[str] = field(default_factory=list)


def _require(mapping: dict, key: str, context: str) -> object:
    if key not in mapping:
        raise ConfigError(f"missing required key {key!r} in {context}")
    return mapping[key]


def load_config(root: Path, config_path: Path | None = None) -> Config:
    path = config_path or root / DEFAULT_CONFIG_NAME
    if not path.exists():
        return Config()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be a mapping")

    cfg = Config()
    if "doc_roots" in data:
        cfg.doc_roots = [
            DocRoot(
                path=str(_require(d, "path", "doc_roots entry")),
                extensions=[str(e) for e in d.get("extensions", [".md"])],
            )
            for d in data["doc_roots"]
        ]
    cfg.exempt_dirs = [str(d) for d in data.get("exempt_dirs", [])]

    taxonomy = data.get("taxonomy", {})
    if "classes" in taxonomy:
        cfg.taxonomy_classes = [str(c) for c in taxonomy["classes"]]
    cfg.taxonomy_extra_files = [str(f) for f in taxonomy.get("extra_files", [])]

    status = data.get("status_prose", {})
    cfg.status_forbidden_extra = [
        ForbiddenPhrase(
            pattern=str(_require(p, "pattern", "status_prose.forbidden_extra entry")),
            hint=str(p.get("hint", "forbidden phrase")),
        )
        for p in status.get("forbidden_extra", [])
    ]

    flr = data.get("file_line_refs", {})
    if "extensions" in flr:
        cfg.file_line_extensions = [str(e).lstrip(".") for e in flr["extensions"]]
    cfg.file_line_source_roots = [
        SourceRoot(
            path=str(_require(s, "path", "file_line_refs.source_roots entry")),
            extensions=[str(e) for e in s.get("extensions", [])],
        )
        for s in flr.get("source_roots", [])
    ]

    cfg.count_triggers = [str(t) for t in data.get("count_drift", {}).get("triggers", [])]
    cfg.drift_map = str(data.get("drift_map", cfg.drift_map))
    cfg.deps_only_manifests = [
        str(f) for f in data.get("doc_drift", {}).get("deps_only_manifests", [])
    ]
    cfg.generated = [
        GeneratedDoc(
            doc=str(_require(g, "doc", "generated entry")),
            command=str(_require(g, "command", "generated entry")),
        )
        for g in data.get("generated", [])
    ]
    cfg.claim_sources = [
        ClaimSource(
            type=str(_require(s, "type", "behavioral_claims.sources entry")),
            path=str(_require(s, "path", "behavioral_claims.sources entry")),
        )
        for s in data.get("behavioral_claims", {}).get("sources", [])
    ]

    action_pinning = data.get("action_pinning", {})
    cfg.action_pin_workflow_dir = str(
        action_pinning.get("workflow_dir", cfg.action_pin_workflow_dir)
    )
    if "extensions" in action_pinning:
        cfg.action_pin_extensions = [str(e) for e in action_pinning["extensions"]]

    snippet = data.get("snippet_regions", {})
    cfg.snippet_doc_roots = [
        DocRoot(
            path=str(_require(d, "path", "snippet_regions.doc_roots entry")),
            extensions=[str(e) for e in d.get("extensions", [".md", ".mdx"])],
        )
        for d in snippet.get("doc_roots", [])
    ]
    cfg.snippet_source_roots = [
        SourceRoot(
            path=str(_require(s, "path", "snippet_regions.source_roots entry")),
            extensions=[str(e) for e in s.get("extensions", [])],
        )
        for s in snippet.get("source_roots", [])
    ]
    cfg.snippet_markers = [
        SnippetMarkerSyntax(
            extensions=[str(e) for e in _require(m, "extensions", "snippet_regions.markers entry")],
            prefixes=[str(p) for p in _require(m, "prefixes", "snippet_regions.markers entry")],
        )
        for m in snippet.get("markers", [])
    ]

    cfg.boundaries = [
        BoundaryRule(
            from_dir=str(_require(r, "from", "boundaries.rules entry")),
            forbid=str(_require(r, "forbid", "boundaries.rules entry")),
            name=str(r.get("name", "")),
            extensions=[str(e) for e in r.get("extensions", [])],
            hint=str(r.get("hint", "")),
        )
        for r in data.get("boundaries", {}).get("rules", [])
    ]

    doc_coverage = data.get("doc_coverage", {})
    cfg.doc_coverage_source_roots = [
        SourceRoot(
            path=str(_require(s, "path", "doc_coverage.source_roots entry")),
            extensions=[str(e) for e in s.get("extensions", [".py"])],
        )
        for s in doc_coverage.get("source_roots", [])
    ]
    cfg.doc_coverage_doc_scopes = [str(s) for s in doc_coverage.get("doc_scopes", [])]
    return cfg


def iter_docs(root: Path, cfg: Config) -> list[Path]:
    """All doc files under the configured doc roots, exempt dirs removed."""
    out: list[Path] = []
    for doc_root in cfg.doc_roots:
        base = root / doc_root.path
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if not any(path.name.endswith(ext) for ext in doc_root.extensions):
                continue
            rel = path.relative_to(root).as_posix()
            if any(rel.startswith(d) for d in cfg.exempt_dirs):
                continue
            out.append(path)
    return out
