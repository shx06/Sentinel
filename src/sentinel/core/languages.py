"""
Supported programming languages for the Sentinel Gatekeeper.

Defines the :class:`Language` enum used to tag a code-change context so
that language-specific :class:`~sentinel.gatekeeper.policy.Policy`
implementations can opt-in or opt-out during evaluation.
"""

from enum import Enum, auto


class Language(Enum):
    """Enumeration of programming languages understood by Sentinel."""

    PYTHON = auto()
    JAVA = auto()
    TYPESCRIPT = auto()
    JAVASCRIPT = auto()
    UNKNOWN = auto()
