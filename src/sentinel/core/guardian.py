"""
Architectural Guardian: analyzes project structure and enforces rules.

Scans a directory tree for Python, Java, and TypeScript source files,
builds a dependency graph using :class:`~sentinel.core.scanner.CodeScanner`,
and validates the graph against a set of :class:`~sentinel.core.rules.Rule`
instances.
"""

import os
from typing import Dict, List

from .rules import Rule
from .scanner import CodeScanner

# File extensions that the Guardian will scan
_SUPPORTED_EXTENSIONS = frozenset({".py", ".java", ".ts", ".tsx"})

# Default max lines per function before flagging it
_DEFAULT_MAX_FUNCTION_LINES = 50


class ArchitecturalGuardian:
    """
    High-level façade for the Architectural Guardian pillar.

    Combines :class:`CodeScanner` and the rule engine to provide a simple
    two-step API:

    1. :meth:`analyze_structure` – walk a directory, parse every Python file,
       and build an in-memory dependency graph.
    2. :meth:`check_rules` – validate the graph against a list of
       :class:`~sentinel.core.rules.Rule` objects and return all violations.
    """

    def __init__(self):
        """Initialize the ArchitecturalGuardian with a fresh CodeScanner."""
        self._scanner = CodeScanner()
        self.graph: Dict = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze_structure(self, path: str) -> Dict:
        """
        Scan all supported source files under *path* and build a dependency graph.

        Supported file types: ``.py``, ``.java``, ``.ts``, ``.tsx``.

        Each entry in the returned graph is keyed by the absolute file path
        and contains:

        * ``imports`` – list of module/class names imported by the file.
        * ``functions`` – list of function info dicts (name, params,
          complexity); populated for Python files only.
        * ``module_name`` – dotted module name derived from the file's
          path relative to the package root (Python files) or a
          simplified path-based name (Java/TypeScript files).
        * ``violations`` – list of pre-generated violation messages for
          Java import layering and TypeScript ``any``-type usage.

        Args:
            path: Root directory to scan.  All supported source files found
                  recursively are analyzed.

        Returns:
            The dependency graph dictionary (also stored on
            ``self.graph`` for subsequent :meth:`check_rules` calls).
        """
        graph: Dict = {}
        root = os.path.abspath(path)

        # Collect all supported source files
        source_files: List[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                ext = os.path.splitext(filename)[1]
                if ext in _SUPPORTED_EXTENSIONS:
                    source_files.append(os.path.join(dirpath, filename))

        # Determine the package root for Python module-name derivation
        py_files = [f for f in source_files if f.endswith(".py")]
        package_root = self._find_package_root(root, py_files)

        for file_path in source_files:
            try:
                with open(file_path, encoding="utf-8") as fh:
                    content = fh.read()
            except OSError:
                continue

            ext = os.path.splitext(file_path)[1]
            filename = os.path.basename(file_path)
            violations: List[str] = []

            raw_imports = self._scanner.find_imports(content, ext)

            if ext == ".py":
                functions = self._scanner.get_functions(content)
                module_name = self._derive_module_name(file_path, package_root)
                imports = self._resolve_imports(raw_imports, module_name)

                # --- Python-specific violation checks ---

                # TODO / FIXME markers
                for comment in self._scanner.find_todo_comments(content):
                    violations.append(
                        f"[TODO] TODO/FIXME comment in '{filename}': {comment}"
                    )

                # Missing docstrings on public functions / classes
                for item in self._scanner.find_missing_docstrings(content):
                    violations.append(
                        f"[DOCSTRING] Missing docstring in "
                        f"'{module_name}::{item['name']}' ({item['kind']})"
                    )

                # Overly long functions (line-count proxy via start/end_point)
                tree_py = self._scanner._parsers[".py"].parse(content.encode())
                self._collect_long_functions(
                    tree_py.root_node, violations, filename, module_name
                )

            else:
                functions = []
                # Use a simplified path-based identifier for non-Python files
                try:
                    module_name = os.path.relpath(file_path, root)
                except ValueError:
                    module_name = file_path
                imports = raw_imports

                if ext == ".java":
                    # --- Java layering: emit per-import violation ---
                    for fq_name in imports:
                        parts = fq_name.split(".")
                        if parts and parts[-1] and parts[-1][0].islower() and len(parts) >= 2:
                            class_name = parts[-2]
                        else:
                            class_name = parts[-1]
                        violations.append(
                            f"Import of '{class_name}' in '{filename}'"
                        )

                    # --- Java-specific violation checks ---
                    for field in self._scanner.find_public_fields(content):
                        violations.append(
                            f"[PUBLIC_FIELD] Public non-constant field "
                            f"'{field}' in '{filename}'"
                        )

                    for type_name in self._scanner.find_missing_javadoc(content):
                        violations.append(
                            f"[JAVADOC] Missing Javadoc for class "
                            f"'{type_name}' in '{filename}'"
                        )

                    for naming_v in self._scanner.find_java_naming_violations(content):
                        violations.append(
                            f"[NAMING] {naming_v} in '{filename}'"
                        )

                    # TODO markers in Java (// TODO …)
                    for comment in self._scanner.find_todo_comments(content):
                        violations.append(
                            f"[TODO] TODO/FIXME comment in '{filename}': {comment}"
                        )

                elif ext in (".ts", ".tsx"):
                    # --- TypeScript: any-type usage ---
                    any_usages = self._scanner.find_any_usages(content, ext)
                    if any_usages:
                        try:
                            rel_path = os.path.relpath(file_path, root)
                        except ValueError:
                            rel_path = file_path
                        violations.append(
                            f"Found usage of 'any' in {rel_path}"
                        )

                    # --- TypeScript-specific violation checks ---
                    try:
                        rel_path = os.path.relpath(file_path, root)
                    except ValueError:
                        rel_path = file_path

                    for _ in self._scanner.find_unsafe_type_assertions(content, ext):
                        violations.append(
                            f"[UNSAFE_CAST] Unsafe 'as any' assertion in '{rel_path}'"
                        )
                        break  # one violation per file is enough to flag it

                    if self._scanner.find_console_logs(content, ext):
                        violations.append(
                            f"[CONSOLE_LOG] console.log() usage in '{rel_path}'"
                        )

                    # TODO markers in TypeScript
                    for comment in self._scanner.find_todo_comments(content):
                        violations.append(
                            f"[TODO] TODO/FIXME comment in '{filename}': {comment}"
                        )

            graph[file_path] = {
                "imports": imports,
                "functions": functions,
                "module_name": module_name,
                "violations": violations,
            }

        self.graph = graph
        return graph

    def check_rules(self, rules: List[Rule]) -> List[str]:
        """
        Validate the current dependency graph against a list of rules.

        :meth:`analyze_structure` must be called before this method so
        that ``self.graph`` is populated.

        In addition to rule-generated violations, any pre-generated
        ``violations`` stored per file during :meth:`analyze_structure`
        (e.g. Java import layering messages and TypeScript ``any``-usage
        messages) are included in the returned list.

        Args:
            rules: List of :class:`~sentinel.core.rules.Rule` instances
                   to evaluate.

        Returns:
            Combined list of violation messages from all rules and
            file-level pre-generated violations.  An empty list indicates
            no violations were found.
        """
        violations: List[str] = []
        # Include pre-generated file-level violations (Java/TS)
        for info in self.graph.values():
            violations.extend(info.get("violations", []))
        for rule in rules:
            violations.extend(rule.check(self.graph))
        return violations

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_imports(
        raw_imports: List[str], module_name: str
    ) -> List[str]:
        """
        Resolve relative imports to absolute module names.

        Args:
            raw_imports: Import strings from the scanner (may include
                         relative forms such as ``.rules`` or ``..utils``).
            module_name: Dotted module name of the file being processed.

        Returns:
            List of imports with relative forms converted to absolute names.
        """
        resolved: List[str] = []
        # Package of the current module (everything before the last dot)
        parts = module_name.split(".") if module_name else []
        package_parts = parts[:-1] if len(parts) > 1 else parts

        for imp in raw_imports:
            if imp.startswith("."):
                # Count leading dots to determine how many levels to go up
                level = 0
                while level < len(imp) and imp[level] == ".":
                    level += 1
                relative_name = imp[level:]  # module name after the dots

                # Go up (level - 1) levels from the current package
                base_parts = package_parts[: len(package_parts) - (level - 1)]
                if relative_name:
                    resolved_parts = base_parts + [relative_name]
                else:
                    resolved_parts = base_parts
                resolved.append(".".join(resolved_parts))
            else:
                resolved.append(imp)
        return resolved

    @staticmethod
    def _find_package_root(root: str, py_files: List[str]) -> str:
        """
        Find the highest directory that acts as the package root.

        The package root is the deepest ancestor of *root* that still
        contains an ``__init__.py`` file.  If no such directory can be
        determined the scan root itself is returned.

        Args:
            root: The directory passed to :meth:`analyze_structure`.
            py_files: All Python files discovered under *root*.

        Returns:
            Absolute path to the package root directory.
        """
        # Collect all directories that contain __init__.py
        init_dirs: List[str] = []
        for fp in py_files:
            dirname = os.path.dirname(fp)
            if os.path.basename(fp) == "__init__.py":
                init_dirs.append(dirname)

        if not init_dirs:
            return root

        # Walk up from *root* until we leave the chain of __init__.py dirs
        candidate = root
        while True:
            parent = os.path.dirname(candidate)
            if parent == candidate:
                break
            if os.path.isfile(os.path.join(parent, "__init__.py")):
                candidate = parent
            else:
                break
        return candidate

    @staticmethod
    def _derive_module_name(file_path: str, package_root: str) -> str:
        """
        Convert a file path to a dotted Python module name.

        For example, given ``package_root=/src`` and
        ``file_path=/src/sentinel/core/scanner.py``, the result is
        ``sentinel.core.scanner``.

        Args:
            file_path: Absolute path to the Python source file.
            package_root: Absolute path to the package root directory.

        Returns:
            Dotted module name string, or an empty string if the path
            cannot be made relative to *package_root*.
        """
        try:
            rel = os.path.relpath(file_path, package_root)
        except ValueError:
            return ""

        # Strip .py extension and replace path separators with dots
        if rel.endswith(".py"):
            rel = rel[:-3]
        module_name = rel.replace(os.sep, ".")

        # Drop trailing __init__ component
        if module_name.endswith(".__init__"):
            module_name = module_name[: -len(".__init__")]
        elif module_name == "__init__":
            module_name = ""

        return module_name

    @staticmethod
    def _collect_long_functions(
        node: object,
        violations: List[str],
        filename: str,
        module_name: str,
        max_lines: int = _DEFAULT_MAX_FUNCTION_LINES,
    ) -> None:
        """
        Walk a tree-sitter AST and emit violations for overly long functions.

        Args:
            node: Root AST node (tree-sitter ``Node``).
            violations: Accumulator list for violation strings.
            filename: Base file name used in violation messages.
            module_name: Dotted module name used in violation messages.
            max_lines: Maximum allowed line count per function.
        """
        if node.type == "function_definition":  # type: ignore[attr-defined]
            name_node = node.child_by_field_name("name")  # type: ignore[attr-defined]
            name = name_node.text.decode() if name_node else "<unknown>"
            start_line = node.start_point[0]  # type: ignore[attr-defined]
            end_line = node.end_point[0]  # type: ignore[attr-defined]
            line_count = end_line - start_line + 1
            if line_count > max_lines:
                violations.append(
                    f"[LONG_FUNCTION] Function '{module_name}::{name}' in "
                    f"'{filename}' is {line_count} lines long "
                    f"(max allowed: {max_lines})"
                )
        for child in node.children:  # type: ignore[attr-defined]
            ArchitecturalGuardian._collect_long_functions(
                child, violations, filename, module_name, max_lines
            )
