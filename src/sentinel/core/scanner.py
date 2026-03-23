"""
Code scanner for static analysis of Python, Java, and TypeScript source files.

Uses tree-sitter to parse source files and extract structural information
such as imports and function definitions.
"""

import re
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

def _make_language(raw, name: str) -> Language:
    """Return a Language instance from a raw capsule or an existing Language object.

    Handles multiple tree-sitter binding versions:
    - v0.22+: ``language()`` already returns a ``Language`` instance.
    - older:  ``Language(ptr)`` is required.
    - some:   ``Language(ptr, name)`` is required when name is missing.
    """
    if isinstance(raw, Language):
        return raw
    try:
        return Language(raw)
    except TypeError:
        return Language(raw, name)


_PY_LANGUAGE = _make_language(tspython.language(), "python")
_JAVA_LANGUAGE = _make_language(tsjava.language(), "java")
_TS_LANGUAGE = _make_language(tsts.language_typescript(), "typescript")
_TSX_LANGUAGE = _make_language(tsts.language_tsx(), "tsx")

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

    def find_todo_comments(self, file_content: str) -> List[str]:
        """
        Find TODO / FIXME / HACK / XXX marker comments in any source file.

        Uses a simple regex over the raw text so it works for Python, Java,
        and TypeScript without language-specific AST traversal.

        Args:
            file_content: Source code as a string.

        Returns:
            List of comment text snippets (stripped) that contain a marker.
        """
        pattern = re.compile(
            r'(?://|#)[^\n]*\b(TODO|FIXME|HACK|XXX)\b[^\n]*',
            re.IGNORECASE,
        )
        return [m.group(0).strip() for m in pattern.finditer(file_content)]

    def find_missing_docstrings(self, file_content: str) -> List[Dict]:
        """
        Identify public Python functions and classes that lack a docstring.

        Only top-level and class-level definitions are checked; private
        names (starting with ``_``) are skipped, except ``__init__``.

        Args:
            file_content: Python source code as a string.

        Returns:
            List of dicts with ``name`` and ``kind`` (``"function"`` or
            ``"class"``) for each definition missing a docstring.
        """
        tree = self._parsers[".py"].parse(file_content.encode())
        missing: List[Dict] = []
        self._collect_missing_docstrings(tree.root_node, missing, inside_function=False)
        return missing

    def find_public_fields(self, file_content: str) -> List[str]:
        """
        Find non-constant public instance fields in Java source code.

        Lines matching ``public <Type> <fieldName>;`` that are *not*
        ``public static final`` (constants) are flagged.

        Args:
            file_content: Java source code as a string.

        Returns:
            List of field names that violate the encapsulation rule.
        """
        pattern = re.compile(
            r'^\s+public\s+(?!static\s+final\b|final\s+static\b|abstract\b|'
            r'class\b|interface\b|enum\b|void\b|@)'
            r'[\w<>\[\]]+\s+([a-z][a-zA-Z0-9_]*)\s*;',
            re.MULTILINE,
        )
        return [m.group(1) for m in pattern.finditer(file_content)]

    def find_missing_javadoc(self, file_content: str) -> List[str]:
        """
        Find Java public class / interface / enum declarations without Javadoc.

        A declaration is considered documented when the closest non-blank
        line above it ends with ``*/`` (closing a block comment).

        Args:
            file_content: Java source code as a string.

        Returns:
            List of type names whose declarations lack a Javadoc comment.
        """
        missing: List[str] = []
        lines = file_content.split("\n")
        decl_re = re.compile(
            r'\bpublic\b.*\b(?:class|interface|enum)\s+(\w+)'
        )
        for i, line in enumerate(lines):
            m = decl_re.search(line)
            if not m:
                continue
            j = i - 1
            while j >= 0 and lines[j].strip() == "":
                j -= 1
            prev = lines[j].strip() if j >= 0 else ""
            if not prev.endswith("*/"):
                missing.append(m.group(1))
        return missing

    def find_java_naming_violations(self, file_content: str) -> List[str]:
        """
        Detect Java naming-convention violations.

        * Types (class / interface / enum) must start with an uppercase letter
          (PascalCase).
        * Methods must start with a lowercase letter (camelCase) – only
          ``public`` / ``protected`` / ``private`` methods are checked.

        Args:
            file_content: Java source code as a string.

        Returns:
            List of human-readable violation descriptions.
        """
        violations: List[str] = []
        # Type names must be PascalCase
        for m in re.finditer(
            r'\b(?:class|interface|enum)\s+([a-z][a-zA-Z0-9_]*)', file_content
        ):
            violations.append(
                f"Type '{m.group(1)}' should be PascalCase"
            )
        # Method names must be camelCase (starts with lowercase)
        for m in re.finditer(
            r'\b(?:public|protected|private)\b[^(;{]*\s+([A-Z][a-zA-Z0-9_]*)\s*\(',
            file_content,
        ):
            name = m.group(1)
            # Ignore constructors (same name as class – already caught above if needed)
            if not re.search(
                r'\bclass\s+' + re.escape(name) + r'\b', file_content
            ):
                violations.append(
                    f"Method '{name}' should start with a lowercase letter (camelCase)"
                )
        return violations

    def find_unsafe_type_assertions(
        self, file_content: str, file_ext: str = ".ts"
    ) -> List[str]:
        """
        Find TypeScript ``as any`` unsafe type-assertion expressions.

        Args:
            file_content: TypeScript or TSX source code.
            file_ext: File extension (unused; kept for API symmetry).

        Returns:
            List of ``"as any"`` strings, one per occurrence found.
        """
        pattern = re.compile(r'\bas\s+any\b')
        return [m.group(0) for m in pattern.finditer(file_content)]

    def find_console_logs(
        self, file_content: str, file_ext: str = ".ts"
    ) -> List[str]:
        """
        Find ``console.log / .warn / .error / .debug`` calls in TypeScript.

        Args:
            file_content: TypeScript or TSX source code.
            file_ext: File extension (unused; kept for API symmetry).

        Returns:
            List of matched call prefixes (e.g. ``"console.log("``).
        """
        pattern = re.compile(r'console\.(log|warn|error|debug)\s*\(')
        return [m.group(0) for m in pattern.finditer(file_content)]

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

    def _collect_missing_docstrings(
        self, node: Node, missing: List[Dict], inside_function: bool
    ) -> None:
        """
        Traverse the AST and collect function / class definitions missing docstrings.

        Only top-level and class-member definitions are reported.  Private
        names (single leading ``_``) are skipped; dunder names are skipped
        except for ``__init__``.

        Args:
            node: Current AST node.
            missing: Accumulator list.
            inside_function: True when we are already inside a function body
                             (inner functions are skipped to avoid noise).
        """
        if node.type in ("function_definition", "class_definition"):
            name_node = node.child_by_field_name("name")
            body_node = node.child_by_field_name("body")
            name = name_node.text.decode() if name_node else "<unknown>"

            # Skip private names (but allow __init__)
            if name.startswith("_") and name != "__init__":
                # Still recurse into class bodies even for private classes
                if node.type == "class_definition" and body_node:
                    for child in body_node.children:
                        self._collect_missing_docstrings(child, missing, False)
                return

            # Skip nested functions (only check top-level / class-level)
            if inside_function and node.type == "function_definition":
                return

            has_docstring = False
            if body_node:
                for child in body_node.children:
                    if child.type == "comment":
                        continue
                    if child.type == "expression_statement":
                        for gc in child.children:
                            if gc.type == "string":
                                has_docstring = True
                                break
                    break  # only inspect the first non-comment statement

            if not has_docstring:
                kind = "function" if node.type == "function_definition" else "class"
                missing.append({"name": name, "kind": kind})

            # Recurse into class body to catch method-level docstrings
            if node.type == "class_definition" and body_node:
                for child in body_node.children:
                    self._collect_missing_docstrings(child, missing, False)
            elif node.type == "function_definition" and body_node:
                for child in body_node.children:
                    self._collect_missing_docstrings(child, missing, True)
            return

        for child in node.children:
            self._collect_missing_docstrings(child, missing, inside_function)

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
