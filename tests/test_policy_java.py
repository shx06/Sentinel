import unittest
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import PolicyConfig, JavaLayeringPolicy


class TestJavaLayeringPolicy(unittest.TestCase):
    def setUp(self):
        config = PolicyConfig()
        config.add_policy(JavaLayeringPolicy())
        self.gatekeeper = Gatekeeper(config)

    def test_java_blocks_service_importing_controller(self):
        """Java projects are blocked when a Service imports a Controller."""
        guardian_report = [
            "Import of 'UserController' in 'OrderService.java'"
        ]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.JAVA,
        )
        self.assertFalse(verdict.approved)
        self.assertIn(guardian_report[0], verdict.blocking_issues)

    def test_java_allows_controller_importing_service(self):
        """Java projects allow a Controller importing a Service (valid direction)."""
        guardian_report = [
            "Import of 'OrderService' in 'OrderController.java'"
        ]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.JAVA,
        )
        self.assertTrue(verdict.approved)

    def test_python_ignores_java_layering_policy(self):
        """Non-Java projects are not affected by JavaLayeringPolicy."""
        guardian_report = [
            "Import of 'UserController' in 'OrderService.java'"
        ]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.PYTHON,
        )
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

    def test_java_blocks_multiple_violations(self):
        """All matching violations are reported when multiple exist."""
        guardian_report = [
            "Import of 'UserController' in 'OrderService.java'",
            "Import of 'PaymentController' in 'BillingService.java'",
            "Import of 'OrderService' in 'OrderController.java'",
        ]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.JAVA,
        )
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


if __name__ == "__main__":
    unittest.main()
