"""Core domain entities for Kratos agent system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AttackPhase(str, Enum):
    """Current phase in the pentesting methodology."""

    RECON = "recon"
    SCANNING = "scanning"
    ENUMERATION = "enumeration"
    EXPLOITATION = "exploitation"
    PRIVESC = "privilege_escalation"
    POST_EXPLOIT = "post_exploitation"
    COMPLETE = "complete"


class MessageRole(str, Enum):
    """Role of a message in the conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A single message in the agent conversation."""

    role: MessageRole
    content: str
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ToolCall:
    """A tool invocation requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ToolResult:
    """Result from executing a tool."""

    tool_call_id: str
    output: str
    success: bool = True
    truncated: bool = False


@dataclass
class ToolDefinition:
    """Definition of a tool available to the agent."""

    name: str
    description: str
    parameters: dict[str, Any]
    execute: Any = None  # Callable, set at registration


@dataclass
class Target:
    """A pentesting target."""

    ip: str
    hostname: str | None = None
    ports: list[int] = field(default_factory=list)
    services: dict[int, str] = field(default_factory=dict)
    os_info: str | None = None


@dataclass
class Flag:
    """A captured flag."""

    value: str
    flag_type: str = "unknown"  # user, root, ctf
    source: str = ""


@dataclass
class SessionState:
    """Current state of an attack session."""

    target: Target | None = None
    phase: AttackPhase = AttackPhase.RECON
    flags: list[Flag] = field(default_factory=list)
    credentials: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    messages: list[Message] = field(default_factory=list)
    turn_count: int = 0
