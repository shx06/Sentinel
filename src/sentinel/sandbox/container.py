"""
Sandbox Container Manager.

Wraps the Docker Python SDK to launch and tear down isolated, ephemeral
containers for safe code execution.
"""

import docker
from docker.models.containers import Container


class SandboxContainer:
    """
    Manages a short-lived Docker container used as an execution sandbox.

    The container is started with restricted network and filesystem access
    so that code running inside it cannot affect the host machine.

    Example::

        container = SandboxContainer()
        container.start()
        # … run code inside container …
        container.stop()
    """

    def __init__(self) -> None:
        self._client: docker.DockerClient = docker.from_env()
        self._container: Container | None = None

    def start(self, image: str = "python:3.11-slim") -> None:
        """
        Pull (if necessary) and start an isolated container.

        The container is created with:

        * ``network_disabled=True`` – no outbound network access.
        * ``read_only=False`` – writes are confined to the container layer.
        * ``auto_remove=False`` – we remove it explicitly in :meth:`stop`.

        Args:
            image: Docker image to use.  Defaults to ``"python:3.11-slim"``.
        """
        self._container = self._client.containers.run(
            image,
            command="sleep infinity",
            detach=True,
            network_disabled=True,
            auto_remove=False,
        )

    def stop(self) -> None:
        """
        Stop and forcefully remove the running container.

        Safe to call even if the container has already exited.
        """
        if self._container is not None:
            try:
                self._container.remove(force=True)
            except docker.errors.NotFound:
                pass
            finally:
                self._container = None

    @property
    def container(self) -> Container | None:
        """The underlying :class:`docker.models.containers.Container`, or ``None``."""
        return self._container
