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

from jk_standards import output

DEFAULT_CONFIG_NAME = "jk-standards.yaml"

# Roots for which iter_docs has already reported a fail-open degradation this
# process. iter_docs is called once per consuming check (six of them), so a
# single non-repo / unreadable-git run would otherwise print the same line six
# times; deduping by root keeps it to one line per run while still emitting for
# every distinct root (each test's tmp_path is unique, so tests see the line).
_fail_open_reported: set[str] = set()


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
    # status-prose accuracy arm: how many days a doc's last-touched commit may
    # be newer than its `Status: ... (YYYY-MM-DD)` anchor before the anchor is
    # flagged as stale. Default 0 = flag any commit strictly newer than the
    # anchor (D021). The arm only runs diff-scoped when a base ref is available;
    # a Status-line-only edit never counts as a substantive change.
    status_date_tolerance_days: int = 0
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
    # doc-coverage advisory floor: when set (0..100), modules whose live
    # documented-unit ratio falls below this percent emit a warning-only
    # annotation that is counted in the summary but NEVER changes the exit code
    # on its own (D014/MEM061). Default None = advisory off.
    doc_coverage_module_min_percent: int | None = None
    # doc-completeness: taxonomy classes whose docs are exempt from the
    # mapped-or-declared membership test. Mirrors the status_prose precedent of
    # keying off the front-matter class: an ``archived`` doc is deliberately
    # frozen, so requiring it to be mapped or cannot_drift-declared is noise.
    # Keys off the doc's own front-matter class (read at run time), NOT
    # cfg.generated — a generated-config doc classed ``gated`` stays governed.
    doc_completeness_exempt_classes: list[str] = field(default_factory=lambda: ["archived"])
    # research-provenance: bib_file opts the check in (empty = skipped);
    # anchor_pattern matches citation-anchor ids; phrase is the regex a
    # research-derived page's provenance sentence must match; doc_roots
    # default to the top-level doc_roots (falls back at run time).
    provenance_bib_file: str = ""
    provenance_anchor_pattern: str = r"(ref|fr)-[A-Za-z0-9-]+"
    provenance_phrase: str = r"not original (research|theory)"
    provenance_doc_roots: list[DocRoot] = field(default_factory=list)
    # import-cycle: Python package dirs (relative to root) whose module-level
    # import graph is scanned for cycles. An absent/empty section yields empty
    # packages, so the check skips (passes 0). Mirrors `boundaries`'
    # skip-when-unconfigured contract; an out-of-shape value raises ConfigError
    # so the CLI surfaces it as exit 2 (D010) rather than a check failure.
    import_cycle_packages: list[str] = field(default_factory=list)
    # workflow-permissions: where the workflows live and which extensions count.
    # Both checks below default to the same place as action-pinning but keep
    # their own fields so a repo can scope them independently.
    workflow_perm_dir: str = ".github/workflows"
    workflow_perm_extensions: list[str] = field(default_factory=lambda: [".yml", ".yaml"])
    # workflow-concurrency: `global_locks` names the groups that are *meant* to
    # serialise the whole repository (a Pages deploy, a shared environment), so
    # a deliberate global mutex is declared rather than indistinguishable from
    # a forgotten `github.ref`. `ref_tokens` are the expressions that count as
    # per-ref scoping; the default list is every context GitHub exposes that
    # varies per branch, tag, or pull request.
    workflow_concurrency_dir: str = ".github/workflows"
    workflow_concurrency_extensions: list[str] = field(default_factory=lambda: [".yml", ".yaml"])
    workflow_concurrency_global_locks: list[str] = field(default_factory=list)
    # release-pins: `repo` (owner/name) opts the check in — with none set there
    # is nothing to recognise a pin to *this* project by, so the check skips.
    # `untagged_versions` records releases that shipped a changelog section but
    # never got a tag, keeping the check a ratchet on future releases rather
    # than an argument with history; the count is always reported.
    release_pin_repo: str = ""
    release_pin_repo_url: str = ""
    release_pin_changelog: str = "CHANGELOG.md"
    release_pin_extensions: list[str] = field(
        default_factory=lambda: [".md", ".mdx", ".yml", ".yaml"]
    )
    release_pin_exclude: list[str] = field(default_factory=list)
    release_pin_untagged_versions: list[str] = field(default_factory=list)
    workflow_concurrency_ref_tokens: list[str] = field(
        default_factory=lambda: [
            "github.ref",
            "github.ref_name",
            "github.head_ref",
            "github.event.number",
            "github.event.pull_request.number",
            "github.run_id",
            "github.sha",
        ]
    )


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
    cfg.status_date_tolerance_days = _date_tolerance_days(status.get("date_tolerance_days"))

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

    workflow_permissions = data.get("workflow_permissions", {})
    cfg.workflow_perm_dir = str(workflow_permissions.get("workflow_dir", cfg.workflow_perm_dir))
    if "extensions" in workflow_permissions:
        cfg.workflow_perm_extensions = [str(e) for e in workflow_permissions["extensions"]]

    workflow_concurrency = data.get("workflow_concurrency", {})
    cfg.workflow_concurrency_dir = str(
        workflow_concurrency.get("workflow_dir", cfg.workflow_concurrency_dir)
    )
    if "extensions" in workflow_concurrency:
        cfg.workflow_concurrency_extensions = [str(e) for e in workflow_concurrency["extensions"]]
    cfg.workflow_concurrency_global_locks = _global_locks(workflow_concurrency.get("global_locks"))
    if "ref_tokens" in workflow_concurrency:
        cfg.workflow_concurrency_ref_tokens = [str(t) for t in workflow_concurrency["ref_tokens"]]

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

    provenance = data.get("research_provenance", {})
    cfg.provenance_bib_file = str(provenance.get("bib_file", cfg.provenance_bib_file))
    cfg.provenance_anchor_pattern = str(
        provenance.get("anchor_pattern", cfg.provenance_anchor_pattern)
    )
    cfg.provenance_phrase = str(provenance.get("phrase", cfg.provenance_phrase))
    cfg.provenance_doc_roots = [
        DocRoot(
            path=str(_require(d, "path", "research_provenance.doc_roots entry")),
            extensions=[str(e) for e in d.get("extensions", [".md", ".mdx"])],
        )
        for d in provenance.get("doc_roots", [])
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
    cfg.doc_coverage_module_min_percent = _module_min_percent(
        doc_coverage.get("module_min_percent")
    )

    doc_completeness = data.get("doc_completeness", {})
    if "exempt_classes" in doc_completeness:
        cfg.doc_completeness_exempt_classes = [str(c) for c in doc_completeness["exempt_classes"]]

    cfg.import_cycle_packages = _import_cycle_packages(data.get("import_cycle"))

    release_pins = data.get("release_pins", {})
    cfg.release_pin_repo = str(release_pins.get("repo", cfg.release_pin_repo))
    cfg.release_pin_repo_url = str(
        release_pins.get("repo_url")
        or (f"https://github.com/{cfg.release_pin_repo}" if cfg.release_pin_repo else "")
    )
    cfg.release_pin_changelog = str(release_pins.get("changelog", cfg.release_pin_changelog))
    if "extensions" in release_pins:
        cfg.release_pin_extensions = [str(e) for e in release_pins["extensions"]]
    cfg.release_pin_exclude = [str(e) for e in release_pins.get("exclude", [])]
    cfg.release_pin_untagged_versions = _untagged_versions(release_pins.get("untagged_versions"))
    return cfg


def _untagged_versions(value: object) -> list[str]:
    """Validate ``release_pins.untagged_versions`` into a list of versions.

    Out-of-shape input raises :class:`ConfigError` rather than coercing:
    turning ``[0.7]`` into ``["0.7"]`` would declare an exemption for a version
    string that never appears in any changelog heading, silently leaving the
    real gap unguarded.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"release_pins.untagged_versions must be a list, got {value!r}")
    out: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise ConfigError(
                f"release_pins.untagged_versions entries must be strings, got {entry!r}"
            )
        out.append(entry)
    return out


def _date_tolerance_days(value: object) -> int:
    """Validate ``status_prose.date_tolerance_days`` into a non-negative int.

    An unset/``None`` section yields ``0`` — flag any commit strictly newer than
    the Status anchor (D021). Out-of-shape input raises :class:`ConfigError`
    rather than coercing so the CLI surfaces it as exit 2 (D010): ``bool`` is
    rejected explicitly (it is an ``int`` subclass, so ``True``/``False`` would
    otherwise slip through as 1/0), and floats/strings fail the int check. A
    negative window is nonsensical (it would flag on the anchor's own day) and
    is rejected too.
    """
    if value is None:
        return 0
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            f"status_prose.date_tolerance_days must be a non-negative int or unset, got {value!r}"
        )
    if value < 0:
        raise ConfigError(f"status_prose.date_tolerance_days must be >= 0, got {value}")
    return value


def _global_locks(value: object) -> list[str]:
    """Validate ``workflow_concurrency.global_locks`` into a list of group names.

    An unset section yields ``[]`` — no group is declared repo-wide, so every
    group must scope itself by ref. Out-of-shape input raises
    :class:`ConfigError` rather than coercing: silently reading ``[5]`` as
    ``["5"]`` would declare a lock nobody wrote, which is precisely the kind of
    invisible grant this check exists to surface.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError(f"workflow_concurrency.global_locks must be a list, got {value!r}")
    out: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            raise ConfigError(
                f"workflow_concurrency.global_locks entries must be strings, got {entry!r}"
            )
        out.append(entry)
    return out


def _import_cycle_packages(value: object) -> list[str]:
    """Validate the optional ``import_cycle`` section into a list of package dirs.

    An unset/``None`` section yields ``[]`` (check skips). Otherwise the section
    must be a mapping with a ``packages`` list of strings. Anything out of shape
    — a scalar section, a non-list ``packages``, or a non-string entry — is a
    :class:`ConfigError` so the CLI surfaces it as exit 2 (D010) rather than
    silently coercing (``[str(e) for e in ...]`` would mask ``[5]`` as ``["5"]``).
    ``bool`` entries are rejected as non-strings, matching the intent.
    """
    if value is None:
        return []
    if not isinstance(value, dict):
        raise ConfigError(f"import_cycle must be a mapping or unset, got {value!r}")
    packages = value.get("packages", [])
    if not isinstance(packages, list):
        raise ConfigError(f"import_cycle.packages must be a list, got {packages!r}")
    out: list[str] = []
    for entry in packages:
        if not isinstance(entry, str):
            raise ConfigError(f"import_cycle.packages entries must be strings, got {entry!r}")
        out.append(entry)
    return out


def _module_min_percent(value: object) -> int | None:
    """Validate the optional doc_coverage.module_min_percent advisory floor.

    Accepts an int in ``[0, 100]`` (0 and 100 inclusive) or an unset/``None``
    value (advisory off). Everything else is a :class:`ConfigError` so the CLI
    surfaces it as exit 2 (D010) rather than silently coercing: ``bool`` is
    rejected explicitly (it is an ``int`` subclass, so ``True``/``False`` would
    otherwise slip through as 1/0), and floats/strings fail the int check.
    """
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            f"doc_coverage.module_min_percent must be an int in [0, 100] or unset, got {value!r}"
        )
    if not 0 <= value <= 100:
        raise ConfigError(f"doc_coverage.module_min_percent must be in [0, 100], got {value}")
    return value


def iter_docs(root: Path, cfg: Config) -> list[Path]:
    """All git-tracked doc files under the configured doc roots, exempt dirs removed.

    After the extension/exempt-dir filtering, the enumeration is intersected with
    git's tracked working-tree paths so a gitignored or untracked doc under a
    doc_root is not governed — this is what keeps a local run (which sees such
    files) in agreement with CI (whose checkout does not). When tracking cannot
    be determined — ``root`` is not a git repo, or git is unreadable —
    :func:`gitutil.tracked_paths` returns ``None`` and this *fails open*: every
    enumerated doc is returned unfiltered, exactly as before this filter existed,
    and a single summary line names the degradation so a non-repo run is
    diagnosable rather than silently governing nothing.
    """
    # Lazy import keeps config free of a hard dependency on the git seam and
    # sidesteps any import-cycle risk on the zero-dependency load path.
    from jk_standards import gitutil

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

    tracked = gitutil.tracked_paths(root)
    if tracked is None:
        _report_fail_open(root)
        return out
    return [p for p in out if p.relative_to(root).as_posix() in tracked]


def _report_fail_open(root: Path) -> None:
    """Emit the iter_docs fail-open degradation line at most once per root.

    Mirrors the ``[cpp]``-absent and ``list_tags``-``None`` precedents: a
    degradation that silently governs nothing is a landmine, so name it. Deduped
    by root because iter_docs runs once per consuming check within a single
    ``jk-standards all`` invocation.
    """
    key = str(root)
    if key in _fail_open_reported:
        return
    _fail_open_reported.add(key)
    output.summary(
        f"iter_docs: git tracking unreadable under {root} — enumerating all "
        "doc(s) without a tracked-status filter (fail-open)"
    )
