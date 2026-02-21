"""
Tests for language-aware Gatekeeper behavior.

Verifies that language-specific policies are correctly applied or skipped
based on the language context passed to :meth:`Gatekeeper.evaluate`.
"""

import pytest

from sentinel.core.languages import Language
from sentinel.gatekeeper.judge import Gatekeeper
from sentinel.gatekeeper.policy import (
    JavaLayeringPolicy,
    NoCircularDependenciesPolicy,
    PolicyConfig,
    StrictTypingPolicy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gatekeeper(*policies):
    """Return a Gatekeeper configured with exactly the given policies."""
    config = PolicyConfig()
    for p in policies:
        config.add_policy(p)
    return Gatekeeper(config=config)


# ---------------------------------------------------------------------------
# Language enum tests
# ---------------------------------------------------------------------------

class TestLanguageEnum:
    def test_all_members_exist(self):
        for name in ("PYTHON", "JAVA", "TYPESCRIPT", "JAVASCRIPT", "UNKNOWN"):
            assert hasattr(Language, name)

    def test_members_are_distinct(self):
        members = list(Language)
        assert len(members) == len(set(members))


# ---------------------------------------------------------------------------
# applies_to tests
# ---------------------------------------------------------------------------

class TestAppliesToPolicy:
    def test_no_circular_dependencies_applies_to_python(self):
        policy = NoCircularDependenciesPolicy()
        assert policy.applies_to(Language.PYTHON) is True

    def test_no_circular_dependencies_skipped_for_java(self):
        policy = NoCircularDependenciesPolicy()
        assert policy.applies_to(Language.JAVA) is False

    def test_no_circular_dependencies_skipped_for_typescript(self):
        policy = NoCircularDependenciesPolicy()
        assert policy.applies_to(Language.TYPESCRIPT) is False

    def test_no_circular_dependencies_skipped_for_javascript(self):
        policy = NoCircularDependenciesPolicy()
        assert policy.applies_to(Language.JAVASCRIPT) is False

    def test_no_circular_dependencies_skipped_for_unknown(self):
        policy = NoCircularDependenciesPolicy()
        assert policy.applies_to(Language.UNKNOWN) is False

    def test_strict_typing_applies_to_typescript(self):
        policy = StrictTypingPolicy()
        assert policy.applies_to(Language.TYPESCRIPT) is True

    def test_strict_typing_applies_to_javascript(self):
        policy = StrictTypingPolicy()
        assert policy.applies_to(Language.JAVASCRIPT) is True

    def test_strict_typing_skipped_for_python(self):
        policy = StrictTypingPolicy()
        assert policy.applies_to(Language.PYTHON) is False

    def test_strict_typing_skipped_for_java(self):
        policy = StrictTypingPolicy()
        assert policy.applies_to(Language.JAVA) is False

    def test_java_layering_applies_to_java(self):
        policy = JavaLayeringPolicy()
        assert policy.applies_to(Language.JAVA) is True

    def test_java_layering_skipped_for_python(self):
        policy = JavaLayeringPolicy()
        assert policy.applies_to(Language.PYTHON) is False

    def test_java_layering_skipped_for_typescript(self):
        policy = JavaLayeringPolicy()
        assert policy.applies_to(Language.TYPESCRIPT) is False


# ---------------------------------------------------------------------------
# Gatekeeper.evaluate with language filtering
# ---------------------------------------------------------------------------

class TestGatekeeperLanguageFiltering:
    """Verify that only applicable policies run when language is supplied."""

    def test_python_circular_dep_blocked(self):
        gk = _make_gatekeeper(NoCircularDependenciesPolicy())
        verdict = gk.evaluate(
            guardian_report=["Circular dependency: a -> b -> a"],
            language=Language.PYTHON,
        )
        assert not verdict.approved
        assert any("Circular" in issue for issue in verdict.blocking_issues)

    def test_python_circular_dep_not_triggered_for_java(self):
        gk = _make_gatekeeper(NoCircularDependenciesPolicy())
        # The same guardian report should not block a Java project
        verdict = gk.evaluate(
            guardian_report=["Circular dependency: a -> b -> a"],
            language=Language.JAVA,
        )
        assert verdict.approved
        assert verdict.blocking_issues == []

    def test_strict_typing_blocked_for_typescript(self):
        gk = _make_gatekeeper(StrictTypingPolicy())
        verdict = gk.evaluate(
            guardian_report=["Typing violation: implicit any in module X"],
            language=Language.TYPESCRIPT,
        )
        assert not verdict.approved
        assert any("Typing" in issue for issue in verdict.blocking_issues)

    def test_strict_typing_blocked_for_javascript(self):
        gk = _make_gatekeeper(StrictTypingPolicy())
        verdict = gk.evaluate(
            guardian_report=["Typing violation: missing return type"],
            language=Language.JAVASCRIPT,
        )
        assert not verdict.approved

    def test_strict_typing_not_triggered_for_python(self):
        gk = _make_gatekeeper(StrictTypingPolicy())
        verdict = gk.evaluate(
            guardian_report=["Typing violation: implicit any"],
            language=Language.PYTHON,
        )
        assert verdict.approved
        assert verdict.blocking_issues == []

    def test_java_layering_blocked_for_java(self):
        gk = _make_gatekeeper(JavaLayeringPolicy())
        verdict = gk.evaluate(
            guardian_report=["Layering violation: UI layer accesses DB layer directly"],
            language=Language.JAVA,
        )
        assert not verdict.approved
        assert any("Layering" in issue for issue in verdict.blocking_issues)

    def test_java_layering_not_triggered_for_typescript(self):
        gk = _make_gatekeeper(JavaLayeringPolicy())
        verdict = gk.evaluate(
            guardian_report=["Layering violation: UI layer accesses DB layer directly"],
            language=Language.TYPESCRIPT,
        )
        assert verdict.approved
        assert verdict.blocking_issues == []

    def test_no_applicable_policies_gives_approved_with_full_confidence(self):
        # A Java-specific policy evaluated against a Python project should
        # yield an approved verdict with confidence 1.0 (no applicable rules).
        gk = _make_gatekeeper(JavaLayeringPolicy())
        verdict = gk.evaluate(language=Language.PYTHON)
        assert verdict.approved
        assert verdict.confidence == pytest.approx(1.0)

    def test_unknown_language_skips_language_specific_policies(self):
        gk = _make_gatekeeper(
            NoCircularDependenciesPolicy(),
            StrictTypingPolicy(),
            JavaLayeringPolicy(),
        )
        verdict = gk.evaluate(
            guardian_report=[
                "Circular dependency: x -> y",
                "Typing violation: missing type",
                "Layering violation: wrong layer",
            ],
            language=Language.UNKNOWN,
        )
        # None of the language-specific policies apply to UNKNOWN
        assert verdict.approved
        assert verdict.blocking_issues == []

    def test_default_language_is_unknown(self):
        """evaluate() without explicit language behaves as UNKNOWN."""
        gk = _make_gatekeeper(NoCircularDependenciesPolicy())
        verdict = gk.evaluate(guardian_report=["Circular dependency: a -> b"])
        # Policy does not apply to UNKNOWN, so no blocking issues
        assert verdict.approved

    def test_mixed_policies_only_applicable_ones_run(self):
        from sentinel.gatekeeper.policy import NoCriticalBugsPolicy

        class FakeFuzzReport:
            failure_count = 2

        gk = _make_gatekeeper(
            NoCriticalBugsPolicy(),        # universal – always applies
            NoCircularDependenciesPolicy(), # Python-only
        )
        verdict = gk.evaluate(
            fuzzer_report=FakeFuzzReport(),
            guardian_report=["Circular dependency: a -> b"],
            language=Language.JAVA,  # NoCircularDependenciesPolicy should be skipped
        )
        # NoCriticalBugsPolicy must still fire
        assert not verdict.approved
        assert any("crashing" in issue for issue in verdict.blocking_issues)
        # But NO circular dependency issue
        assert not any("Circular" in issue for issue in verdict.blocking_issues)
