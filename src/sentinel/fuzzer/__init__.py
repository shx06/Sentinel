"""
Adversarial Fuzzer module for Sentinel.

Automates the generation of "Chaos Data" to break code and ensure
robustness beyond happy-path testing.

Public API::

    from sentinel.fuzzer import AdversarialFuzzer, FuzzReport, FuzzGenerator
    from sentinel.fuzzer.strategies import STRATEGIES, get_strategies
"""

from .engine import AdversarialFuzzer, FuzzReport
from .generator import FuzzGenerator
from .strategies import STRATEGIES, get_strategies

__all__ = [
    "AdversarialFuzzer",
    "FuzzGenerator",
    "FuzzReport",
    "STRATEGIES",
    "get_strategies",
]
