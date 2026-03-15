"""General-purpose tools for command execution."""

from __future__ import annotations

from kratos.domain.entities import ToolDefinition

run_command = ToolDefinition(
    name="run_command",
    description=(
        "Execute a shell command inside the Kali Linux environment. "
        "Use this for any system command: nmap, gobuster, sqlmap, "
        "metasploit, file operations, networking, etc. "
        "The command runs in a Kali Linux container with full pentesting tools."
    ),
    parameters={
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute (e.g., 'nmap -sV 10.0.0.1')",
            },
        },
        "required": ["command"],
    },
)

read_file = ToolDefinition(
    name="read_file",
    description="Read the contents of a file in the Kali environment.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to read",
            },
        },
        "required": ["path"],
    },
)

write_file = ToolDefinition(
    name="write_file",
    description="Write content to a file in the Kali environment.",
    parameters={
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file to write",
            },
            "content": {
                "type": "string",
                "description": "Content to write to the file",
            },
        },
        "required": ["path", "content"],
    },
)


def get_general_tools() -> list[ToolDefinition]:
    """Return general-purpose tool definitions."""
    return [run_command, read_file, write_file]
