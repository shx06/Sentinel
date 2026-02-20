"""
Policy engine for the Principled Gatekeeper.

Defines the abstract :class:`Policy` base class and concrete policy
implementations that inspect pillar reports to decide whether a code
change should be approved or rejected.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Optional


class Policy(ABC):
    """
    Abstract base class for all Gatekeeper policies.

    A policy inspects one or more pillar reports and returns a (possibly
    empty) list of violation messages.  A non-empty list means the policy
    was violated and the change should be blocked.
    """

    @abstractmethod
    def evaluate(
        self,
        historian_report: Optional[Any],
        guardian_report: Optional[Any],
        fuzzer_report: Optional[Any],
        sandbox_report: Optional[Any],
    ) -> List[str]:
        """
        Evaluate the pillar reports and return violation messages.

        Args:
            historian_report: Report from the Contextual Historian pillar.
            guardian_report: Report from the Architectural Guardian pillar
                             (list of violation strings).
            fuzzer_report: :class:`~sentinel.fuzzer.engine.FuzzReport` from
                           the Adversarial Fuzzer pillar.
            sandbox_report: :class:`~sentinel.sandbox.runner.RunResult` from
                            the Sandbox pillar.

        Returns:
            List of human-readable violation messages.  An empty list means
            no violation.
        """


class NoCriticalBugsPolicy(Policy):
    """
    Rejects a change when the Fuzzer finds at least one crashing input.

    A "crash" is any unhandled exception recorded by
    :class:`~sentinel.fuzzer.engine.FuzzReport`.
    """

    def evaluate(
        self,
        historian_report: Optional[Any],
        guardian_report: Optional[Any],
        fuzzer_report: Optional[Any],
        sandbox_report: Optional[Any],
    ) -> List[str]:
        """
        Check for fuzzer-discovered crashes.

        Args:
            historian_report: Unused by this policy.
            guardian_report: Unused by this policy.
            fuzzer_report: A :class:`~sentinel.fuzzer.engine.FuzzReport`
                           (or any object with a ``failure_count`` attribute).
            sandbox_report: Unused by this policy.

        Returns:
            A single-item list describing the crash count, or an empty list
            when no crashes were found.
        """
        if fuzzer_report is None:
            return []
        failure_count = getattr(fuzzer_report, "failure_count", 0)
        if failure_count > 0:
            return [
                f"Fuzzer detected {failure_count} crashing input(s) – "
                "critical bugs must be fixed before merging."
            ]
        return []


class ArchitectureCompliancePolicy(Policy):
    """
    Rejects a change when the Guardian reports circular dependencies.

    The *guardian_report* is expected to be a list of violation strings
    as returned by :meth:`~sentinel.core.guardian.ArchitecturalGuardian.check_rules`.
    Entries that contain the word ``"Circular"`` are treated as blocking.
    """

    def evaluate(
        self,
        historian_report: Optional[Any],
        guardian_report: Optional[Any],
        fuzzer_report: Optional[Any],
        sandbox_report: Optional[Any],
    ) -> List[str]:
        """
        Check for circular dependency violations from the Guardian.

        Args:
            historian_report: Unused by this policy.
            guardian_report: List of violation strings from the Guardian,
                             or ``None``.
            fuzzer_report: Unused by this policy.
            sandbox_report: Unused by this policy.

        Returns:
            List of circular-dependency violation messages, or an empty list.
        """
        if not guardian_report:
            return []
        circular = [v for v in guardian_report if "Circular" in v]
        return circular


class TestPassPolicy(Policy):
    """
    Rejects a change when the Sandbox execution exits with a non-zero code.

    A non-zero :attr:`~sentinel.sandbox.runner.RunResult.exit_code` or a
    :attr:`~sentinel.sandbox.runner.RunResult.timed_out` flag indicates
    that the sandboxed tests did not pass.
    """

    def evaluate(
        self,
        historian_report: Optional[Any],
        guardian_report: Optional[Any],
        fuzzer_report: Optional[Any],
        sandbox_report: Optional[Any],
    ) -> List[str]:
        """
        Check whether the Sandbox run succeeded.

        Args:
            historian_report: Unused by this policy.
            guardian_report: Unused by this policy.
            fuzzer_report: Unused by this policy.
            sandbox_report: A :class:`~sentinel.sandbox.runner.RunResult`
                            (or any object with ``exit_code`` and
                            ``timed_out`` attributes), or ``None``.

        Returns:
            A single-item list describing the failure, or an empty list when
            the sandbox run succeeded.
        """
        if sandbox_report is None:
            return []
        timed_out = getattr(sandbox_report, "timed_out", False)
        exit_code = getattr(sandbox_report, "exit_code", 0)
        if timed_out:
            return ["Sandbox execution timed out – tests did not complete."]
        if exit_code != 0:
            return [
                f"Sandbox execution failed with exit code {exit_code} – "
                "tests must pass before merging."
            ]
        return []


class PolicyConfig:
    """
    Registry of enabled :class:`Policy` instances.

    Allows consumers to build a custom policy suite and pass it to the
    :class:`~sentinel.gatekeeper.judge.Gatekeeper`.

    Example::

        config = PolicyConfig()
        config.add_policy(NoCriticalBugsPolicy())
        config.add_policy(TestPassPolicy())

    A default configuration with all standard policies enabled is available
    via :meth:`default`.
    """

    def __init__(self) -> None:
        self._policies: List[Policy] = []

    def add_policy(self, policy: Policy) -> None:
        """
        Register a policy.

        Args:
            policy: A :class:`Policy` instance to add.
        """
        self._policies.append(policy)

    @property
    def policies(self) -> List[Policy]:
        """Ordered list of registered policies."""
        return list(self._policies)

    @classmethod
    def default(cls) -> "PolicyConfig":
        """
        Create a :class:`PolicyConfig` with all standard policies enabled.

        Returns:
            A :class:`PolicyConfig` containing :class:`NoCriticalBugsPolicy`,
            :class:`ArchitectureCompliancePolicy`, and :class:`TestPassPolicy`.
        """
        config = cls()
        config.add_policy(NoCriticalBugsPolicy())
        config.add_policy(ArchitectureCompliancePolicy())
        config.add_policy(TestPassPolicy())
        return config
