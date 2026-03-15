"""Ollama adapter for LLM inference."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import ollama

from kratos.config import config
from kratos.domain.entities import (
    Message,
    MessageRole,
    ToolCall,
    ToolDefinition,
)
from kratos.domain.ports import LLMPort

logger = logging.getLogger(__name__)


def _messages_to_ollama(messages: list[Message]) -> list[dict[str, Any]]:
    """Convert domain messages to Ollama format."""
    result = []
    for msg in messages:
        entry: dict[str, Any] = {
            "role": msg.role.value,
            "content": msg.content or "",
        }
        if msg.tool_calls:
            entry["tool_calls"] = [
                {
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                }
                for tc in msg.tool_calls
            ]
        result.append(entry)
    return result


def _tools_to_ollama(
    tools: list[ToolDefinition] | None,
) -> list[dict[str, Any]] | None:
    """Convert domain tool definitions to Ollama format."""
    if not tools:
        return None
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in tools
    ]


def _parse_tool_calls(
    raw_calls: list[dict[str, Any]] | None,
) -> list[ToolCall] | None:
    """Parse Ollama tool calls into domain ToolCall objects."""
    if not raw_calls:
        return None
    calls = []
    for i, rc in enumerate(raw_calls):
        fn = rc.get("function", rc)
        args = fn.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {"raw": args}
        calls.append(
            ToolCall(
                id=f"call_{i}",
                name=fn.get("name", "unknown"),
                arguments=args,
            )
        )
    return calls if calls else None


class OllamaAdapter(LLMPort):
    """Ollama-based LLM adapter."""

    def __init__(
        self,
        model: str | None = None,
        host: str | None = None,
    ):
        self._model = model or config.model
        self._client = ollama.Client(host=host or config.ollama_host)

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> Message:
        """Send messages and get a complete response."""
        ollama_msgs = _messages_to_ollama(messages)
        ollama_tools = _tools_to_ollama(tools)

        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": ollama_msgs,
        }
        if ollama_tools:
            kwargs["tools"] = ollama_tools

        response = self._client.chat(**kwargs)

        msg = response.get("message", response)
        tool_calls = _parse_tool_calls(msg.get("tool_calls"))

        return Message(
            role=MessageRole.ASSISTANT,
            content=msg.get("content", ""),
            tool_calls=tool_calls,
        )

    async def chat_stream(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
    ) -> AsyncIterator[str]:
        """Stream response tokens. Falls back to non-streaming if tools present."""
        if tools:
            # Ollama streaming + tools is unreliable, fall back
            response = await self.chat(messages, tools)
            if response.content:
                yield response.content
            return

        ollama_msgs = _messages_to_ollama(messages)
        stream = self._client.chat(
            model=self._model,
            messages=ollama_msgs,
            stream=True,
        )
        for chunk in stream:
            msg = chunk.get("message", chunk)
            token = msg.get("content", "")
            if token:
                yield token
