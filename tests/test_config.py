"""Config-loading tests: every YAML branch of load_config + iter_docs."""

from pathlib import Path

import pytest

from jk_standards.config import (
    BoundaryRule,
    ClaimSource,
    Config,
    ConfigError,
    DocRoot,
    ForbiddenPhrase,
    GeneratedDoc,
    SourceRoot,
    iter_docs,
    load_config,
)


def write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# --- load_config: file resolution -------------------------------------------


def test_missing_config_returns_defaults(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.doc_roots == [DocRoot("docs")]
    assert cfg.taxonomy_classes == ["generated", "gated", "archived"]
    assert "py" in cfg.file_line_extensions
    assert cfg.drift_map == ".github/docs-drift-map.yml"


def test_explicit_config_path(tmp_path):
    write(tmp_path, "custom.yaml", "doc_roots:\n  - path: alt\n")
    cfg = load_config(tmp_path, tmp_path / "custom.yaml")
    assert cfg.doc_roots == [DocRoot("alt", [".md"])]


def test_top_level_non_mapping_raises(tmp_path):
    write(tmp_path, "jk-standards.yaml", "- one\n- two\n")
    with pytest.raises(ConfigError, match="top level must be a mapping"):
        load_config(tmp_path)


def test_empty_yaml_returns_defaults(tmp_path):
    write(tmp_path, "jk-standards.yaml", "")
    cfg = load_config(tmp_path)
    assert cfg.doc_roots == [DocRoot("docs")]


# --- doc_roots --------------------------------------------------------------


def test_doc_roots_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "doc_roots:\n  - path: src\n    extensions: ['.md', '.mdx']\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.doc_roots == [DocRoot("src", [".md", ".mdx"])]


def test_doc_roots_missing_path_raises(tmp_path):
    write(tmp_path, "jk-standards.yaml", "doc_roots:\n  - extensions: ['.md']\n")
    with pytest.raises(ConfigError, match="missing required key 'path'"):
        load_config(tmp_path)


def test_doc_roots_default_extensions(tmp_path):
    write(tmp_path, "jk-standards.yaml", "doc_roots:\n  - path: src\n")
    cfg = load_config(tmp_path)
    assert cfg.doc_roots == [DocRoot("src", [".md"])]


# --- exempt_dirs ------------------------------------------------------------


def test_exempt_dirs_parsed(tmp_path):
    write(tmp_path, "jk-standards.yaml", "exempt_dirs: ['docs/archive', 'vendor']\n")
    cfg = load_config(tmp_path)
    assert cfg.exempt_dirs == ["docs/archive", "vendor"]


# --- taxonomy ---------------------------------------------------------------


def test_taxonomy_classes_and_extra_files_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "taxonomy:\n  classes: ['living', 'frozen']\n  extra_files: ['README.md']\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.taxonomy_classes == ["living", "frozen"]
    assert cfg.taxonomy_extra_files == ["README.md"]


# --- status_prose -----------------------------------------------------------


def test_status_prose_forbidden_extra_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        (
            "status_prose:\n"
            "  forbidden_extra:\n"
            "    - pattern: '\\bcoming soon\\b'\n"
            "      hint: 'ship it or delete it'\n"
            "    - pattern: 'TBD'\n"
        ),
    )
    cfg = load_config(tmp_path)
    assert cfg.status_forbidden_extra == [
        ForbiddenPhrase(r"\bcoming soon\b", "ship it or delete it"),
        ForbiddenPhrase("TBD", "forbidden phrase"),
    ]


def test_status_prose_forbidden_extra_missing_pattern_raises(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "status_prose:\n  forbidden_extra:\n    - hint: nope\n",
    )
    with pytest.raises(ConfigError, match="missing required key 'pattern'"):
        load_config(tmp_path)


# --- file_line_refs ---------------------------------------------------------


def test_file_line_refs_extensions_strip_leading_dot(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "file_line_refs:\n  extensions: ['.py', 'js', '.tsx']\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.file_line_extensions == ["py", "js", "tsx"]


def test_file_line_refs_source_roots_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        (
            "file_line_refs:\n"
            "  source_roots:\n"
            "    - path: src\n"
            "      extensions: ['.py']\n"
            "    - path: lib\n"
        ),
    )
    cfg = load_config(tmp_path)
    assert cfg.file_line_source_roots == [
        SourceRoot("src", [".py"]),
        SourceRoot("lib", []),
    ]


def test_file_line_refs_source_roots_missing_path_raises(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "file_line_refs:\n  source_roots:\n    - extensions: ['.py']\n",
    )
    with pytest.raises(ConfigError, match="missing required key 'path'"):
        load_config(tmp_path)


# --- count_drift ------------------------------------------------------------


def test_count_drift_triggers_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "count_drift:\n  triggers: ['factory presets', 'chapters']\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.count_triggers == ["factory presets", "chapters"]


# --- drift_map --------------------------------------------------------------


def test_drift_map_override(tmp_path):
    write(tmp_path, "jk-standards.yaml", "drift_map: ops/drift.yml\n")
    cfg = load_config(tmp_path)
    assert cfg.drift_map == "ops/drift.yml"


def test_drift_map_default_when_absent(tmp_path):
    write(tmp_path, "jk-standards.yaml", "exempt_dirs: []\n")
    cfg = load_config(tmp_path)
    assert cfg.drift_map == ".github/docs-drift-map.yml"


# --- doc_drift.deps_only_manifests ------------------------------------------


def test_deps_only_manifests_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "doc_drift:\n  deps_only_manifests: ['package.json', 'pyproject.toml']\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.deps_only_manifests == ["package.json", "pyproject.toml"]


# --- generated --------------------------------------------------------------


def test_generated_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "generated:\n  - doc: docs/api.md\n    command: 'make docs'\n",
    )
    cfg = load_config(tmp_path)
    assert cfg.generated == [GeneratedDoc("docs/api.md", "make docs")]


def test_generated_missing_doc_raises(tmp_path):
    write(tmp_path, "jk-standards.yaml", "generated:\n  - command: 'make docs'\n")
    with pytest.raises(ConfigError, match="missing required key 'doc'"):
        load_config(tmp_path)


def test_generated_missing_command_raises(tmp_path):
    write(tmp_path, "jk-standards.yaml", "generated:\n  - doc: docs/api.md\n")
    with pytest.raises(ConfigError, match="missing required key 'command'"):
        load_config(tmp_path)


# --- behavioral_claims.sources ---------------------------------------------


def test_claim_sources_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        (
            "behavioral_claims:\n"
            "  sources:\n"
            "    - type: pytest\n"
            "      path: tests\n"
            "    - type: gtest\n"
            "      path: cpp/tests\n"
        ),
    )
    cfg = load_config(tmp_path)
    assert cfg.claim_sources == [
        ClaimSource("pytest", "tests"),
        ClaimSource("gtest", "cpp/tests"),
    ]


def test_claim_sources_missing_type_raises(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "behavioral_claims:\n  sources:\n    - path: tests\n",
    )
    with pytest.raises(ConfigError, match="missing required key 'type'"):
        load_config(tmp_path)


def test_claim_sources_missing_path_raises(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        "behavioral_claims:\n  sources:\n    - type: pytest\n",
    )
    with pytest.raises(ConfigError, match="missing required key 'path'"):
        load_config(tmp_path)


# --- boundaries -------------------------------------------------------------


def test_boundaries_rules_parsed(tmp_path):
    write(
        tmp_path,
        "jk-standards.yaml",
        (
            "boundaries:\n"
            "  rules:\n"
            "    - name: checks-no-cli\n"
            "      from: src/jk_standards/checks\n"
            "      forbid: 'jk_standards\\.cli'\n"
            "      extensions: ['.py']\n"
            "      hint: a check must not import the CLI\n"
            "    - from: src/a\n"
            "      forbid: 'import b'\n"
        ),
    )
    cfg = load_config(tmp_path)
    assert cfg.boundaries == [
        BoundaryRule(
            from_dir="src/jk_standards/checks",
            forbid=r"jk_standards\.cli",
            name="checks-no-cli",
            extensions=[".py"],
            hint="a check must not import the CLI",
        ),
        BoundaryRule(from_dir="src/a", forbid="import b"),
    ]


def test_boundaries_missing_from_raises(tmp_path):
    write(tmp_path, "jk-standards.yaml", "boundaries:\n  rules:\n    - forbid: 'x'\n")
    with pytest.raises(ConfigError, match="missing required key 'from'"):
        load_config(tmp_path)


def test_boundaries_missing_forbid_raises(tmp_path):
    write(tmp_path, "jk-standards.yaml", "boundaries:\n  rules:\n    - from: src\n")
    with pytest.raises(ConfigError, match="missing required key 'forbid'"):
        load_config(tmp_path)


# --- doc_coverage.module_min_percent (advisory floor) ----------------------


def test_module_min_percent_default_is_none(tmp_path):
    cfg = load_config(tmp_path)
    assert cfg.doc_coverage_module_min_percent is None


def test_module_min_percent_absent_when_section_present(tmp_path):
    write(tmp_path, "jk-standards.yaml", "doc_coverage:\n  doc_scopes: ['docs']\n")
    cfg = load_config(tmp_path)
    assert cfg.doc_coverage_module_min_percent is None


@pytest.mark.parametrize("value", [0, 50, 100])
def test_module_min_percent_valid_values_accepted(tmp_path, value):
    write(tmp_path, "jk-standards.yaml", f"doc_coverage:\n  module_min_percent: {value}\n")
    cfg = load_config(tmp_path)
    assert cfg.doc_coverage_module_min_percent == value


@pytest.mark.parametrize("value", [101, -1])
def test_module_min_percent_out_of_range_raises(tmp_path, value):
    write(tmp_path, "jk-standards.yaml", f"doc_coverage:\n  module_min_percent: {value}\n")
    with pytest.raises(ConfigError, match=r"module_min_percent must be in \[0, 100\]"):
        load_config(tmp_path)


@pytest.mark.parametrize("literal", ["true", "false"])
def test_module_min_percent_bool_raises(tmp_path, literal):
    # YAML `true`/`false` parse to Python bool; bool is an int subclass, so it
    # must be rejected explicitly rather than coerced to 1/0.
    write(tmp_path, "jk-standards.yaml", f"doc_coverage:\n  module_min_percent: {literal}\n")
    with pytest.raises(ConfigError, match="module_min_percent must be an int"):
        load_config(tmp_path)


@pytest.mark.parametrize("literal", ["85.5", "'85'", "high"])
def test_module_min_percent_non_int_raises(tmp_path, literal):
    write(tmp_path, "jk-standards.yaml", f"doc_coverage:\n  module_min_percent: {literal}\n")
    with pytest.raises(ConfigError, match="module_min_percent must be an int"):
        load_config(tmp_path)


# --- iter_docs --------------------------------------------------------------


def test_iter_docs_finds_matching_extensions(tmp_path):
    write(tmp_path, "docs/a.md", "x")
    write(tmp_path, "docs/b.txt", "x")
    write(tmp_path, "docs/c.mdx", "x")
    cfg = Config(doc_roots=[DocRoot("docs", [".md", ".mdx"])])
    result = [p.name for p in iter_docs(tmp_path, cfg)]
    assert result == ["a.md", "c.mdx"]


def test_iter_docs_skips_missing_root(tmp_path):
    cfg = Config(doc_roots=[DocRoot("nonexistent")])
    assert iter_docs(tmp_path, cfg) == []


def test_iter_docs_skips_exempt_dirs(tmp_path):
    write(tmp_path, "docs/keep.md", "x")
    write(tmp_path, "docs/archive/old.md", "x")
    cfg = Config(doc_roots=[DocRoot("docs", [".md"])], exempt_dirs=["docs/archive"])
    result = [p.relative_to(tmp_path).as_posix() for p in iter_docs(tmp_path, cfg)]
    assert result == ["docs/keep.md"]


def test_iter_docs_skips_non_files(tmp_path):
    # rglob('*') matches directories too; the `is_file()` branch filters them.
    (tmp_path / "docs" / "subdir").mkdir(parents=True)
    write(tmp_path, "docs/a.md", "x")
    cfg = Config(doc_roots=[DocRoot("docs", [".md"])])
    result = [p.name for p in iter_docs(tmp_path, cfg)]
    assert result == ["a.md"]
