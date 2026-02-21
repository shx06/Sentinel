"""
The Judge: Principled Gatekeeper orchestrator.

Aggregates intelligence from all Sentinel pillars and renders a final
:class:`~sentinel.gatekeeper.verdict.Verdict` by running each enabled
:class:`~sentinel.gatekeeper.policy.Policy`.
"""

from typing import Any, List, Optional

from sentinel.core.languages import Language
from .policy import Policy, PolicyConfig
from .verdict import Verdict


class Gatekeeper:
    """
    Executive decision-maker that unifies the entire Sentinel system.

    Iterates through a set of :class:`~sentinel.gatekeeper.policy.Policy`
    instances, collects all violations, and produces a
    :class:`~sentinel.gatekeeper.verdict.Verdict`.

    Example::

        gatekeeper = Gatekeeper()
        verdict = gatekeeper.evaluate(
            historian_report=None,
            guardian_report=[],
            fuzzer_report=fuzz_report,
            sandbox_report=run_result,
        )
        if not verdict.approved:
            print(verdict.blocking_issues)
    """

    def __init__(self, config: Optional[PolicyConfig] = None) -> None:
        """
        Initialize the Gatekeeper.

        Args:
            config: :class:`~sentinel.gatekeeper.policy.PolicyConfig`
                    containing the enabled policies.  Defaults to
                    :meth:`~sentinel.gatekeeper.policy.PolicyConfig.default`
                    when ``None``.
        """
        self._config = config if config is not None else PolicyConfig.default()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(
        self,
        historian_report: Optional[Any] = None,
        guardian_report: Optional[Any] = None,
        fuzzer_report: Optional[Any] = None,
        sandbox_report: Optional[Any] = None,
        language: Language = Language.UNKNOWN,
    ) -> Verdict:
        """
        Evaluate all pillar reports and return a final :class:`~sentinel.gatekeeper.verdict.Verdict`.

        Iterates through every enabled :class:`~sentinel.gatekeeper.policy.Policy`
        whose :meth:`~sentinel.gatekeeper.policy.Policy.applies_to` returns
        ``True`` for *language*, collects violations, and produces a verdict.
        The change is approved only when no policy reports a violation.

        Confidence is calculated as the ratio of passing policies to the
        total number of evaluated policies (``1.0`` when there are no
        applicable policies).

        Args:
            historian_report: Report from the Contextual Historian (optional).
            guardian_report: Violation list from the Architectural Guardian
                             (optional).
            fuzzer_report: :class:`~sentinel.fuzzer.engine.FuzzReport` from
                           the Adversarial Fuzzer (optional).
            sandbox_report: :class:`~sentinel.sandbox.runner.RunResult` from
                            the Sandbox (optional).
            language: The :class:`~sentinel.core.languages.Language` of the
                      code change being evaluated.  Defaults to
                      :attr:`~sentinel.core.languages.Language.UNKNOWN`,
                      which causes all universal policies to run and
                      language-specific ones to be skipped.

        Returns:
            A :class:`~sentinel.gatekeeper.verdict.Verdict` with the final
            decision, confidence score, summary, blocking issues, and
            warnings.
        """
        policies: List[Policy] = [
            p for p in self._config.policies if p.applies_to(language)
        ]
        blocking_issues: List[str] = []
        passing = 0

        for policy in policies:
            violations = policy.evaluate(
                historian_report=historian_report,
                guardian_report=guardian_report,
                fuzzer_report=fuzzer_report,
                sandbox_report=sandbox_report,
            )
            if violations:
                blocking_issues.extend(violations)
            else:
                passing += 1

        approved = len(blocking_issues) == 0

        # Confidence: fraction of applicable policies that passed
        confidence = passing / len(policies) if policies else 1.0

        if approved:
            summary = "All policies passed. The change is approved."
        else:
            summary = (
                f"{len(blocking_issues)} blocking issue(s) found. "
                "The change is rejected."
            )

        return Verdict(
            approved=approved,
            confidence=confidence,
            summary=summary,
            blocking_issues=blocking_issues,
            warnings=[],
        )
