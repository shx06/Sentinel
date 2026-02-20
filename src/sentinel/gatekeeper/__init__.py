"""
Gatekeeper module for Sentinel.

Acts as the executive decision-maker, enforcing quality standards and
security policies by aggregating intelligence from the other four pillars
(Historian, Guardian, Fuzzer, Sandbox) and issuing a final Verdict.

Public API::

    from sentinel.gatekeeper import GatekeeperJudge, Policy
    from sentinel.gatekeeper import Verdict, Violation, VerdictStatus
"""

from .judge import GatekeeperJudge
from .policy import Policy
from .verdict import Verdict, VerdictStatus, Violation

__all__ = [
    "GatekeeperJudge",
    "Policy",
    "Verdict",
    "VerdictStatus",
    "Violation",
]
