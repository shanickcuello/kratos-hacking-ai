"""Ports (interfaces) for the domain layer.

These define the contracts that adapters must implement.
The domain layer depends only on these abstractions, never on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from kratos.domain.entities import Message, ToolDefinition


class LLMPort(ABC):
    """Interface for LLM inference."""

    @abstractmethod
    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> Message:
        """Send messages and get a complete response."""

    @abstractmethod
    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[str]:
        """Send messages and stream the response token by token."""


class DockerPort(ABC):
    """Interface for executing commands in Docker containers."""

    @abstractmethod
    async def exec_command(
        self, command: str, timeout: int = 120
    ) -> str:
        """Execute a command and return output."""

    @abstractmethod
    async def exec_command_stream(
        self, command: str, timeout: int = 120
    ) -> AsyncIterator[str]:
        """Execute a command and stream output line by line."""

    @abstractmethod
    async def ensure_running(self) -> bool:
        """Ensure the executor container is running."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the executor container."""


class UIPort(ABC):
    """Interface for user interaction (CLI, TUI, etc.)."""

    @abstractmethod
    async def display_assistant(self, text: str) -> None:
        """Display assistant message."""

    @abstractmethod
    async def display_tool_output(
        self, tool_name: str, output: str
    ) -> None:
        """Display tool execution output."""

    @abstractmethod
    async def display_status(self, status: str) -> None:
        """Display status update."""

    @abstractmethod
    async def get_user_input(self) -> str:
        """Get input from the user."""

    @abstractmethod
    async def stream_token(self, token: str) -> None:
        """Display a single streamed token."""

    @abstractmethod
    async def start_thinking(self, message: str = "Thinking") -> None:
        """Show visual indication that the model is thinking."""

    @abstractmethod
    async def stop_thinking(self) -> None:
        """Stop the thinking indicator."""
