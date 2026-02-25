"""
Code scanner for static analysis of Python, Java, and TypeScript source files.

Uses tree-sitter to parse source files and extract structural information
such as imports and function definitions.
"""

from typing import Dict, List

import tree_sitter_java as tsjava
import tree_sitter_python as tspython
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

# Branch node types used for cyclomatic complexity calculation
_BRANCH_TYPES = frozenset(
    {
        "if_statement",
        "elif_clause",
        "else_clause",
        "for_statement",
        "while_statement",
        "try_statement",
        "except_clause",
        "with_statement",
        "conditional_expression",
        "boolean_operator",
    }
)

def _make_language(raw) -> Language:
    """Return a Language instance from a raw capsule or an existing Language object."""
    return raw if isinstance(raw, Language) else Language(raw)


_PY_LANGUAGE = _make_language(tspython.language())
_JAVA_LANGUAGE = _make_language(tsjava.language())
_TS_LANGUAGE = _make_language(tsts.language_typescript())
_TSX_LANGUAGE = _make_language(tsts.language_tsx())

# Maps file extension to tree-sitter Language object
_LANGUAGE_MAP: Dict[str, Language] = {
    ".py": _PY_LANGUAGE,
    ".java": _JAVA_LANGUAGE,
    ".ts": _TS_LANGUAGE,
    ".tsx": _TSX_LANGUAGE,
}


class CodeScanner:
    """
    Static analyzer for Python, Java, and TypeScript/TSX source files.

    Uses tree-sitter to build an AST and extract dependency and
    structural information without executing the code.
    """

    def __init__(self):
        """Initialize the CodeScanner with tree-sitter parsers for each supported language."""
        self._parsers: Dict[str, Parser] = {
            ext: Parser(lang) for ext, lang in _LANGUAGE_MAP.items()
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_imports(self, file_content: str, file_ext: str = ".py") -> List[str]:
        """
        Extract all imported module names from source code.

        For Python, handles both ``import X`` and ``from X import Y`` forms
        and returns the module path (e.g. ``sentinel.core.scanner``).

        For Java, returns the fully-qualified class name from each
        ``import`` declaration (e.g. ``com.example.Foo``).

        For TypeScript/TSX, returns the module specifier string from each
        ``import … from '…'`` statement (e.g. ``./bar``).

        Args:
            file_content: Source code as a string.
            file_ext: File extension used to select the parser and
                      collection strategy (default: ``".py"``).

        Returns:
            List of imported module/class name strings (may contain
            duplicates if the same module is imported multiple times).
        """
        parser = self._parsers.get(file_ext, self._parsers[".py"])
        tree = parser.parse(file_content.encode())
        imports: List[str] = []
        if file_ext == ".java":
            self._collect_java_imports(tree.root_node, imports)
        elif file_ext in (".ts", ".tsx"):
            self._collect_ts_imports(tree.root_node, imports)
        else:
            self._collect_imports(tree.root_node, imports)
        return imports

    def find_any_usages(self, file_content: str, file_ext: str = ".ts") -> List[str]:
        """
        Detect usages of the ``any`` type in TypeScript or TSX source code.

        Scans the AST for ``predefined_type`` nodes whose text is ``any``,
        which covers annotations such as ``let x: any`` and
        ``function f(a: any)``.

        Args:
            file_content: TypeScript or TSX source code as a string.
            file_ext: File extension used to select the parser
                      (``".ts"`` or ``".tsx"``; default: ``".ts"``).

        Returns:
            List of ``"any"`` strings, one per occurrence found in the
            source (length equals the number of ``any`` type usages).
        """
        parser = self._parsers.get(file_ext, self._parsers[".ts"])
        tree = parser.parse(file_content.encode())
        usages: List[str] = []
        self._collect_any_usages(tree.root_node, usages)
        return usages

    def get_functions(self, file_content: str) -> List[Dict]:
        """
        Extract function signatures and complexity metrics from Python source.

        Only top-level and class-level ``def`` statements are returned;
        nested functions defined inside another function are excluded.

        Args:
            file_content: Python source code as a string.

        Returns:
            List of dictionaries, each containing:
              - ``name`` (str): Function name.
              - ``params`` (str): Parameter list as written in the source,
                including parentheses (e.g. ``"(x, y)"``).
              - ``complexity`` (int): Approximate cyclomatic complexity
                (number of branch points + 1).
        """
        tree = self._parsers[".py"].parse(file_content.encode())
        functions: List[Dict] = []
        self._collect_functions(tree.root_node, functions, nested=False)
        return functions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _collect_java_imports(self, node: Node, imports: List[str]) -> None:
        """Recursively traverse the AST and collect Java import declarations."""
        if node.type == "import_declaration":
            for child in node.children:
                if child.type in ("scoped_identifier", "identifier"):
                    imports.append(child.text.decode())
        else:
            for child in node.children:
                self._collect_java_imports(child, imports)

    def _collect_ts_imports(self, node: Node, imports: List[str]) -> None:
        """Recursively traverse the AST and collect TypeScript import module paths."""
        if node.type == "import_statement":
            for child in node.children:
                if child.type == "string":
                    # Strip surrounding quotes from the module specifier
                    module = child.text.decode()[1:-1]
                    imports.append(module)
        else:
            for child in node.children:
                self._collect_ts_imports(child, imports)

    def _collect_any_usages(self, node: Node, usages: List[str]) -> None:
        """Recursively traverse the AST and collect ``any`` predefined-type nodes."""
        if node.type == "predefined_type" and node.text == b"any":
            usages.append(node.text.decode())
        for child in node.children:
            self._collect_any_usages(child, usages)

    def _collect_imports(self, node: Node, imports: List[str]) -> None:
        """Recursively traverse the AST and collect import module names."""
        if node.type == "import_statement":
            # import os  /  import os.path  /  import a, b
            for child in node.children:
                if child.type in ("dotted_name", "aliased_import"):
                    # For `import a as b`, dotted_name is the first named child
                    name_node = (
                        child.child_by_field_name("name")
                        if child.type == "aliased_import"
                        else child
                    )
                    if name_node:
                        imports.append(name_node.text.decode())

        elif node.type == "import_from_statement":
            # from pathlib import Path  /  from . import foo
            module_node = node.child_by_field_name("module_name")
            if module_node:
                imports.append(module_node.text.decode())

        else:
            for child in node.children:
                self._collect_imports(child, imports)

    def _collect_functions(
        self, node: Node, functions: List[Dict], nested: bool
    ) -> None:
        """
        Recursively collect function definitions from the AST.

        Args:
            node: Current AST node.
            functions: Accumulator list for found function dicts.
            nested: When True the current node is already inside a
                    function body, so inner ``def`` statements are
                    skipped (not collected but their children are still
                    visited for complexity counting purposes).
        """
        if node.type == "function_definition":
            name_node = node.child_by_field_name("name")
            params_node = node.child_by_field_name("parameters")
            body_node = node.child_by_field_name("body")

            name = name_node.text.decode() if name_node else "<unknown>"
            params = params_node.text.decode() if params_node else "()"
            complexity = (
                self._count_complexity(body_node) + 1 if body_node else 1
            )

            if not nested:
                functions.append(
                    {"name": name, "params": params, "complexity": complexity}
                )

            # Visit body for nested functions (but mark them as nested)
            if body_node:
                for child in body_node.children:
                    self._collect_functions(child, functions, nested=True)
            return

        for child in node.children:
            self._collect_functions(child, functions, nested=nested)

    def _count_complexity(self, node: Node) -> int:
        """
        Count branch-contributing nodes within a subtree.

        Args:
            node: Root of the subtree to analyse.

        Returns:
            Total count of branch node types found.
        """
        count = 0
        if node.type in _BRANCH_TYPES:
            count += 1
        for child in node.children:
            count += self._count_complexity(child)
        return count
