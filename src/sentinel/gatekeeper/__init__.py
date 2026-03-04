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
        # Python
        NoCircularDependenciesPolicy,
        FunctionComplexityPolicy,
        TODOCommentPolicy,
        RequireDocstringPolicy,
        # Java
        JavaLayeringPolicy,
        PublicFieldPolicy,
        MissingJavadocPolicy,
        JavaNamingConventionPolicy,
        # TypeScript
        StrictTypingPolicy,
        NoUnsafeTypeAssertionPolicy,
        NoConsoleLogPolicy,
    )
"""

from .judge import Gatekeeper
from .policy import (
    ArchitectureCompliancePolicy,
    FunctionComplexityPolicy,
    JavaLayeringPolicy,
    JavaNamingConventionPolicy,
    MissingJavadocPolicy,
    NoCriticalBugsPolicy,
    NoCircularDependenciesPolicy,
    NoConsoleLogPolicy,
    NoUnsafeTypeAssertionPolicy,
    Policy,
    PolicyConfig,
    PublicFieldPolicy,
    RequireDocstringPolicy,
    StrictTypingPolicy,
    TestPassPolicy,
    TODOCommentPolicy,
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
    # Python policies
    "FunctionComplexityPolicy",
    "NoCircularDependenciesPolicy",
    "RequireDocstringPolicy",
    "TODOCommentPolicy",
    # Java policies
    "JavaLayeringPolicy",
    "JavaNamingConventionPolicy",
    "MissingJavadocPolicy",
    "PublicFieldPolicy",
    # TypeScript policies
    "NoConsoleLogPolicy",
    "NoUnsafeTypeAssertionPolicy",
    "StrictTypingPolicy",
]
