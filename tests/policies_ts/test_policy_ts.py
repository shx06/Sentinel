"""
TypeScript policy tests for the Principled Gatekeeper.

Covers every TypeScript-specific policy that Sentinel enforces when
performing automated PR reviews of TypeScript code:

* StrictTypingPolicy            - blocks `any` type usage
* NoUnsafeTypeAssertionPolicy   - blocks `as any` assertions
* NoConsoleLogPolicy            - blocks console.log() calls

Each test class validates:
  1. The policy blocks the exact violation it was designed for.
  2. The policy does NOT fire on clean code.
  3. The policy is language-gated (Python/Java submissions are not affected).
  4. Missing (None) guardian reports are handled gracefully.

Integration tests at the bottom simulate a full PR review using the
Guardian + Gatekeeper pipeline against real TypeScript source files.
"""

import os
import tempfile
import unittest

POLICY_SPECS = [
    {
        "name": "StrictTypingPolicy",
        "language": "TYPESCRIPT",
        "match_mode": "casefold_contains",
        "patterns": ["Found usage of 'any'"],
        "description": "Reject TypeScript code that uses the any type.",
    },
    {
        "name": "NoUnsafeTypeAssertionPolicy",
        "language": "TYPESCRIPT",
        "match_mode": "contains",
        "patterns": ["[UNSAFE_CAST]"],
        "description": "Reject TypeScript code that uses unsafe as any assertions.",
    },
    {
        "name": "NoConsoleLogPolicy",
        "language": "TYPESCRIPT",
        "match_mode": "contains",
        "patterns": ["[CONSOLE_LOG]"],
        "description": "Reject TypeScript code that still contains console logging.",
    },
]

from sentinel.core.guardian import ArchitecturalGuardian
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import (
    PolicyConfig,
    policy_from_name,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gatekeeper(*policies) -> Gatekeeper:
    config = PolicyConfig()
    for p in policies:
        config.add_policy(p)
    return Gatekeeper(config)


def _policy(name: str):
    return policy_from_name(name, Language.TYPESCRIPT)


def _run_guardian(source: str, filename: str = "index.ts") -> list:
    """Write *source* to a temp file, run the Guardian, return violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        guardian = ArchitecturalGuardian()
        guardian.analyze_structure(tmpdir)
        return guardian.check_rules([])


# ---------------------------------------------------------------------------
# StrictTypingPolicy
# ---------------------------------------------------------------------------

class TestStrictTypingPolicy(unittest.TestCase):
    """StrictTypingPolicy blocks TypeScript PRs that use the `any` type."""

    def setUp(self):
        self.gk = _make_gatekeeper(_policy("StrictTypingPolicy"))

    def test_blocks_any_usage(self):
        report = ["Found usage of 'any' in src/index.ts"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)
        self.assertTrue(
            any("found usage of 'any'" in i.lower() for i in verdict.blocking_issues)
        )

    def test_detection_is_case_insensitive(self):
        report = ["FOUND USAGE OF 'ANY' in src/utils.ts"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)

    def test_passes_clean_code(self):
        report = ["Circular dependency detected: a -> b"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_python_not_affected(self):
        report = ["Found usage of 'any' in some_file.py"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_java_not_affected(self):
        report = ["Found usage of 'any' in Foo.java"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_javascript_not_affected(self):
        report = ["Found usage of 'any' in src/app.js"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVASCRIPT)
        self.assertTrue(verdict.approved)

    def test_multiple_any_usages_all_reported(self):
        report = [
            "Found usage of 'any' in src/a.ts",
            "Found usage of 'any' in src/b.ts",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# NoUnsafeTypeAssertionPolicy
# ---------------------------------------------------------------------------

class TestNoUnsafeTypeAssertionPolicy(unittest.TestCase):
    """NoUnsafeTypeAssertionPolicy blocks `as any` expressions in TypeScript."""

    def setUp(self):
        self.gk = _make_gatekeeper(_policy("NoUnsafeTypeAssertionPolicy"))

    def test_blocks_as_any_assertion(self):
        report = ["[UNSAFE_CAST] Unsafe 'as any' assertion in 'src/index.ts'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)
        self.assertTrue(any("[UNSAFE_CAST]" in i for i in verdict.blocking_issues))

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_unrelated_violation_does_not_trigger(self):
        report = ["Found usage of 'any' in src/index.ts"]  # different tag
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_python_not_affected(self):
        report = ["[UNSAFE_CAST] Unsafe 'as any' assertion in 'src/index.ts'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_java_not_affected(self):
        report = ["[UNSAFE_CAST] Unsafe 'as any' assertion in 'src/index.ts'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_multiple_unsafe_casts_all_reported(self):
        report = [
            "[UNSAFE_CAST] Unsafe 'as any' assertion in 'src/a.ts'",
            "[UNSAFE_CAST] Unsafe 'as any' assertion in 'src/b.ts'",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# NoConsoleLogPolicy
# ---------------------------------------------------------------------------

class TestNoConsoleLogPolicy(unittest.TestCase):
    """NoConsoleLogPolicy blocks TypeScript PRs with leftover console.log calls."""

    def setUp(self):
        self.gk = _make_gatekeeper(_policy("NoConsoleLogPolicy"))

    def test_blocks_console_log(self):
        report = ["[CONSOLE_LOG] console.log() usage in 'src/index.ts'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)
        self.assertTrue(any("[CONSOLE_LOG]" in i for i in verdict.blocking_issues))

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_unrelated_violation_does_not_trigger(self):
        report = ["[UNSAFE_CAST] Unsafe 'as any' assertion in 'src/index.ts'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_python_not_affected(self):
        report = ["[CONSOLE_LOG] console.log() usage in 'src/index.ts'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_java_not_affected(self):
        report = ["[CONSOLE_LOG] console.log() usage in 'src/index.ts'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_multiple_console_logs_reported(self):
        report = [
            "[CONSOLE_LOG] console.log() usage in 'src/a.ts'",
            "[CONSOLE_LOG] console.log() usage in 'src/b.ts'",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# PolicyConfig.for_typescript() factory
# ---------------------------------------------------------------------------

class TestPolicyConfigForTypeScript(unittest.TestCase):
    """Validate the TypeScript-specific factory and full-suite behaviour."""

    def setUp(self):
        self.gk = Gatekeeper(PolicyConfig.for_typescript())

    def test_factory_contains_all_typescript_policies(self):
        names = {type(p).__name__ for p in PolicyConfig.for_typescript().policies}
        self.assertIn("StrictTypingPolicy", names)
        self.assertIn("NoUnsafeTypeAssertionPolicy", names)
        self.assertIn("NoConsoleLogPolicy", names)

    def test_clean_ts_pr_is_approved(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)
        self.assertAlmostEqual(verdict.confidence, 1.0)

    def test_all_ts_violations_aggregate_correctly(self):
        report = [
            "Found usage of 'any' in src/index.ts",
            "[UNSAFE_CAST] Unsafe 'as any' assertion in 'src/index.ts'",
            "[CONSOLE_LOG] console.log() usage in 'src/utils.ts'",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)
        self.assertGreaterEqual(len(verdict.blocking_issues), 3)
        self.assertLess(verdict.confidence, 1.0)

    def test_partial_violations_produce_partial_confidence(self):
        report = ["[CONSOLE_LOG] console.log() usage in 'src/a.ts'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertFalse(verdict.approved)
        self.assertGreater(verdict.confidence, 0.0)
        self.assertLess(verdict.confidence, 1.0)

    def test_verdict_summary_on_rejection(self):
        report = ["Found usage of 'any' in src/index.ts"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertIn("rejected", verdict.summary.lower())

    def test_verdict_summary_on_approval(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.TYPESCRIPT)
        self.assertIn("approved", verdict.summary.lower())


# ---------------------------------------------------------------------------
# Integration: Guardian -> Gatekeeper end-to-end for TypeScript
# ---------------------------------------------------------------------------

class TestTypeScriptEndToEnd(unittest.TestCase):
    """Run real Guardian scans and feed results into the Gatekeeper."""

    def _evaluate(self, source: str, filename: str = "index.ts"):
        violations = _run_guardian(source, filename)
        gk = Gatekeeper(PolicyConfig.for_typescript())
        return gk.evaluate(guardian_report=violations, language=Language.TYPESCRIPT)

    def test_any_type_triggers_strict_typing_policy(self):
        source = "let value: any = 42;\n"
        verdict = self._evaluate(source)
        self.assertTrue(
            any("any" in i.lower() for i in verdict.blocking_issues)
        )

    def test_clean_typescript_passes(self):
        source = "let value: number = 42;\n"
        verdict = self._evaluate(source)
        self.assertFalse(
            any("Found usage of" in i for i in verdict.blocking_issues)
        )

    def test_as_any_triggers_unsafe_cast_policy(self):
        source = "const x = (value as any).foo;\n"
        verdict = self._evaluate(source)
        self.assertTrue(any("[UNSAFE_CAST]" in i for i in verdict.blocking_issues))

    def test_console_log_triggers_policy(self):
        source = "console.log('debug info');\n"
        verdict = self._evaluate(source)
        self.assertTrue(any("[CONSOLE_LOG]" in i for i in verdict.blocking_issues))

    def test_no_console_log_in_clean_code(self):
        source = "export function add(a: number, b: number): number { return a + b; }\n"
        verdict = self._evaluate(source)
        self.assertFalse(any("[CONSOLE_LOG]" in i for i in verdict.blocking_issues))

    def test_tsx_file_also_checked(self):
        source = "const x: any = null;\nconsole.log(x);\n"
        verdict = self._evaluate(source, "App.tsx")
        self.assertTrue(any("[CONSOLE_LOG]" in i for i in verdict.blocking_issues))


if __name__ == "__main__":
    unittest.main()
