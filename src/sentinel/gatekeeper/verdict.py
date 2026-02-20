"""
Verdict system for the Principled Gatekeeper.

Defines the :class:`Verdict` and :class:`Violation` data classes that
represent the outcome of a gatekeeper evaluation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class VerdictStatus(str, Enum):
    """Overall status of a gatekeeper evaluation."""

    PASS = "PASS"
    FAIL = "FAIL"


@dataclass
class Violation:
    """
    A single policy violation found during evaluation.

    Attributes:
        severity: How serious the violation is (e.g. ``"error"``,
                  ``"warning"``, ``"info"``).
        message: Human-readable description of the violation.
        context: Optional dictionary with additional structured details.
    """

    severity: str
    message: str
    context: Optional[Dict[str, Any]] = field(default=None)


@dataclass
class Verdict:
    """
    Final decision issued by the :class:`~sentinel.gatekeeper.judge.GatekeeperJudge`.

    Attributes:
        status: :attr:`VerdictStatus.PASS` when all policies are satisfied,
                :attr:`VerdictStatus.FAIL` otherwise.
        summary: One-line human-readable summary of the verdict.
        details: Full list of :class:`Violation` objects that informed the
                 decision.
    """

    status: VerdictStatus
    summary: str
    details: List[Violation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """``True`` when the verdict is :attr:`VerdictStatus.PASS`."""
        return self.status == VerdictStatus.PASS
