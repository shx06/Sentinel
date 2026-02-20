"""
Verdict data class for the Principled Gatekeeper.

Represents the final decision rendered by the :class:`~sentinel.gatekeeper.judge.Gatekeeper`
after evaluating all pillar reports.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Verdict:
    """
    Final decision produced by the Gatekeeper.

    Attributes:
        approved: ``True`` when the code change passed all enabled policies.
        confidence: Confidence score between ``0.0`` (no confidence) and
                    ``1.0`` (fully confident).
        summary: Short executive summary of the decision.
        blocking_issues: Reasons why the change was rejected (non-empty only
                         when *approved* is ``False``).
        warnings: Non-blocking issues that should be reviewed but do not
                  prevent approval.
    """

    approved: bool
    confidence: float
    summary: str
    blocking_issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
