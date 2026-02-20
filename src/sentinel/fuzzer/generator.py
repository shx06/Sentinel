"""
Fuzz Input Generator.

Uses Python's :mod:`inspect` module to read a callable's type-annotated
signature and maps each parameter to the appropriate adversarial strategy
from :mod:`sentinel.fuzzer.strategies`.
"""

import inspect
import itertools
from typing import Any, Callable, Iterator, List, Tuple

from .strategies import get_strategies


class FuzzGenerator:
    """
    Generates adversarial input combinations for a target function.

    For each parameter in the function's signature the generator looks up
    the corresponding strategy from the strategy registry.  It then yields
    every combination of one value per parameter (cartesian product), so
    that every adversarial edge case is exercised independently.

    Parameters that carry no type annotation are mapped to ``[None]``.

    Example::

        def add(x: int, y: int) -> int:
            return x + y

        gen = FuzzGenerator()
        for inputs in gen.generate(add):
            print(inputs)   # e.g. (0, -1), (sys.maxsize, 0), …
    """

    def generate(
        self, target: Callable
    ) -> Iterator[Tuple[Any, ...]]:
        """
        Yield adversarial input tuples for *target*.

        Args:
            target: The callable whose signature is inspected.

        Yields:
            Tuples of arguments, one per call attempt.
        """
        param_strategies = self._build_param_strategies(target)
        if not param_strategies:
            yield ()
            return

        yield from self._cartesian(param_strategies)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_param_strategies(target: Callable) -> List[List[Any]]:
        """
        Inspect *target* and return a list of strategy value lists.

        One inner list is returned per positional parameter (``POSITIONAL_OR_KEYWORD``
        and ``POSITIONAL_ONLY``); ``*args``, ``**kwargs``, and keyword-only
        parameters are skipped.

        Args:
            target: Callable to inspect.

        Returns:
            List of adversarial value lists, one per positional parameter.
        """
        try:
            sig = inspect.signature(target)
        except (ValueError, TypeError):
            return []

        strategies: List[List[Any]] = []
        for param in sig.parameters.values():
            if param.kind in (
                param.VAR_POSITIONAL,
                param.VAR_KEYWORD,
                param.KEYWORD_ONLY,
            ):
                continue

            annotation = param.annotation
            if annotation is inspect.Parameter.empty:
                strategies.append([None])
            else:
                strategies.append(get_strategies(annotation))

        return strategies

    @staticmethod
    def _cartesian(lists: List[List[Any]]) -> Iterator[Tuple[Any, ...]]:
        """
        Yield cartesian-product tuples of elements from *lists*.

        Delegates to :func:`itertools.product` for lazy, memory-efficient
        generation.

        Args:
            lists: Non-empty list of non-empty lists.

        Yields:
            Tuples containing one element from each inner list.
        """
        yield from itertools.product(*lists)
