"""
The Judge: core decision-maker for the Principled Gatekeeper.

Aggregates intelligence from the other four Sentinel pillars
(Historian, Guardian, Fuzzer, Sandbox) and issues a final
:class:`~sentinel.gatekeeper.verdict.Verdict`.
"""

from typing import Any, Dict, List, Optional

from .policy import Policy
from .verdict import Verdict, VerdictStatus, Violation


class GatekeeperJudge:
    """
    Aggregates pillar reports and enforces quality/security policies.

    Usage::

        from sentinel.gatekeeper import GatekeeperJudge, Policy

        judge = GatekeeperJudge(policy=Policy(max_complexity=8))
        verdict = judge.evaluate(context)
        print(verdict.status)   # VerdictStatus.PASS or VerdictStatus.FAIL
    """

    def __init__(self, policy: Optional[Policy] = None) -> None:
        """
        Initialize the judge with an optional :class:`Policy`.

        Args:
            policy: The policy to enforce.  If *None*, a default
                    :class:`Policy` is created.
        """
        self.policy = policy if policy is not None else Policy()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate(self, context: Dict[str, Any]) -> Verdict:
        """
        Evaluate reports from all pillars and return a :class:`Verdict`.

        The *context* dictionary may contain the following keys
        (all optional):

        * ``"historian"`` – report dict produced by
          :class:`~sentinel.historian.engine.ContextualHistorian`.
        * ``"guardian"`` – list of violation strings produced by
          :class:`~sentinel.core.guardian.ArchitecturalGuardian`.
        * ``"fuzzer"`` – :class:`~sentinel.fuzzer.engine.FuzzReport`
          (or any object with a ``failure_count`` attribute).
        * ``"sandbox"`` – :class:`~sentinel.sandbox.runner.RunResult`
          (or any object with ``exit_code`` and ``timed_out`` attributes).

        Args:
            context: Mapping of pillar name to its report.

        Returns:
            A :class:`Verdict` reflecting all policy checks.
        """
        violations: List[Violation] = []

        violations.extend(self._check_guardian(context.get("guardian")))
        violations.extend(self._check_fuzzer(context.get("fuzzer")))
        violations.extend(self._check_sandbox(context.get("sandbox")))
        violations.extend(self._check_historian(context.get("historian")))

        if violations:
            status = VerdictStatus.FAIL
            summary = (
                f"FAIL – {len(violations)} violation(s) detected."
            )
        else:
            status = VerdictStatus.PASS
            summary = "PASS – all policy checks succeeded."

        return Verdict(status=status, summary=summary, details=violations)

    # ------------------------------------------------------------------
    # Private checkers – one per pillar
    # ------------------------------------------------------------------

    def _check_guardian(
        self, guardian_report: Optional[Any]
    ) -> List[Violation]:
        """
        Check violations reported by the Architectural Guardian.

        The Guardian returns a list of plain string violation messages
        (e.g. from :class:`~sentinel.core.rules.FunctionComplexityRule`
        configured with :attr:`Policy.max_complexity`).  Each message is
        wrapped in a :class:`Violation` with severity ``"error"``.

        Note:
            :attr:`Policy.max_complexity` is the threshold that should be
            used when constructing the Guardian's
            :class:`~sentinel.core.rules.FunctionComplexityRule`.  The
            judge enforces the policy by treating every Guardian violation
            as a policy failure.

        Args:
            guardian_report: List of violation strings, or ``None``.

        Returns:
            List of :class:`Violation` objects.
        """
        if not guardian_report:
            return []

        violations: List[Violation] = []
        for message in guardian_report:
            violations.append(
                Violation(
                    severity="error",
                    message=message,
                    context={"pillar": "guardian"},
                )
            )
        return violations

    def _check_fuzzer(
        self, fuzzer_report: Optional[Any]
    ) -> List[Violation]:
        """
        Check the fuzzer report against :attr:`Policy.allowed_fuzzer_crashes`.

        Args:
            fuzzer_report: A :class:`~sentinel.fuzzer.engine.FuzzReport`
                           instance (or any object with a ``failure_count``
                           attribute), or ``None``.

        Returns:
            List of :class:`Violation` objects.
        """
        if fuzzer_report is None:
            return []

        failure_count = getattr(fuzzer_report, "failure_count", 0)
        if failure_count > self.policy.allowed_fuzzer_crashes:
            return [
                Violation(
                    severity="error",
                    message=(
                        f"Fuzzer detected {failure_count} crash(es); "
                        f"policy allows {self.policy.allowed_fuzzer_crashes}."
                    ),
                    context={
                        "pillar": "fuzzer",
                        "failure_count": failure_count,
                        "allowed": self.policy.allowed_fuzzer_crashes,
                    },
                )
            ]
        return []

    def _check_sandbox(
        self, sandbox_report: Optional[Any]
    ) -> List[Violation]:
        """
        Check the sandbox execution result.

        A non-zero exit code or a timed-out execution is treated as a
        policy violation.

        Args:
            sandbox_report: A :class:`~sentinel.sandbox.runner.RunResult`
                            instance (or any object with ``exit_code`` and
                            ``timed_out`` attributes), or ``None``.

        Returns:
            List of :class:`Violation` objects.
        """
        if sandbox_report is None:
            return []

        violations: List[Violation] = []

        timed_out = getattr(sandbox_report, "timed_out", False)
        if timed_out:
            violations.append(
                Violation(
                    severity="error",
                    message="Sandbox execution timed out.",
                    context={"pillar": "sandbox", "timed_out": True},
                )
            )

        exit_code = getattr(sandbox_report, "exit_code", 0)
        if not timed_out and exit_code != 0:
            violations.append(
                Violation(
                    severity="error",
                    message=(
                        f"Sandbox execution failed with exit code {exit_code}."
                    ),
                    context={
                        "pillar": "sandbox",
                        "exit_code": exit_code,
                    },
                )
            )

        return violations

    def _check_historian(
        self, historian_report: Optional[Any]
    ) -> List[Violation]:
        """
        Check content from the Contextual Historian against forbidden patterns.

        Scans every document in the historian report for strings listed in
        :attr:`Policy.forbidden_patterns`.

        Args:
            historian_report: A list of result dicts as returned by
                              :meth:`~sentinel.historian.engine.ContextualHistorian.explain_context`,
                              or ``None``.

        Returns:
            List of :class:`Violation` objects.
        """
        if not historian_report or not self.policy.forbidden_patterns:
            return []

        violations: List[Violation] = []
        for entry in historian_report:
            if isinstance(entry, dict):
                document = entry.get("document", "")
            else:
                # Unexpected format – skip non-dict entries gracefully.
                continue
            for pattern in self.policy.forbidden_patterns:
                if pattern in document:
                    violations.append(
                        Violation(
                            severity="warning",
                            message=(
                                f"Forbidden pattern '{pattern}' found in "
                                "historian document."
                            ),
                            context={
                                "pillar": "historian",
                                "pattern": pattern,
                            },
                        )
                    )
        return violations
