import unittest
from sentinel.core.languages import Language
from sentinel.gatekeeper import Gatekeeper
from sentinel.gatekeeper.policy import PolicyConfig, NoCriticalBugsPolicy


class TestLanguageEnum(unittest.TestCase):
    def test_expected_languages_exist(self):
        """Language enum exposes the expected members."""
        self.assertIn(Language.PYTHON, Language)
        self.assertIn(Language.JAVA, Language)
        self.assertIn(Language.TYPESCRIPT, Language)
        self.assertIn(Language.JAVASCRIPT, Language)
        self.assertIn(Language.UNKNOWN, Language)


class TestPolicyConfig(unittest.TestCase):
    def test_add_and_retrieve_policies(self):
        """Policies added to PolicyConfig are retrievable in order."""
        config = PolicyConfig()
        policy = NoCriticalBugsPolicy()
        config.add_policy(policy)
        self.assertEqual(config.policies, [policy])

    def test_default_config_has_policies(self):
        """Default PolicyConfig is non-empty."""
        config = PolicyConfig.default()
        self.assertGreater(len(config.policies), 0)


class TestGatekeeperRouting(unittest.TestCase):
    def test_empty_policy_config_approves(self):
        """Gatekeeper with no policies always approves."""
        gatekeeper = Gatekeeper(PolicyConfig())
        verdict = gatekeeper.evaluate(language=Language.PYTHON)
        self.assertTrue(verdict.approved)
        self.assertEqual(verdict.confidence, 1.0)

    def test_unknown_language_skips_language_specific_policies(self):
        """Language.UNKNOWN causes language-specific policies to be skipped."""
        from sentinel.gatekeeper.policy import NoCircularDependenciesPolicy
        config = PolicyConfig()
        config.add_policy(NoCircularDependenciesPolicy())
        gatekeeper = Gatekeeper(config)
        # NoCircularDependenciesPolicy only applies to PYTHON, so UNKNOWN is approved
        verdict = gatekeeper.evaluate(
            guardian_report=["Circular dependency detected: a -> b -> a"],
            language=Language.UNKNOWN,
        )
        self.assertTrue(verdict.approved)


if __name__ == "__main__":
    unittest.main()
