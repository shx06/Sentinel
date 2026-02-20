"""
Sandbox Runner.

Executes arbitrary Python code inside a :class:`SandboxContainer` and
captures ``stdout``, ``stderr``, and the exit code.
"""

from __future__ import annotations

import io
import posixpath
import tarfile
import uuid
from dataclasses import dataclass

from .container import SandboxContainer

# Exit code produced by the ``timeout`` utility when a process is killed.
_TIMEOUT_EXIT_CODE = 124


@dataclass
class RunResult:
    """
    Result of a sandboxed code execution.

    Attributes:
        stdout: Standard output produced by the script.
        stderr: Standard error produced by the script.
        exit_code: Process exit code (``0`` == success).
        timed_out: ``True`` when execution was aborted due to the timeout.
    """

    stdout: str
    stderr: str
    exit_code: int
    timed_out: bool = False


class SandboxRunner:
    """
    Executes Python code strings inside an isolated Docker container.

    Requires a running :class:`SandboxContainer`.  The container must be
    started before calling :meth:`run_code` and stopped afterwards.

    Example::

        container = SandboxContainer()
        container.start()
        runner = SandboxRunner(container)
        result = runner.run_code("print('hello')")
        container.stop()
        print(result.stdout)   # "hello\\n"
    """

    def __init__(self, container: SandboxContainer) -> None:
        self._container = container

    def run_code(self, code: str, timeout: int = 5) -> RunResult:
        """
        Write *code* to a temp file inside the container and execute it.

        The script is executed via the system ``timeout`` utility so that
        runaway processes (e.g. infinite loops) are killed after *timeout*
        seconds.

        Args:
            code: Python source code to execute.
            timeout: Maximum wall-clock seconds allowed.  Defaults to ``5``.

        Returns:
            A :class:`RunResult` with stdout, stderr, exit code, and
            ``timed_out`` flag.

        Raises:
            RuntimeError: If the container has not been started.
        """
        container = self._container.container
        if container is None:
            raise RuntimeError("Container is not running. Call start() first.")

        # Write code into the container as a uniquely named temp file.
        filename = f"sentinel_{uuid.uuid4().hex}.py"
        script_path = posixpath.join("/tmp", filename)
        container.put_archive("/tmp", _build_tar(filename, code.encode()))

        # Run via the ``timeout`` utility so runaway scripts are killed.
        exit_code, output = container.exec_run(
            cmd=["timeout", str(timeout), "python", script_path],
            stdout=True,
            stderr=True,
            demux=True,
        )

        # Clean up the script file; best-effort – ignore errors.
        container.exec_run(cmd=["rm", "-f", script_path], stdout=False, stderr=False)

        raw_stdout, raw_stderr = output if isinstance(output, tuple) else (output, b"")
        timed_out = exit_code == _TIMEOUT_EXIT_CODE

        return RunResult(
            stdout=raw_stdout.decode(errors="replace") if raw_stdout else "",
            stderr=raw_stderr.decode(errors="replace") if raw_stderr else "",
            exit_code=exit_code,
            timed_out=timed_out,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_tar(filename: str, data: bytes) -> bytes:
    """
    Build an in-memory tar archive containing a single file.

    Args:
        filename: Name for the file inside the archive.
        data: Raw file content.

    Returns:
        Bytes of a valid tar archive.
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()
