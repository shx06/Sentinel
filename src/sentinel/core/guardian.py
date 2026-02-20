"""
Architectural Guardian: analyzes project structure and enforces rules.

Scans a directory tree for Python source files, builds a dependency graph
using :class:`~sentinel.core.scanner.CodeScanner`, and validates the graph
against a set of :class:`~sentinel.core.rules.Rule` instances.
"""

import os
from typing import Dict, List

from .rules import Rule
from .scanner import CodeScanner


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
        Scan all Python files under *path* and build a dependency graph.

        Each entry in the returned graph is keyed by the absolute file path
        and contains:

        * ``imports`` – list of module names imported by the file.
        * ``functions`` – list of function info dicts (name, params,
          complexity) as returned by
          :meth:`~sentinel.core.scanner.CodeScanner.get_functions`.
        * ``module_name`` – dotted module name derived from the file's
          path relative to the package root (used for intra-project
          dependency resolution).

        Args:
            path: Root directory to scan.  All ``.py`` files found
                  recursively are analyzed.

        Returns:
            The dependency graph dictionary (also stored on
            ``self.graph`` for subsequent :meth:`check_rules` calls).
        """
        graph: Dict = {}
        root = os.path.abspath(path)

        # Collect all .py files
        py_files: List[str] = []
        for dirpath, _dirnames, filenames in os.walk(root):
            for filename in filenames:
                if filename.endswith(".py"):
                    py_files.append(os.path.join(dirpath, filename))

        # Determine the package root (highest directory containing __init__.py)
        package_root = self._find_package_root(root, py_files)

        for file_path in py_files:
            try:
                with open(file_path, encoding="utf-8") as fh:
                    content = fh.read()
            except OSError:
                continue

            raw_imports = self._scanner.find_imports(content)
            functions = self._scanner.get_functions(content)
            module_name = self._derive_module_name(file_path, package_root)

            # Resolve relative imports to absolute module names
            imports = self._resolve_imports(raw_imports, module_name)

            graph[file_path] = {
                "imports": imports,
                "functions": functions,
                "module_name": module_name,
            }

        self.graph = graph
        return graph

    def check_rules(self, rules: List[Rule]) -> List[str]:
        """
        Validate the current dependency graph against a list of rules.

        :meth:`analyze_structure` must be called before this method so
        that ``self.graph`` is populated.

        Args:
            rules: List of :class:`~sentinel.core.rules.Rule` instances
                   to evaluate.

        Returns:
            Combined list of violation messages from all rules.  An empty
            list indicates no violations were found.
        """
        violations: List[str] = []
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
