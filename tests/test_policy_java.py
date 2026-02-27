from sentinel.gatekeeper.policy import Policy
class BlockServiceImportControllerPolicy(Policy):
    """
    Blocks Java code when a Service imports a Controller.
    """
    def applies_to(self, language):
        return language is Language.JAVA
    def evaluate(self, historian_report, guardian_report, fuzzer_report, sandbox_report):
        violations = []
        import re
        pattern = re.compile(r"Import of '.*Controller' in '.*Service\.java'")
        if guardian_report:
            for v in guardian_report:
                print(f"[DEBUG] Java Policy checking violation: {v}")
                if pattern.search(v):
                    violations.append(f"Service importing Controller detected: {v}")
        return violations
import re

class BlockServiceImportControllerPolicy(Policy):
    """
    Blocks Java code when a Service imports a Controller.
    """
    def applies_to(self, language):
        return language is Language.JAVA
    def evaluate(self, historian_report, guardian_report, fuzzer_report, sandbox_report):
        violations = []
        pattern = re.compile(r"Import of '.*Controller' in '.*Service\.java'")
        if guardian_report:
            for v in guardian_report:
                if pattern.search(v):
                    violations.append(f"Service importing Controller detected: {v}")
        return violations
from sentinel.gatekeeper.policy import Policy

class BlockPublicFieldPolicy(Policy):
    """
    Blocks Java code with public fields (not constants).
    """
    def applies_to(self, language):
        return language is Language.JAVA
    def evaluate(self, historian_report, guardian_report, fuzzer_report, sandbox_report):
        violations = []
        if guardian_report:
            for v in guardian_report:
                if "public" in v.lower() and "field" in v.lower():
                    violations.append(f"Public field detected: {v}")
        return violations

class RequireJavadocPolicy(Policy):
    """
    Blocks Java code missing Javadoc comments for classes.
    """
    def applies_to(self, language):
        return language is Language.JAVA
    def evaluate(self, historian_report, guardian_report, fuzzer_report, sandbox_report):
        violations = []
        if guardian_report:
            for v in guardian_report:
                if "missing javadoc" in v.lower():
                    violations.append(f"Missing Javadoc detected: {v}")
        return violations
import unittest
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import PolicyConfig, JavaLayeringPolicy, Policy


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
