from sentinel.gatekeeper.policy import Policy

class BlockForbiddenImportsPolicy(Policy):
    """
    Blocks Python code that imports forbidden modules (os, sys).
    """
    def applies_to(self, language):
        return language is Language.PYTHON
    def evaluate(self, historian_report, guardian_report, fuzzer_report, sandbox_report):
        violations = []
        if guardian_report:
            for v in guardian_report:
                if "import os" in v.lower() or "import sys" in v.lower():
                    violations.append(f"Forbidden import detected: {v}")
        return violations

class BlockTODOCommentPolicy(Policy):
    """
    Blocks Python code containing TODO comments.
    """
    def applies_to(self, language):
        return language is Language.PYTHON
    def evaluate(self, historian_report, guardian_report, fuzzer_report, sandbox_report):
        violations = []
        if guardian_report:
            for v in guardian_report:
                if "todo" in v.lower():
                    violations.append(f"TODO comment detected: {v}")
        return violations
import unittest
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import PolicyConfig, NoCircularDependenciesPolicy


class TestNoCircularDependenciesPolicy(unittest.TestCase):
    def setUp(self):
        config = PolicyConfig()
        config.add_policy(NoCircularDependenciesPolicy())
        self.gatekeeper = Gatekeeper(config)

    def test_python_enforces_circular_deps(self):
        """Test that Python projects get blocked by circular dependencies."""
        guardian_report = ["Circular dependency detected: a -> b -> a"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.PYTHON,
        )
        self.assertFalse(verdict.approved)
        self.assertIn("Circular", verdict.blocking_issues[0])

    def test_java_ignores_circular_deps_policy(self):
        """Test that Java projects IGNORE the Python-specific policy."""
        guardian_report = ["Circular dependency detected: a -> b -> a"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.JAVA,
        )
        # Should be APPROVED because NoCircularDependenciesPolicy
        # applies_to(JAVA) returns False
        self.assertTrue(verdict.approved)

    def test_python_approved_without_circular_deps(self):
        """Python projects without circular dependencies are approved."""
        guardian_report = ["Layering violation: ui -> data"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.PYTHON,
        )
        self.assertTrue(verdict.approved)

    def test_no_guardian_report(self):
        """Missing guardian report results in approval."""
        verdict = self.gatekeeper.evaluate(
            guardian_report=None,
            language=Language.PYTHON,
        )
        self.assertTrue(verdict.approved)


if __name__ == "__main__":
    unittest.main()
