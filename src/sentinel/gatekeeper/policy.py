"""
Policy Engine for the Principled Gatekeeper.

Defines the :class:`Policy` class which holds thresholds and rules
that the :class:`~sentinel.gatekeeper.judge.GatekeeperJudge` enforces.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Policy:
    """
    Defines acceptable quality and security thresholds for a project.

    Attributes:
        max_complexity: Maximum allowed cyclomatic complexity for any
                        function.  Defaults to ``10``.
        allowed_fuzzer_crashes: Maximum number of fuzzer-detected crashes
                                that are tolerated.  Defaults to ``0``.
        forbidden_patterns: List of source-code patterns (plain strings)
                            that must not appear in the codebase.
                            Defaults to an empty list.
    """

    max_complexity: int = 10
    allowed_fuzzer_crashes: int = 0
    forbidden_patterns: List[str] = field(default_factory=list)
