"""
Code scanner for static analysis of Python source files.

Uses tree-sitter to parse Python files and extract structural information
such as imports and function definitions.
"""

from typing import Dict, List

import tree_sitter_python as tspython
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

_PY_LANGUAGE = Language(tspython.language(), "python")


class CodeScanner:
    """
    Static analyzer for Python source files.

    Uses tree-sitter to build an AST and extract dependency and
    structural information without executing the code.
    """

    def __init__(self):
        """Initialize the CodeScanner with a tree-sitter Python parser."""
        self._parser = Parser(_PY_LANGUAGE)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def find_imports(self, file_content: str) -> List[str]:
        """
        Extract all imported module names from Python source code.

        Handles both ``import X`` and ``from X import Y`` forms.
        Returns the top-level module path being imported (e.g.
        ``sentinel.core.scanner`` for
        ``from sentinel.core.scanner import CodeScanner``).

        Args:
            file_content: Python source code as a string.

        Returns:
            List of imported module name strings (may contain duplicates
            if the same module is imported multiple times).
        """
        tree = self._parser.parse(file_content.encode())
        imports: List[str] = []
        self._collect_imports(tree.root_node, imports)
        return imports

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
        tree = self._parser.parse(file_content.encode())
        functions: List[Dict] = []
        self._collect_functions(tree.root_node, functions, nested=False)
        return functions

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
