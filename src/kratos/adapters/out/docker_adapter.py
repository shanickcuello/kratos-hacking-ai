"""Docker adapter for executing commands in Kali Linux containers."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator

import docker
from docker.errors import NotFound

from kratos.config import config
from kratos.domain.ports import DockerPort

logger = logging.getLogger(__name__)

MAX_OUTPUT_CHARS = 15_000


class DockerAdapter(DockerPort):
    """Execute commands inside a Kali Linux Docker container."""

    def __init__(
        self,
        image: str | None = None,
        container_name: str = "kratos-kali",
    ):
        self._image = image or config.docker_image
        self._container_name = container_name
        self._client = docker.from_env()
        self._container = None

    async def ensure_running(self) -> bool:
        """Ensure the Kali executor container is running."""
        try:
            container = self._client.containers.get(self._container_name)
            if container.status != "running":
                container.start()
            self._container = container
            logger.info("Kali container '%s' is running", self._container_name)
            return True
        except NotFound:
            pass

        logger.info(
            "Starting Kali container '%s' from image '%s'",
            self._container_name,
            self._image,
        )
        self._container = self._client.containers.run(
            self._image,
            name=self._container_name,
            detach=True,
            tty=True,
            stdin_open=True,
            network_mode="host",
            remove=False,
        )
        return True

    async def exec_command(
        self, command: str, timeout: int = 120
    ) -> str:
        """Execute a command inside the Kali container."""
        if not self._container:
            await self.ensure_running()

        logger.debug("Executing in Kali: %s", command)
        try:
            exit_code, output = self._container.exec_run(
                ["bash", "-c", command],
                demux=False,
                environment={"TERM": "dumb"},
            )
            decoded = output.decode("utf-8", errors="replace") if output else ""

            # Truncate if too long
            if len(decoded) > MAX_OUTPUT_CHARS:
                decoded = (
                    decoded[:MAX_OUTPUT_CHARS]
                    + f"\n\n[OUTPUT TRUNCATED - {len(decoded)} chars total]"
                )

            if exit_code != 0:
                decoded += f"\n[Exit code: {exit_code}]"

            return decoded
        except Exception as e:
            return f"[Error executing command: {e}]"

    async def exec_command_stream(
        self, command: str, timeout: int = 120
    ) -> AsyncIterator[str]:
        """Execute a command and stream output line by line."""
        # For now, run and yield the full result
        # TODO: implement real streaming via docker exec attach
        result = await self.exec_command(command, timeout)
        for line in result.split("\n"):
            yield line

    async def stop(self) -> None:
        """Stop the Kali container."""
        if self._container:
            try:
                self._container.stop(timeout=5)
                logger.info("Kali container stopped")
            except Exception as e:
                logger.warning("Error stopping container: %s", e)
