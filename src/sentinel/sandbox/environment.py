"""
Sandbox Environment Manager.

High-level context manager that prepares an isolated execution environment,
optionally installing Python dependencies inside the container before running
code via :class:`~sentinel.sandbox.runner.SandboxRunner`.
"""

from __future__ import annotations

from typing import List

from .container import SandboxContainer
from .runner import RunResult, SandboxRunner


class SandboxEnvironment:
    """
    High-level manager for a sandboxed Python execution environment.

    Handles the full lifecycle of a :class:`SandboxContainer`: starting it,
    optionally pre-installing pip dependencies, running code, and ensuring
    cleanup even when errors occur.

    Can be used as a plain object or as a context manager::

        with SandboxEnvironment() as env:
            env.install(["requests"])
            result = env.run_code("import requests; print(requests.__version__)")
            print(result.stdout)

    Attributes:
        image: Docker image used when starting the container.
    """

    def __init__(self, image: str = "python:3.11-slim") -> None:
        self.image = image
        self._container = SandboxContainer()
        self._runner: SandboxRunner | None = None

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "SandboxEnvironment":
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """
        Start the underlying container and initialise the runner.

        Must be called before :meth:`install` or :meth:`run_code` when *not*
        using the context-manager protocol.
        """
        self._container.start(image=self.image)
        self._runner = SandboxRunner(self._container)

    def stop(self) -> None:
        """
        Stop and remove the underlying container.

        Safe to call multiple times; subsequent calls are no-ops.
        """
        self._container.stop()
        self._runner = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self, packages: List[str], timeout: int = 60) -> RunResult:
        """
        Install one or more pip packages inside the container.

        Args:
            packages: List of package specifiers (e.g. ``["requests", "numpy==1.26"]``).
            timeout: Maximum seconds to wait for pip to finish.  Defaults to ``60``.

        Returns:
            A :class:`~sentinel.sandbox.runner.RunResult` from the pip invocation.

        Raises:
            RuntimeError: If the environment has not been started.
        """
        if self._runner is None:
            raise RuntimeError("Environment is not running. Call start() first.")

        container = self._container.container
        cmd = ["pip", "install"] + packages
        exit_code, output = container.exec_run(
            cmd=cmd,
            stdout=True,
            stderr=True,
            demux=True,
        )
        raw_stdout, raw_stderr = output if isinstance(output, tuple) else (output, b"")
        return RunResult(
            stdout=raw_stdout.decode(errors="replace") if raw_stdout else "",
            stderr=raw_stderr.decode(errors="replace") if raw_stderr else "",
            exit_code=exit_code,
        )

    def run_code(self, code: str, timeout: int = 5) -> RunResult:
        """
        Execute *code* in the prepared sandbox.

        Args:
            code: Python source code to run.
            timeout: Maximum seconds allowed for execution.  Defaults to ``5``.

        Returns:
            A :class:`~sentinel.sandbox.runner.RunResult`.

        Raises:
            RuntimeError: If the environment has not been started.
        """
        if self._runner is None:
            raise RuntimeError("Environment is not running. Call start() first.")

        return self._runner.run_code(code, timeout=timeout)
