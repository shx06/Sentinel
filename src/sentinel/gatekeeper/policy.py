"""Policy framework for the Principled Gatekeeper.

This module defines the Gatekeeper's policy interface, universal runtime
policies, and the machinery that converts tests-backed ``POLICY_SPECS``
catalog entries into executable policy objects.
"""

import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from sentinel.core.languages import Language
from .test_policy_source import load_policy_specs


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


class SpecBackedPolicy(Policy):
    """A policy instantiated directly from the tests-backed ``POLICY_SPECS`` catalog."""

    def __init__(self, spec: Dict[str, Any]) -> None:
        self._spec = spec
        self._language = Language[spec["language"]]
        self._patterns = list(spec.get("patterns", []))
        self._match_mode = spec.get("match_mode", "contains")

    def applies_to(self, language: Language) -> bool:
        return language is self._language

    def evaluate(
        self,
        historian_report: Optional[Any],
        guardian_report: Optional[Any],
        fuzzer_report: Optional[Any],
        sandbox_report: Optional[Any],
    ) -> List[str]:
        if not guardian_report:
            return []

        matches: List[str] = []
        for violation in guardian_report:
            if any(self._matches_pattern(violation, pattern) for pattern in self._patterns):
                matches.append(violation)
        return matches

    def _matches_pattern(self, violation: str, pattern: str) -> bool:
        if self._match_mode == "regex":
            return bool(re.search(pattern, violation))
        if self._match_mode == "casefold_contains":
            return pattern.casefold() in violation.casefold()
        return pattern in violation


_SPEC_POLICY_CLASS_CACHE: Dict[str, type[SpecBackedPolicy]] = {}


def _build_spec_policy(spec: Dict[str, Any]) -> SpecBackedPolicy:
    """Create a dynamic policy instance whose class name matches the spec name."""
    name = spec["name"]
    policy_class = _SPEC_POLICY_CLASS_CACHE.get(name)
    if policy_class is None:
        policy_class = type(name, (SpecBackedPolicy,), {})
        _SPEC_POLICY_CLASS_CACHE[name] = policy_class
    return policy_class(spec)


def policy_from_spec(spec: Dict[str, Any]) -> Policy:
    """Build a runtime policy instance from a tests-backed policy spec."""
    return _build_spec_policy(spec)


def policy_from_name(name: str, language: Language) -> Policy:
    """Load a named language policy from the tests-backed ``POLICY_SPECS`` catalogs."""
    for spec in load_policy_specs(language):
        if spec["name"] == name:
            return policy_from_spec(spec)
    raise ValueError(f"Policy spec '{name}' not found for language {language.name}.")


# ---------------------------------------------------------------------------
# Policy registry
# ---------------------------------------------------------------------------

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
    via :meth:`default`.  Language-specific suites are available via
    :meth:`for_python`, :meth:`for_java`, and :meth:`for_typescript`.
    """

    def __init__(self) -> None:
        self._policies: List[Policy] = []

    def add_policy(self, policy: Policy) -> None:
        """Register a policy."""
        self._policies.append(policy)

    @property
    def policies(self) -> List[Policy]:
        """Ordered list of registered policies."""
        return list(self._policies)

    @classmethod
    def default(cls) -> "PolicyConfig":
        """
        Create a :class:`PolicyConfig` with the universal cross-language
        policies enabled (fuzzer crashes, architecture compliance, sandbox).
        """
        config = cls()
        config.add_policy(NoCriticalBugsPolicy())
        config.add_policy(ArchitectureCompliancePolicy())
        config.add_policy(TestPassPolicy())
        return config

    @classmethod
    def from_languages(cls, languages: List[Language]) -> "PolicyConfig":
        """Load the active runtime policies for the given languages from ``tests/``."""
        config = cls()
        for language in languages:
            if language is Language.PYTHON:
                for policy in cls.for_python().policies:
                    config.add_policy(policy)
            elif language is Language.JAVA:
                for policy in cls.for_java().policies:
                    config.add_policy(policy)
            elif language is Language.TYPESCRIPT:
                for policy in cls.for_typescript().policies:
                    config.add_policy(policy)
        return config

    @classmethod
    def for_python(cls) -> "PolicyConfig":
        """
        Create a :class:`PolicyConfig` from the tests-backed Python policy catalog.
        """
        config = cls()
        specs = load_policy_specs(Language.PYTHON)
        for spec in specs:
            config.add_policy(_build_spec_policy(spec))
        return config

    @classmethod
    def for_java(cls) -> "PolicyConfig":
        """
        Create a :class:`PolicyConfig` from the tests-backed Java policy catalog.
        """
        config = cls()
        specs = load_policy_specs(Language.JAVA)
        for spec in specs:
            config.add_policy(_build_spec_policy(spec))
        return config

    @classmethod
    def for_typescript(cls) -> "PolicyConfig":
        """
        Create a :class:`PolicyConfig` from the tests-backed TypeScript policy catalog.
        """
        config = cls()
        specs = load_policy_specs(Language.TYPESCRIPT)
        for spec in specs:
            config.add_policy(_build_spec_policy(spec))
        return config
