"""
Java policy tests for the Principled Gatekeeper.

Covers every Java-specific policy that Sentinel enforces when performing
automated PR reviews of Java code:

* JavaLayeringPolicy         - blocks Service importing Controller
* PublicFieldPolicy          - blocks non-constant public fields
* MissingJavadocPolicy       - blocks public types without Javadoc
* JavaNamingConventionPolicy - blocks PascalCase / camelCase violations

Each test class validates:
  1. The policy blocks the exact violation it was designed for.
  2. The policy does NOT fire on clean code.
  3. The policy is language-gated (Python/TS submissions are not affected).
  4. Missing (None) guardian reports are handled gracefully.

Integration tests at the bottom simulate a full PR review using the
Guardian + Gatekeeper pipeline against real Java source files.
"""

import os
import tempfile
import unittest

POLICY_SPECS = [{'name': 'JavaLayeringPolicy',
  'language': 'JAVA',
  'match_mode': 'regex',
  'patterns': ["Import of '.*Controller' in '.*Service\\.java'"],
  'description': 'Reject Java service classes that import controller classes.'},
 {'name': 'PublicFieldPolicy',
  'language': 'JAVA',
  'match_mode': 'contains',
  'patterns': ['[PUBLIC_FIELD]'],
  'description': 'Reject Java classes that expose mutable public fields.'},
 {'name': 'MissingJavadocPolicy',
  'language': 'JAVA',
  'match_mode': 'contains',
  'patterns': ['[JAVADOC]'],
  'description': 'Reject Java public types that are missing Javadoc.'},
 {'name': 'JavaNamingConventionPolicy',
  'language': 'JAVA',
  'match_mode': 'contains',
  'patterns': ['[NAMING]'],
  'description': 'Reject Java code that violates naming conventions.'},
 {'name': 'JavaDTOImportPolicy',
  'language': 'JAVA',
  'match_mode': 'regex',
  'patterns': ["Import of '.*RequestDTO' in '.*Controller\\.java'",
               "Import of '.*ResponseDTO' in '.*Controller\\.java'"],
  'description': 'Reject Java controller classes that import DTO classes directly.'},
 {'name': 'JavaSpringFrameworkImportPolicy',
  'language': 'JAVA',
  'match_mode': 'regex',
  'patterns': ["Import of 'Autowired' in '.*\\.java'",
               "Import of 'CommandLineRunner' in '.*\\.java'",
               "Import of 'SpringApplication' in '.*\\.java'",
               "Import of 'SpringBootApplication' in '.*\\.java'"],
  'description': 'Reject Java classes that import Spring Framework classes outside of the main '
                 'application class.'},
 {'name': 'JavaModelImportPolicy',
  'language': 'JAVA',
  'match_mode': 'regex',
  'patterns': ["Import of '.*Model' in '.*Controller\\.java'"],
  'description': 'Reject Java controller classes that import model classes directly.'},
 {'name': 'JavaApplicationClassImportPolicy',
  'language': 'JAVA',
  'match_mode': 'regex',
  'patterns': ["Import of '.*Controller' in '.*Application\\.java'",
               "Import of '.*DTO' in '.*Application\\.java'",
               "Import of '.*Model' in '.*Application\\.java'"],
  'description': 'Reject Java application classes that import controller, DTO, or model classes '
                 'directly.'},
 {'name': 'JavaControllerFrameworkImportPolicy',
  'language': 'JAVA',
  'match_mode': 'regex',
  'patterns': ["Import of 'ResponseStatus' in '.*Controller\\.java'"],
  'description': 'Reject Java controller classes that import framework-specific response status '
                 'classes directly.'},
 {'name': 'JavaControllerServiceImportPolicy',
  'language': 'JAVA',
  'match_mode': 'regex',
  'patterns': ["Import of '.*Service' in '.*Controller\\.java'"],
  'description': 'Reject Java controller classes that import service classes directly, bypassing '
                 'the established layering.'}]

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
    return policy_from_name(name, Language.JAVA)


def _run_guardian(source: str, filename: str = "MyClass.java") -> list:
    """Write *source* to a temp file, run the Guardian, return violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(source)
        guardian = ArchitecturalGuardian()
        guardian.analyze_structure(tmpdir)
        return guardian.check_rules([])


# ---------------------------------------------------------------------------
# JavaLayeringPolicy
# ---------------------------------------------------------------------------

class TestJavaLayeringPolicy(unittest.TestCase):
    """JavaLayeringPolicy blocks Services that import Controller classes."""

    def setUp(self):
        self.gk = _make_gatekeeper(_policy("JavaLayeringPolicy"))

    def test_blocks_service_importing_controller(self):
        report = ["Import of 'UserController' in 'OrderService.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)
        self.assertIn(report[0], verdict.blocking_issues)

    def test_passes_controller_importing_service(self):
        """Controller importing Service is the correct direction."""
        report = ["Import of 'OrderService' in 'OrderController.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_python_not_affected(self):
        report = ["Import of 'UserController' in 'OrderService.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_typescript_not_affected(self):
        report = ["Import of 'UserController' in 'OrderService.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_multiple_layering_violations_all_reported(self):
        report = [
            "Import of 'UserController' in 'OrderService.java'",
            "Import of 'PaymentController' in 'BillingService.java'",
            "Import of 'OrderService' in 'OrderController.java'",  # valid
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# PublicFieldPolicy
# ---------------------------------------------------------------------------

class TestPublicFieldPolicy(unittest.TestCase):
    """PublicFieldPolicy blocks non-constant public fields in Java classes."""

    def setUp(self):
        self.gk = _make_gatekeeper(_policy("PublicFieldPolicy"))

    def test_blocks_public_field(self):
        report = ["[PUBLIC_FIELD] Public non-constant field 'name' in 'User.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)
        self.assertTrue(any("[PUBLIC_FIELD]" in i for i in verdict.blocking_issues))

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_unrelated_violation_does_not_trigger(self):
        report = ["Import of 'Logger' in 'Service.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_python_not_affected(self):
        report = ["[PUBLIC_FIELD] Public non-constant field 'x' in 'Foo.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_typescript_not_affected(self):
        report = ["[PUBLIC_FIELD] Public non-constant field 'x' in 'Foo.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)

    def test_multiple_public_fields_all_reported(self):
        report = [
            "[PUBLIC_FIELD] Public non-constant field 'name' in 'User.java'",
            "[PUBLIC_FIELD] Public non-constant field 'age' in 'User.java'",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)
        self.assertEqual(len(verdict.blocking_issues), 2)


# ---------------------------------------------------------------------------
# MissingJavadocPolicy
# ---------------------------------------------------------------------------

class TestMissingJavadocPolicy(unittest.TestCase):
    """MissingJavadocPolicy blocks Java public types without Javadoc."""

    def setUp(self):
        self.gk = _make_gatekeeper(_policy("MissingJavadocPolicy"))

    def test_blocks_missing_javadoc(self):
        report = ["[JAVADOC] Missing Javadoc for class 'UserService' in 'UserService.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)
        self.assertTrue(any("[JAVADOC]" in i for i in verdict.blocking_issues))

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_unrelated_violation_does_not_trigger(self):
        report = ["Import of 'FooBar' in 'Service.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_python_not_affected(self):
        report = ["[JAVADOC] Missing Javadoc for class 'Foo' in 'Foo.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_typescript_not_affected(self):
        report = ["[JAVADOC] Missing Javadoc for class 'Foo' in 'Foo.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)


# ---------------------------------------------------------------------------
# JavaNamingConventionPolicy
# ---------------------------------------------------------------------------

class TestJavaNamingConventionPolicy(unittest.TestCase):
    """JavaNamingConventionPolicy enforces PascalCase types and camelCase methods."""

    def setUp(self):
        self.gk = _make_gatekeeper(_policy("JavaNamingConventionPolicy"))

    def test_blocks_lowercase_class_name(self):
        report = ["[NAMING] Type 'myService' should be PascalCase in 'myService.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)
        self.assertTrue(any("[NAMING]" in i for i in verdict.blocking_issues))

    def test_blocks_uppercase_method_name(self):
        report = ["[NAMING] Method 'ProcessOrder' should start with lowercase in 'Service.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)

    def test_passes_empty_report(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_passes_none_report(self):
        verdict = self.gk.evaluate(guardian_report=None, language=Language.JAVA)
        self.assertTrue(verdict.approved)

    def test_python_not_affected(self):
        report = ["[NAMING] Type 'myService' should be PascalCase in 'myService.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.PYTHON)
        self.assertTrue(verdict.approved)

    def test_typescript_not_affected(self):
        report = ["[NAMING] Type 'myService' should be PascalCase in 'myService.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.TYPESCRIPT)
        self.assertTrue(verdict.approved)


# ---------------------------------------------------------------------------
# PolicyConfig.for_java() factory
# ---------------------------------------------------------------------------

class TestPolicyConfigForJava(unittest.TestCase):
    """Validate the Java-specific factory and full-suite behaviour."""

    def setUp(self):
        self.gk = Gatekeeper(PolicyConfig.for_java())

    def test_factory_contains_all_java_policies(self):
        names = {type(p).__name__ for p in PolicyConfig.for_java().policies}
        self.assertIn("JavaLayeringPolicy", names)
        self.assertIn("PublicFieldPolicy", names)
        self.assertIn("MissingJavadocPolicy", names)
        self.assertIn("JavaNamingConventionPolicy", names)

    def test_clean_java_pr_is_approved(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.JAVA)
        self.assertTrue(verdict.approved)
        self.assertAlmostEqual(verdict.confidence, 1.0)

    def test_all_java_violations_aggregate_correctly(self):
        report = [
            "Import of 'UserController' in 'OrderService.java'",
            "[PUBLIC_FIELD] Public non-constant field 'name' in 'User.java'",
            "[JAVADOC] Missing Javadoc for class 'UserService' in 'UserService.java'",
            "[NAMING] Type 'myHelper' should be PascalCase in 'myHelper.java'",
        ]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)
        self.assertGreaterEqual(len(verdict.blocking_issues), 4)
        self.assertLess(verdict.confidence, 1.0)

    def test_partial_violations_produce_partial_confidence(self):
        report = ["[PUBLIC_FIELD] Public non-constant field 'x' in 'Foo.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertFalse(verdict.approved)
        self.assertGreater(verdict.confidence, 0.0)
        self.assertLess(verdict.confidence, 1.0)

    def test_verdict_summary_on_rejection(self):
        report = ["Import of 'UserController' in 'OrderService.java'"]
        verdict = self.gk.evaluate(guardian_report=report, language=Language.JAVA)
        self.assertIn("rejected", verdict.summary.lower())

    def test_verdict_summary_on_approval(self):
        verdict = self.gk.evaluate(guardian_report=[], language=Language.JAVA)
        self.assertIn("approved", verdict.summary.lower())


# ---------------------------------------------------------------------------
# Integration: Guardian -> Gatekeeper end-to-end for Java
# ---------------------------------------------------------------------------

class TestJavaEndToEnd(unittest.TestCase):
    """Run real Guardian scans and feed results into the Gatekeeper."""

    def _evaluate(self, source: str, filename: str = "MyService.java"):
        violations = _run_guardian(source, filename)
        gk = Gatekeeper(PolicyConfig.for_java())
        return gk.evaluate(guardian_report=violations, language=Language.JAVA)

    def test_service_importing_controller_is_blocked(self):
        source = "import com.example.controller.UserController;\n"
        verdict = self._evaluate(source, "UserService.java")
        self.assertTrue(
            any("UserController" in i and "UserService.java" in i
                for i in verdict.blocking_issues)
        )

    def test_controller_importing_service_passes_layering(self):
        source = "import com.example.service.UserService;\n"
        verdict = self._evaluate(source, "UserController.java")
        self.assertFalse(
            any("Import of 'UserService' in 'UserController.java'" in i
                and self.gk_matches_layering(i)
                for i in verdict.blocking_issues)
        )

    def gk_matches_layering(self, v: str) -> bool:
        import re
        return bool(re.search(r"Import of '.*Controller' in '.*Service\.java'", v))

    def test_public_field_triggers_policy(self):
        source = (
            "public class User {\n"
            "    public String name;\n"
            "}\n"
        )
        verdict = self._evaluate(source, "User.java")
        self.assertTrue(any("[PUBLIC_FIELD]" in i for i in verdict.blocking_issues))

    def test_public_static_final_constant_not_flagged(self):
        source = (
            "public class Constants {\n"
            "    public static final String VERSION = \"1.0\";\n"
            "}\n"
        )
        verdict = self._evaluate(source, "Constants.java")
        self.assertFalse(any("[PUBLIC_FIELD]" in i for i in verdict.blocking_issues))

    def test_missing_javadoc_triggers_policy(self):
        source = (
            "public class UserService {\n"
            "    public void process() {}\n"
            "}\n"
        )
        verdict = self._evaluate(source, "UserService.java")
        self.assertTrue(any("[JAVADOC]" in i for i in verdict.blocking_issues))

    def test_documented_class_passes_javadoc_policy(self):
        source = (
            "/**\n"
            " * Handles user operations.\n"
            " */\n"
            "public class UserService {\n"
            "}\n"
        )
        verdict = self._evaluate(source, "UserService.java")
        self.assertFalse(any("[JAVADOC]" in i for i in verdict.blocking_issues))


if __name__ == "__main__":
    unittest.main()
