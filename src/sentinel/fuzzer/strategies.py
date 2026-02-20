"""
Fuzzing Strategy Engine.

Provides a registry of chaos-data generators for standard Python types.
Each strategy returns a list of adversarial values designed to expose
edge-case bugs in target functions.
"""

import sys
from typing import Any, Dict, List, Type

# ---------------------------------------------------------------------------
# Individual strategy lists
# ---------------------------------------------------------------------------

_INT_VALUES: List[Any] = [0, -1, 1, sys.maxsize, -sys.maxsize - 1]

_STR_VALUES: List[Any] = [
    "",
    "A" * 10_000,
    "' OR '1'='1",
    " ",
    "\n\t\r",
    "\x00",
]

_FLOAT_VALUES: List[Any] = [
    0.0,
    -0.0,
    float("nan"),
    float("inf"),
    float("-inf"),
    1e308,
    -1e308,
]

_BOOL_VALUES: List[Any] = [True, False]

_LIST_VALUES: List[Any] = [
    [],
    [[]],
    [{"key": []}],
    list(range(1_000)),
]

_DICT_VALUES: List[Any] = [
    {},
    {"a": {}},
    {"a": {"b": {}}},
    {str(i): i for i in range(100)},
]

# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

#: Maps a Python type to the list of adversarial values for that type.
STRATEGIES: Dict[Type, List[Any]] = {
    int: _INT_VALUES,
    str: _STR_VALUES,
    float: _FLOAT_VALUES,
    bool: _BOOL_VALUES,
    list: _LIST_VALUES,
    dict: _DICT_VALUES,
}


def get_strategies(type_hint: Type) -> List[Any]:
    """
    Return adversarial values for the given type hint.

    Falls back to ``[None]`` (a single-element list containing ``None``) when
    the type is not recognised so that the fuzzer can still exercise the
    function.

    Args:
        type_hint: A Python type (e.g. ``int``, ``str``).

    Returns:
        List of adversarial values for that type.
    """
    return STRATEGIES.get(type_hint, [None])
