"""
Sandbox module for Sentinel.

Provides isolated, ephemeral Docker-based environments for safe code execution,
preventing side effects on the host machine.

Public API::

    from sentinel.sandbox import SandboxContainer, SandboxRunner, SandboxEnvironment
    from sentinel.sandbox.runner import RunResult
"""

from .container import SandboxContainer
from .environment import SandboxEnvironment
from .runner import RunResult, SandboxRunner

__all__ = [
    "RunResult",
    "SandboxContainer",
    "SandboxEnvironment",
    "SandboxRunner",
]
