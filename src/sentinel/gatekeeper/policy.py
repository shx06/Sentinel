"""
Policy engine for the Principled Gatekeeper.

Defines the abstract :class:`Policy` base class and concrete policy
implementations that inspect pillar reports to decide whether a code
change should be approved or rejected.
"""

import re
from abc import ABC, abstractmethod
from typing import Any, List, Optional

from sentinel.core.languages import Language


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

    def applies_to(self, language: Language) -> bool:
        """
        Return whether this policy should be evaluated for the given language.

        The default implementation returns ``True`` for every language,
        meaning the policy is universal.  Language-specific subclasses
        should override this method to restrict evaluation to the relevant
        language(s).

        Args:
            language: The :class:`~sentinel.core.languages.Language` of the
                      code change being evaluated.

        Returns:
            ``True`` when the policy should run, ``False`` to skip it.
        """
        return True


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


class NoCircularDependenciesPolicy(Policy):
    """
    Rejects a change when the Guardian reports circular dependencies.

    This policy is specific to **Python** projects.  For other languages it
    is skipped automatically via :meth:`applies_to`.

    The *guardian_report* is expected to be a list of violation strings as
    returned by :meth:`~sentinel.core.guardian.ArchitecturalGuardian.check_rules`.
    Entries that contain the word ``"Circular"`` are treated as blocking.
    """

    def applies_to(self, language: Language) -> bool:
        """Return ``True`` only for Python."""
        return language is Language.PYTHON

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
        return [v for v in guardian_report if "Circular" in v]


class StrictTypingPolicy(Policy):
    """
    Rejects a change when the Guardian reports ``any`` type usage.

    This policy is specific to **TypeScript** projects.  For other languages
    it is skipped automatically via :meth:`applies_to`.

    The *guardian_report* is expected to be a list of violation strings.
    Entries that contain the phrase ``"Found usage of 'any'"``
    (case-insensitive) are treated as blocking.
    """

    def applies_to(self, language: Language) -> bool:
        """Return ``True`` only for TypeScript."""
        return language is Language.TYPESCRIPT

    def evaluate(
        self,
        historian_report: Optional[Any],
        guardian_report: Optional[Any],
        fuzzer_report: Optional[Any],
        sandbox_report: Optional[Any],
    ) -> List[str]:
        """
        Check for ``any`` type usage violations from the Guardian.

        Args:
            historian_report: Unused by this policy.
            guardian_report: List of violation strings from the Guardian,
                             or ``None``.
            fuzzer_report: Unused by this policy.
            sandbox_report: Unused by this policy.

        Returns:
            List of ``any``-usage violation messages, or an empty list.
        """
        if not guardian_report:
            return []
        return [
            v for v in guardian_report
            if "found usage of 'any'" in v.lower()
        ]


class JavaLayeringPolicy(Policy):
    """
    Rejects a change when a Service imports a Controller in a Java project.

    This policy is specific to **Java** projects.  For other languages it
    is skipped automatically via :meth:`applies_to`.

    The *guardian_report* is expected to be a list of violation strings.
    Entries matching the pattern ``Import of '.*Controller' in '.*Service.java'``
    are treated as blocking layering violations.
    """

    _PATTERN = re.compile(r"Import of '.*Controller' in '.*Service\.java'")

    def applies_to(self, language: Language) -> bool:
        """Return ``True`` only for Java."""
        return language is Language.JAVA

    def evaluate(
        self,
        historian_report: Optional[Any],
        guardian_report: Optional[Any],
        fuzzer_report: Optional[Any],
        sandbox_report: Optional[Any],
    ) -> List[str]:
        """
        Check for Service-imports-Controller layering violations from the Guardian.

        Args:
            historian_report: Unused by this policy.
            guardian_report: List of violation strings from the Guardian,
                             or ``None``.
            fuzzer_report: Unused by this policy.
            sandbox_report: Unused by this policy.

        Returns:
            List of layering violation messages, or an empty list.
        """
        if not guardian_report:
            return []
        return [v for v in guardian_report if self._PATTERN.search(v)]


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
