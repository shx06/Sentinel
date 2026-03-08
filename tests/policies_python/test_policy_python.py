"""
Python policy tests for the Principled Gatekeeper.

Covers every Python-specific policy that Sentinel enforces when
performing automated PR reviews of Python code:

* NoCircularDependenciesPolicy  - blocks circular imports
* FunctionComplexityPolicy      - blocks overly complex functions
* TODOCommentPolicy             - blocks TODO/FIXME markers
* RequireDocstringPolicy        - blocks missing public docstrings

Each test class validates:
  1. The policy blocks the exact violation it was designed for.
  2. The policy does NOT fire on clean code.
  3. The policy is language-gated (Java/TS submissions are not affected).
  4. Missing (None) guardian reports are handled gracefully.

Integration tests at the bottom simulate a full PR review using the
Guardian + Gatekeeper pipeline against real source files.
"""

import os
import tempfile
import unittest

from sentinel.core.guardian import ArchitecturalGuardian
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import (
    FunctionComplexityPolicy,
    NoCircularDependenciesPolicy,
    PolicyConfig,
    RequireDocstringPolicy,
    TODOCommentPolicy,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_gatekeeper(*policies) -> Gatekeeper:
    config = PolicyConfig()
    for p in policies:
        config.add_policy(p)
    return Gatekeeper(config)


def _run_guardian(source: str, filename: str = "module.py") -> list:
    """Write *source* to a temp file, run the Guardian, return violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        guardian = ArchitecturalGuardian()
        guardian.analyze_structure(tmpdir)
        return guardian.check_rules([])


# ---------------------------------------------------------------------------
# NoCircularDependenciesPolicy
# ---------------------------------------------------------------------------

class TestNoCircularDependenciesPolicy(unittest.TestCase):
    """NoCircularDependenciesPolicy blocks Python PRs with circular imports."""

    def setUp(self):
        self.gk = _make_gatekeeper(NoCircularDependenciesPolicy())

    def test_blocks_circular_dependency(self):
        report = ["Circular dependency detected: a -> b -> a"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)
        self.assertTrue(any("Circular" in i for i in verdict.blocking_issues))

    def test_passes_clean_code(self):
        report = ["Layering violation: ui -> data"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_java_not_affected(self):
        report = ["Circular dependency detected: a -> b -> a"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_typescript_not_affected(self):
        report = ["Circular dependency detected: a -> b -> a"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_multiple_cycles_all_reported(self):
        report = [
            "Circular dependency detected: a -> b -> a",
            "Circular dependency detected: x -> y -> z -> x",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# FunctionComplexityPolicy
# ---------------------------------------------------------------------------

class TestFunctionComplexityPolicy(unittest.TestCase):
    """FunctionComplexityPolicy blocks Python PRs with over-complex functions."""

    def setUp(self):
        self.gk = _make_gatekeeper(FunctionComplexityPolicy())

    def test_blocks_high_complexity(self):
        report = ["src/app.py::my_func has complexity 15 (max allowed: 10)"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)
        self.assertTrue(any("has complexity" in i for i in verdict.blocking_issues))

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_unrelated_violation_does_not_trigger(self):
        report = ["Circular dependency detected: a -> b -> a"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_java_not_affected(self):
        report = ["src/app.py::my_func has complexity 20 (max allowed: 10)"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_typescript_not_affected(self):
        report = ["src/app.py::my_func has complexity 20 (max allowed: 10)"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_multiple_complex_functions_all_reported(self):
        report = [
            "src/a.py::foo has complexity 12 (max allowed: 10)",
            "src/b.py::bar has complexity 18 (max allowed: 10)",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# TODOCommentPolicy
# ---------------------------------------------------------------------------

class TestTODOCommentPolicy(unittest.TestCase):
    """TODOCommentPolicy blocks Python PRs containing TODO/FIXME markers."""

    def setUp(self):
        self.gk = _make_gatekeeper(TODOCommentPolicy())

    def test_blocks_todo_marker(self):
        report = ["[TODO] TODO/FIXME comment in 'module.py': # TODO: implement this"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)

    def test_blocks_fixme_marker(self):
        report = ["[TODO] TODO/FIXME comment in 'module.py': # FIXME: broken"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)

    def test_passes_no_markers(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_java_not_affected(self):
        report = ["[TODO] TODO/FIXME comment in 'module.py': # TODO: fix"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_typescript_not_affected(self):
        report = ["[TODO] TODO/FIXME comment in 'module.py': # TODO: fix"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_multiple_todos_all_reported(self):
        report = [
            "[TODO] TODO/FIXME comment in 'a.py': # TODO: a",
            "[TODO] TODO/FIXME comment in 'b.py': # FIXME: b",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# RequireDocstringPolicy
# ---------------------------------------------------------------------------

class TestRequireDocstringPolicy(unittest.TestCase):
    """RequireDocstringPolicy blocks Python PRs that omit public docstrings."""

    def setUp(self):
        self.gk = _make_gatekeeper(RequireDocstringPolicy())

    def test_blocks_missing_function_docstring(self):
        report = ["[DOCSTRING] Missing docstring in 'mymod::process' (function)"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)

    def test_blocks_missing_class_docstring(self):
        report = ["[DOCSTRING] Missing docstring in 'mymod::MyClass' (class)"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)

    def test_passes_all_documented(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_java_not_affected(self):
        report = ["[DOCSTRING] Missing docstring in 'mymod::process' (function)"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_typescript_not_affected(self):
        report = ["[DOCSTRING] Missing docstring in 'mymod::process' (function)"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_multiple_missing_all_reported(self):
        report = [
            "[DOCSTRING] Missing docstring in 'mod::foo' (function)",
            "[DOCSTRING] Missing docstring in 'mod::Bar' (class)",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# PolicyConfig.for_python() factory
# ---------------------------------------------------------------------------

class TestPolicyConfigForPython(unittest.TestCase):
    """Validate the language-specific factory and full-suite behaviour."""

    def setUp(self):
        self.gk = Gatekeeper(PolicyConfig.for_python())

    def test_factory_contains_all_python_policies(self):
        names = {type(p).__name__ for p in PolicyConfig.for_python().policies}
        self.assertIn("NoCircularDependenciesPolicy", names)
        self.assertIn("FunctionComplexityPolicy", names)
        self.assertIn("TODOCommentPolicy", names)
        self.assertIn("RequireDocstringPolicy", names)

    def test_clean_pr_is_fully_approved(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.PYTHON)
        self.assertTrue(verdict.approved)
        self.assertAlmostEqual(verdict.confidence, 1.0)

    def test_all_violations_aggregate_correctly(self):
        report = [
            "Circular dependency detected: a -> b -> a",
            "src/a.py::func has complexity 15 (max allowed: 10)",
            "[TODO] TODO/FIXME comment in 'a.py': # TODO: fix",
            "[DOCSTRING] Missing docstring in 'mod::func' (function)",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 4)
        self.assertAlmostEqual(verdict.confidence, 0.0)

    def test_partial_violations_produce_partial_confidence(self):
        # Only one of four policies fires
        report = ["[TODO] TODO/FIXME comment in 'a.py': # TODO: fix"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertFalse(verdict.approved)
        self.assertGreater(verdict.confidence, 0.0)
        self.assertLess(verdict.confidence, 1.0)

    def test_verdict_summary_describes_rejection(self):
        report = ["Circular dependency detected: a -> b -> a"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertIn("rejected", verdict.summary.lower())

    def test_verdict_summary_describes_approval(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.PYTHON)
        self.assertIn("approved", verdict.summary.lower())


# ---------------------------------------------------------------------------
# Integration: Guardian -> Gatekeeper end-to-end
# ---------------------------------------------------------------------------

class TestPythonEndToEnd(unittest.TestCase):
    """Run real Guardian scans and feed results into the Gatekeeper."""

    def _evaluate(self, source: str, filename: str = "module.py"):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, filename)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(source)
            guardian = ArchitecturalGuardian()
            guardian.analyze_structure(tmpdir)
            violations = guardian.check_rules([])
        gk = Gatekeeper(PolicyConfig.for_python())
        return gk.evaluate(guardian_report=violations, language=Language.PYTHON)

    def test_todo_comment_detected_end_to_end(self):
        source = (
            'def process():\n'
            '    """Process something."""\n'
            '    # TODO: implement this properly\n'
            '    pass\n'
        )
        verdict = self._evaluate(source)
        self.assertTrue(any("[TODO]" in i for i in verdict.blocking_issues))

    def test_missing_docstring_detected_end_to_end(self):
        source = 'def undocumented():\n    return 42\n'
        verdict = self._evaluate(source)
        self.assertTrue(any("[DOCSTRING]" in i for i in verdict.blocking_issues))

    def test_fully_documented_function_passes(self):
        source = (
            'def documented():\n'
            '    """A perfectly documented function."""\n'
            '    return 42\n'
        )
        verdict = self._evaluate(source)
        self.assertFalse(any("[DOCSTRING]" in i for i in verdict.blocking_issues))

    def test_no_todo_in_clean_code(self):
        source = (
            'def clean():\n'
            '    """Clean function."""\n'
            '    return 1 + 1\n'
        )
        verdict = self._evaluate(source)
        self.assertFalse(any("[TODO]" in i for i in verdict.blocking_issues))


if __name__ == "__main__":
    unittest.main()
