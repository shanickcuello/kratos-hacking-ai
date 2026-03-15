"""Training data schema for Kratos fine-tuning.

Each training example is a multi-turn conversation in ChatML format.
Tool calls use special tags that the model learns to produce.

Example conversation:
[
  {"role": "system", "content": "You are Kratos, a cybersecurity AI agent..."},
  {"role": "user", "content": "Scan the target 10.10.10.1"},
  {"role": "assistant", "content": "I'll start with a comprehensive nmap scan.\n<tool_call>\n{\"name\": \"nmap_scan\", \"arguments\": {\"target\": \"10.10.10.1\", \"flags\": \"-sV -sC -p-\"}}\n</tool_call>"},
  {"role": "tool", "content": "<tool_result>\nPORT   STATE SERVICE VERSION\n22/tcp open  ssh     OpenSSH 8.9\n80/tcp open  http    Apache 2.4.52\n</tool_result>"},
  {"role": "assistant", "content": "Found 2 open ports:\n- **22/tcp**: SSH (OpenSSH 8.9)\n- **80/tcp**: HTTP (Apache 2.4.52)\n\nLet me enumerate the web server next.\n<tool_call>\n{\"name\": \"gobuster_dir\", \"arguments\": {\"url\": \"http://10.10.10.1\"}}\n</tool_call>"}
]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Turn:
    """A single turn in a training conversation."""

    role: Role
    content: str


@dataclass
class TrainingConversation:
    """A complete training example."""

    id: str
    turns: list[Turn]
    metadata: dict[str, Any] = field(default_factory=dict)
    # Metadata: source (writeup/synthetic/tool_output), difficulty,
    # categories (recon/web/privesc/crypto), tools_used, etc.

    def to_chatml(self) -> str:
        """Convert to ChatML string format for training."""
        parts = []
        for turn in self.turns:
            parts.append(f"<|im_start|>{turn.role.value}")
            parts.append(turn.content)
            parts.append("<|im_end|>")
        return "\n".join(parts)

    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            "id": self.id,
            "conversations": [
                {"role": t.role.value, "content": t.content}
                for t in self.turns
            ],
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TrainingConversation:
        """Load from dict."""
        turns = [
            Turn(role=Role(c["role"]), content=c["content"])
            for c in data["conversations"]
        ]
        return cls(
            id=data["id"],
            turns=turns,
            metadata=data.get("metadata", {}),
        )


# Tool call format the model should learn to produce
TOOL_CALL_FORMAT = """<tool_call>
{{"name": "{tool_name}", "arguments": {arguments_json}}}
</tool_call>"""

TOOL_RESULT_FORMAT = """<tool_result>
{output}
</tool_result>"""

# System prompt template used in ALL training data
SYSTEM_PROMPT_TEMPLATE = """You are Kratos, an elite cybersecurity AI agent specialized in penetration testing and CTF challenges.

You operate inside a Kali Linux environment with full access to pentesting tools.
When you need to execute a command or use a tool, wrap it in <tool_call> tags.

Available tools: {tool_list}

Methodology: Recon → Enumeration → Vulnerability Analysis → Exploitation → Privilege Escalation → Post-Exploitation

Rules:
- Explain your reasoning before each action
- Analyze tool output before deciding the next step
- Track discovered information (ports, services, credentials, flags)
- If stuck, try alternative approaches
- When you find a flag, clearly state it"""
