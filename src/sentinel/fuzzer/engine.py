"""
Adversarial Fuzz Engine.

Drives the fuzzing loop: generates inputs via :class:`FuzzGenerator`,
executes the target function, catches any raised exceptions, and
assembles a :class:`FuzzReport` summarising every crashing input set.
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List, Tuple

from .generator import FuzzGenerator


@dataclass
class FuzzReport:
    """
    Summary of a fuzzing run.

    Attributes:
        target_name: Qualified name of the function under test.
        total_iterations: Number of input combinations attempted.
        failures: List of ``(inputs, exception)`` pairs for every call
                  that raised an unhandled exception.
    """

    target_name: str
    total_iterations: int
    failures: List[Tuple[Tuple[Any, ...], Exception]] = field(
        default_factory=list
    )

    @property
    def failure_count(self) -> int:
        """Number of crashing input combinations found."""
        return len(self.failures)

    @property
    def passed(self) -> bool:
        """``True`` when no crashes were detected."""
        return self.failure_count == 0


class AdversarialFuzzer:
    """
    Proactively searches for bugs by bombarding a function with chaos data.

    Uses :class:`~sentinel.fuzzer.generator.FuzzGenerator` to derive
    adversarial inputs from the function's type annotations, then calls the
    function with each combination, capturing any exceptions.

    Example::

        def divide(a: int, b: int) -> float:
            return a / b

        fuzzer = AdversarialFuzzer()
        report = fuzzer.fuzz(divide)
        print(report.failure_count)   # e.g. 5  (ZeroDivisionError cases)
    """

    def __init__(self) -> None:
        self._generator = FuzzGenerator()

    def fuzz(
        self, target_function: Callable, iterations: int = 100
    ) -> FuzzReport:
        """
        Fuzz *target_function* and return a :class:`FuzzReport`.

        The fuzzer generates up to *iterations* adversarial input tuples
        from the function's type-annotated signature.  Each tuple is passed
        as positional arguments to the function.  If the call raises any
        :class:`Exception` the inputs and the exception are recorded as a
        failure.

        Args:
            target_function: The callable to test.
            iterations: Maximum number of input combinations to attempt.
                        Defaults to ``100``.

        Returns:
            A :class:`FuzzReport` describing the run.
        """
        name = getattr(target_function, "__qualname__", repr(target_function))
        report = FuzzReport(target_name=name, total_iterations=0)

        for inputs in self._generator.generate(target_function):
            if report.total_iterations >= iterations:
                break

            report.total_iterations += 1
            try:
                target_function(*inputs)
            except Exception as exc:  # noqa: BLE001 – intentional: capture any application-level exception
                report.failures.append((inputs, exc))

        return report
