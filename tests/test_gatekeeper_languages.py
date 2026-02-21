import unittest
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import PolicyConfig, NoCircularDependenciesPolicy

class TestPolyglotGatekeeper(unittest.TestCase):
    def setUp(self):
          # 1. Create default empty config
        config = PolicyConfig()
        
        # 2. Add our test policy using the API
        config.add_policy(NoCircularDependenciesPolicy())
        
        # 3. Pass it to Gatekeeper
        self.gatekeeper = Gatekeeper(config)

    def test_python_enforces_circular_deps(self):
        """Test that Python projects get blocked by circular dependencies."""
        # Mock a guardian report with a circular dependency violation
        guardian_report = ["Circular dependency detected: a -> b -> a"]
        
        # Run evaluation with Language.PYTHON
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.PYTHON
        )
        
        self.assertFalse(verdict.approved)
        self.assertIn("Circular", verdict.blocking_issues[0])

    def test_java_ignores_circular_deps_policy(self):
        """Test that Java projects IGNORE the Python-specific policy."""
        # Same report, but for Java
        guardian_report = ["Circular dependency detected: a -> b -> a"]
        
        # Run evaluation with Language.JAVA
        verdict = self.gatekeeper.evaluate(
            guardian_report=guardian_report,
            language=Language.JAVA
        )
        
        # Should be APPROVED because NoCircularDependenciesPolicy 
        # applies_to(JAVA) returns False
        self.assertTrue(verdict.approved)

if __name__ == '__main__':
    unittest.main()