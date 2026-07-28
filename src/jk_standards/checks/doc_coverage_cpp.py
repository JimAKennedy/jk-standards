"""doc-coverage C++ enumerator (behind the optional ``jk-standards[cpp]`` extra).

This module is the C++ arm of :mod:`jk_standards.checks.doc_coverage`. It parses
``.cpp``/``.hpp`` sources with tree-sitter-cpp and returns the SAME
:class:`~jk_standards.checks.doc_coverage.DocUnit` records the Python (ast) path
produces, so the ``enumerate_units`` seam contract is unchanged and the shared
module-granular gate treats C++ and Python units identically.

Graceful degradation is the whole point of hiding the native grammar behind an
optional extra: :func:`_get_cpp_parser` mirrors nfr-review's
``_get_parser() -> None`` fallback (``../nfr-review`` collectors/ast_common.py).
When ``tree_sitter``/``tree_sitter_cpp`` is not importable the parser is ``None``,
:func:`cpp_units_for_file` returns zero units, and a repo that never installed
``jk-standards[cpp]`` keeps working with the PyYAML-only zero-dependency default.

Enumerated public units (the doc-comment ``has_docstring`` signal is set when a
Doxygen doc comment — ``///``, ``//!``, ``/** */``, ``/*! */`` — sits immediately
above the declaration):

* **function** — a named function declaration/definition at namespace scope.
* **class** / **struct** — a named ``class``/``struct`` specifier.
* **method** — a *public* member function of a class or struct. Class members
  are private by default until a ``public:`` label; struct members are public by
  default until a ``private:``/``protected:`` label — matching C++ access rules.

The drift and mention OR-signals are supplied by the caller exactly as for the
Python path, so a C++ unit is documented iff it carries a doc comment, its file
matches a drift-map ``sources:`` glob, or its bare name is mentioned in a doc
scope.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from jk_standards.checks.doc_coverage import DocUnit

if TYPE_CHECKING:
    from tree_sitter import Node, Parser

# The Doxygen doc-comment openers. A plain ``//`` line comment or ``/* */`` block
# comment is deliberately NOT a doc comment — only these four forms set the
# has_docstring signal, matching how a Python docstring (not any comment) does.
_DOC_COMMENT_PREFIXES = ("///", "//!", "/**", "/*!")

# Cached lazily-built parser. ``False`` is the "not yet attempted" sentinel;
# ``None`` records a prior failed import so we never re-try (and never re-warn).
_PARSER: "Parser | None | bool" = False


def _get_cpp_parser() -> "Parser | None":
    """Return a cached tree-sitter C++ parser, or ``None`` if unavailable.

    Mirrors nfr-review's ``_get_parser()`` fallback: the native grammar lives
    only in the optional ``jk-standards[cpp]`` extra, so an ``ImportError`` here
    is the expected graceful-degradation path, not a bug. The result (parser or
    ``None``) is cached on first call.
    """
    global _PARSER
    if _PARSER is False:
        try:
            import tree_sitter
            import tree_sitter_cpp

            lang = tree_sitter.Language(tree_sitter_cpp.language())
            _PARSER = tree_sitter.Parser(lang)
        except (ImportError, ModuleNotFoundError):
            _PARSER = None
    return _PARSER  # type: ignore[return-value]


def _text(node: "Node", source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")


def _name_of(node: "Node | None") -> str | None:
    """Extract the bare name a (possibly nested) declarator introduces.

    Unwraps pointer/reference/parenthesised declarators and qualified names so a
    ``Foo::bar`` method or an ``int* make()`` function still yields ``bar`` /
    ``make``. Returns ``None`` for anonymous or unrecognised declarators.
    """
    if node is None:
        return None
    if node.type in ("identifier", "field_identifier", "type_identifier"):
        return node.text.decode("utf-8", errors="replace") if node.text else None
    if node.type in ("destructor_name", "operator_name", "qualified_identifier"):
        # A destructor (~Foo), an operator (operator==), or a qualified name
        # (ns::Foo::bar) — the trailing name is what a doc scope would mention.
        target = node.child_by_field_name("name")
        return _name_of(target) if target is not None else (
            node.text.decode("utf-8", errors="replace") if node.text else None
        )
    # pointer_declarator, reference_declarator, parenthesized_declarator, etc.
    inner = node.child_by_field_name("declarator")
    if inner is not None:
        return _name_of(inner)
    for child in node.named_children:
        found = _name_of(child)
        if found is not None:
            return found
    return None


def _find_function_declarator(node: "Node") -> "Node | None":
    """Return the (first) ``function_declarator`` under *node*, if any.

    Skips the parameter list so a function-typed parameter never masquerades as
    the declaration's own name.
    """
    if node.type == "function_declarator":
        return node
    for child in node.named_children:
        if child.type == "parameter_list":
            continue
        found = _find_function_declarator(child)
        if found is not None:
            return found
    return None


def _function_name(node: "Node") -> str | None:
    """The name of the function a declaration/definition introduces, or ``None``."""
    func_decl = _find_function_declarator(node)
    if func_decl is None:
        return None
    return _name_of(func_decl.child_by_field_name("declarator"))


def _is_doc_comment(node: "Node | None", target_row: int, source: bytes) -> bool:
    """True if *node* is a Doxygen doc comment sitting just above *target_row*.

    "Just above" means the comment ends on the line immediately preceding the
    declaration (or on the same line — a trailing ``///<`` style), so an
    unrelated comment separated by blank lines does not count.
    """
    if node is None or node.type != "comment":
        return False
    text = _text(node, source).lstrip()
    if not text.startswith(_DOC_COMMENT_PREFIXES):
        return False
    return target_row - node.end_point[0] <= 1


def _class_units(
    spec: "Node",
    node_for_comment: "Node",
    kind: str,
    prev: "Node | None",
    rel: str,
    source: bytes,
    drift: bool,
    tokens: set[str],
) -> list[DocUnit]:
    """Emit the class/struct unit plus its public method units.

    Access defaults follow C++: a ``class`` starts private, a ``struct`` starts
    public; each ``public:``/``private:``/``protected:`` label flips the current
    visibility for the members that follow.
    """
    name = _name_of(spec.child_by_field_name("name"))
    if name is None:
        return []  # anonymous class/struct — nothing a doc could name

    def make(kind_: str, name_: str, lineno: int, has_doc: bool) -> DocUnit:
        return DocUnit(
            file=rel,
            kind=kind_,
            name=name_,
            lineno=lineno,
            has_docstring=has_doc,
            drift_match=drift,
            mention=name_ in tokens,
        )

    units = [
        make(
            kind,
            name,
            spec.start_point[0] + 1,
            _is_doc_comment(prev, node_for_comment.start_point[0], source),
        )
    ]

    body = spec.child_by_field_name("body")
    if body is None:
        return units

    access = "public" if kind == "struct" else "private"
    member_prev: "Node | None" = None
    for child in body.named_children:
        if child.type == "access_specifier":
            label = _text(child, source).strip().rstrip(":").strip()
            access = label or access
            member_prev = child
            continue
        if child.type in ("field_declaration", "function_definition"):
            fname = _function_name(child)
            if fname is not None and access == "public":
                units.append(
                    make(
                        "method",
                        fname,
                        child.start_point[0] + 1,
                        _is_doc_comment(member_prev, child.start_point[0], source),
                    )
                )
        member_prev = child
    return units


def _walk_container(
    container: "Node",
    rel: str,
    source: bytes,
    drift: bool,
    tokens: set[str],
) -> list[DocUnit]:
    """Enumerate public declarations directly under *container*.

    Recurses into ``namespace``/``linkage`` bodies so a function inside
    ``namespace foo { ... }`` is enumerated at its true name.
    """

    def make(kind: str, name: str, lineno: int, has_doc: bool) -> DocUnit:
        return DocUnit(
            file=rel,
            kind=kind,
            name=name,
            lineno=lineno,
            has_docstring=has_doc,
            drift_match=drift,
            mention=name in tokens,
        )

    units: list[DocUnit] = []
    prev: "Node | None" = None
    for child in container.named_children:
        if child.type in ("namespace_definition", "linkage_specification"):
            body = child.child_by_field_name("body")
            if body is not None:
                units.extend(_walk_container(body, rel, source, drift, tokens))
        elif child.type in ("class_specifier", "struct_specifier"):
            kind = "struct" if child.type == "struct_specifier" else "class"
            units.extend(
                _class_units(child, child, kind, prev, rel, source, drift, tokens)
            )
        elif child.type == "declaration":
            spec = next(
                (
                    c
                    for c in child.named_children
                    if c.type in ("class_specifier", "struct_specifier")
                ),
                None,
            )
            if spec is not None:
                kind = "struct" if spec.type == "struct_specifier" else "class"
                units.extend(
                    _class_units(spec, child, kind, prev, rel, source, drift, tokens)
                )
            else:
                fname = _function_name(child)
                if fname is not None:
                    units.append(
                        make(
                            "function",
                            fname,
                            child.start_point[0] + 1,
                            _is_doc_comment(prev, child.start_point[0], source),
                        )
                    )
        elif child.type == "function_definition":
            fname = _function_name(child)
            if fname is not None:
                units.append(
                    make(
                        "function",
                        fname,
                        child.start_point[0] + 1,
                        _is_doc_comment(prev, child.start_point[0], source),
                    )
                )
        prev = child
    return units


def cpp_units_for_file(
    rel: str, source: bytes, drift: bool, tokens: set[str]
) -> list[DocUnit]:
    """Enumerate the public C++ units in *source* (bytes), or ``[]`` if degraded.

    Returns zero units — without raising — when the grammar is unavailable
    (:func:`_get_cpp_parser` is ``None``) or the file fails to parse into a
    translation unit, so a misconfigured or grammar-less repo degrades to a
    no-op rather than a traceback. *drift* and *tokens* are the same
    caller-supplied OR-signals the Python path uses.
    """
    parser = _get_cpp_parser()
    if parser is None:
        return []
    tree = parser.parse(source)
    root = tree.root_node
    if root is None:
        return []
    return _walk_container(root, rel, source, drift, tokens)
