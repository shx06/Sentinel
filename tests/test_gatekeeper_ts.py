import unittest
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import PolicyConfig, StrictTypingPolicy


class TestStrictTypingPolicy(unittest.TestCase):
    def setUp(self):
        config = PolicyConfig()
        config.add_policy(StrictTypingPolicy())
        self.gatekeeper = Gatekeeper(config)

    def test_typescript_blocked_on_any_usage(self):
        """TypeScript changes with 'any' usage are rejected."""
        guardian_report = ["Found usage of 'any' in src/index.ts"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.TYPESCRIPT,
        )
        self.assertFalse(verdict.approved)
        self.assertTrue(
            any("found usage of 'any'" in issue.lower() for issue in verdict.blocking_issues)
        )

    def test_typescript_blocked_case_insensitive(self):
        """Detection is case-insensitive."""
        guardian_report = ["FOUND USAGE OF 'ANY' in src/utils.ts"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.TYPESCRIPT,
        )
        self.assertFalse(verdict.approved)

    def test_typescript_approved_without_any_usage(self):
        """TypeScript changes without 'any' usage are approved."""
        guardian_report = ["Circular dependency detected: a -> b"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.TYPESCRIPT,
        )
        self.assertTrue(verdict.approved)

    def test_python_ignores_any_usage(self):
        """Python projects are not affected by StrictTypingPolicy."""
        guardian_report = ["Found usage of 'any' in some_file.py"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.PYTHON,
        )
        self.assertTrue(verdict.approved)

    def test_javascript_ignores_any_usage(self):
        """JavaScript projects are not affected by StrictTypingPolicy."""
        guardian_report = ["Found usage of 'any' in src/app.js"]
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.JAVASCRIPT,
        )
        self.assertTrue(verdict.approved)

    def test_no_guardian_report(self):
        """Missing guardian report results in approval."""
        verdict = self.gatekeeper.evaluate(
            guardian_report=None,
            language=Language.TYPESCRIPT,
        )
        self.assertTrue(verdict.approved)


if __name__ == "__main__":
    unittest.main()
