import unittest
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import PolicyConfig, JavaLayeringPolicy


class TestJavaLayeringPolicy(unittest.TestCase):
    def setUp(self):
        config = PolicyConfig()
        config.add_policy(JavaLayeringPolicy())
        self.gatekeeper = Gatekeeper(config)

    def test_java_enforces_layering(self):
        """Test that Java projects get blocked by layering violations."""
        guardian_report = ["Layering violation: ui -> data"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.JAVA,
        )
        self.assertFalse(verdict.approved)
        self.assertIn("Layering", verdict.blocking_issues[0])

    def test_python_ignores_java_layering_policy(self):
        """Test that Python projects IGNORE the Java-specific policy."""
        guardian_report = ["Layering violation: ui -> data"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.PYTHON,
        )
        # Should be APPROVED because JavaLayeringPolicy
        # applies_to(PYTHON) returns False
        self.assertTrue(verdict.approved)

    def test_java_approved_without_layering_violations(self):
        """Java projects without layering violations are approved."""
        guardian_report = ["Circular dependency detected: a -> b -> a"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.JAVA,
        )
        self.assertTrue(verdict.approved)

    def test_no_guardian_report(self):
        """Missing guardian report results in approval."""
        verdict = self.gatekeeper.evaluate(
            guardian_report=None,
            language=Language.JAVA,
        )
        self.assertTrue(verdict.approved)


if __name__ == "__main__":
    unittest.main()
