"""
Gatekeeper module for Sentinel.

The Principled Gatekeeper is the executive decision-maker that aggregates
intelligence from the Historian, Guardian, Fuzzer, and Sandbox pillars to
render a final verdict on code changes.

Public API::

    from sentinel.gatekeeper import Gatekeeper, Verdict
    from sentinel.gatekeeper import (
        NoCriticalBugsPolicy,
        ArchitectureCompliancePolicy,
        TestPassPolicy,
        PolicyConfig,
    )
"""

from .judge import Gatekeeper
from .policy import (
    ArchitectureCompliancePolicy,
    NoCriticalBugsPolicy,
    Policy,
    PolicyConfig,
    TestPassPolicy,
)
from .verdict import Verdict

__all__ = [
    "ArchitectureCompliancePolicy",
    "Gatekeeper",
    "NoCriticalBugsPolicy",
    "Policy",
    "PolicyConfig",
    "TestPassPolicy",
    "Verdict",
]
