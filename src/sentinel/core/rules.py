"""
Rule engine for architectural analysis.

Provides an abstract ``Rule`` base class and concrete rule implementations
that validate a dependency graph produced by :class:`ArchitecturalGuardian`.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Set

# Default maximum cyclomatic complexity before a violation is raised
DEFAULT_MAX_COMPLEXITY = 10


class Rule(ABC):
    """
    Abstract base class for all architectural rules.

    Subclasses must implement :meth:`check`, which receives the dependency
    graph built by :class:`~sentinel.core.guardian.ArchitecturalGuardian`
    and returns a (possibly empty) list of human-readable violation messages.
    """

    @abstractmethod
    def check(self, graph: Dict) -> List[str]:
        """
        Validate the dependency graph against this rule.

        Args:
            graph: Dependency graph as returned by
                   ``ArchitecturalGuardian.analyze_structure``.

        Returns:
            List of violation messages.  An empty list means no violations.
        """


class NoCircularDependenciesRule(Rule):
    """
    Rule that detects circular import dependencies between project modules.

    Only intra-project imports are considered (i.e. imports that resolve to
    another file found in the scanned path).  Standard-library and
    third-party imports are ignored.
    """

    def check(self, graph: Dict) -> List[str]:
        """
        Check for circular dependencies in the dependency graph.

        Args:
            graph: Mapping of ``file_path -> {"imports": [...], ...}``
                   as produced by ``ArchitecturalGuardian.analyze_structure``.

        Returns:
            List of violation messages describing each detected cycle.
        """
        # Build a module-name -> file-path lookup so we can resolve imports
        # to concrete project files.
        module_to_file: Dict[str, str] = {}
        for file_path, info in graph.items():
            module_name = info.get("module_name", "")
            if module_name:
                module_to_file[module_name] = file_path

        # Build an adjacency list: file_path -> {file_path, ...}
        adjacency: Dict[str, Set[str]] = {fp: set() for fp in graph}
        for file_path, info in graph.items():
            for imp in info.get("imports", []):
                # Try exact match first, then prefix match for sub-imports
                resolved = module_to_file.get(imp)
                if resolved is None:
                    for mod, fp in module_to_file.items():
                        if imp.startswith(mod + ".") or mod.startswith(
                            imp + "."
                        ):
                            resolved = fp
                            break
                if resolved and resolved != file_path:
                    adjacency[file_path].add(resolved)

        # DFS-based cycle detection
        violations: List[str] = []
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        reported_cycles: Set[frozenset] = set()

        def dfs(node: str, path: List[str]) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbour in adjacency.get(node, set()):
                if neighbour not in visited:
                    dfs(neighbour, path)
                elif neighbour in rec_stack:
                    # Found a cycle – extract the cycle portion of the path
                    cycle_start = path.index(neighbour)
                    cycle = path[cycle_start:]
                    cycle_key = frozenset(cycle)
                    if cycle_key not in reported_cycles:
                        reported_cycles.add(cycle_key)
                        cycle_str = " -> ".join(cycle) + f" -> {neighbour}"
                        violations.append(
                            f"Circular dependency detected: {cycle_str}"
                        )

            path.pop()
            rec_stack.discard(node)

        for file_path in graph:
            if file_path not in visited:
                dfs(file_path, [])

        return violations


class FunctionComplexityRule(Rule):
    """
    Rule that flags functions whose cyclomatic complexity exceeds a threshold.

    Complexity is approximated as the number of branching constructs
    (``if``, ``elif``, ``else``, ``for``, ``while``, ``try``, ``except``,
    ``with``, ternary expressions, and boolean operators) plus one.
    """

    def __init__(self, max_complexity: int = DEFAULT_MAX_COMPLEXITY):
        """
        Initialize the rule.

        Args:
            max_complexity: Maximum allowed complexity (inclusive).
                            Functions with a higher complexity value will
                            be reported as violations.
        """
        self.max_complexity = max_complexity

    def check(self, graph: Dict) -> List[str]:
        """
        Check all functions in the graph for excessive complexity.

        Args:
            graph: Mapping of ``file_path -> {"functions": [...], ...}``
                   as produced by ``ArchitecturalGuardian.analyze_structure``.

        Returns:
            List of violation messages for functions exceeding the threshold.
        """
        violations: List[str] = []
        for file_path, info in graph.items():
            for func in info.get("functions", []):
                complexity = func.get("complexity", 1)
                if complexity > self.max_complexity:
                    violations.append(
                        f"{file_path}::{func['name']} has complexity "
                        f"{complexity} (max allowed: {self.max_complexity})"
                    )
        return violations
