"""
Gatekeeper module for Sentinel.

The Principled Gatekeeper is the executive decision-maker that aggregates
intelligence from the Historian, Guardian, Fuzzer, and Sandbox pillars to
render a final verdict on code changes.

Public API::

    from sentinel.gatekeeper import Gatekeeper, Verdict
    from sentinel.gatekeeper import (
        PolicyConfig,
        # Universal
        NoCriticalBugsPolicy,
        ArchitectureCompliancePolicy,
        TestPassPolicy,
        # Tests-backed policy construction
        policy_from_name,
        policy_from_spec,
    )
"""

from .judge import Gatekeeper
from .policy import (
    ArchitectureCompliancePolicy,
    NoCriticalBugsPolicy,
    Policy,
    PolicyConfig,
    TestPassPolicy,
    policy_from_name,
    policy_from_spec,
)
from .verdict import Verdict

__all__ = [
    # Core
    "Gatekeeper",
    "Policy",
    "PolicyConfig",
    "Verdict",
    # Universal policies
    "ArchitectureCompliancePolicy",
    "NoCriticalBugsPolicy",
    "TestPassPolicy",
    # Tests-backed policy constructors
    "policy_from_name",
    "policy_from_spec",
]
