"""Privilege escalation tools."""

from __future__ import annotations

from kratos.domain.entities import ToolDefinition

linpeas_run = ToolDefinition(
    name="linpeas_run",
    description=(
        "Run LinPEAS for automated Linux privilege escalation enumeration. "
        "Checks sudo, SUID, cron, capabilities, kernel, and more."
    ),
    parameters={
        "type": "object",
        "properties": {
            "flags": {
                "type": "string",
                "description": "LinPEAS flags (e.g., '-a' for all checks, '-s' for superfast)",
            },
        },
    },
)

sudo_check = ToolDefinition(
    name="sudo_check",
    description=(
        "Check sudo privileges for current user (sudo -l). "
        "Essential first step in privilege escalation."
    ),
    parameters={
        "type": "object",
        "properties": {
            "password": {
                "type": "string",
                "description": "User password if known (for 'sudo -l' with password prompt)",
            },
        },
    },
)

suid_find = ToolDefinition(
    name="suid_find",
    description=(
        "Find SUID/SGID binaries on the system. "
        "These may allow privilege escalation via GTFOBins techniques."
    ),
    parameters={
        "type": "object",
        "properties": {},
    },
)

hash_crack = ToolDefinition(
    name="hash_crack",
    description=(
        "Crack password hashes using hashcat or john. "
        "Supports MD5, SHA, NTLM, bcrypt, and many more."
    ),
    parameters={
        "type": "object",
        "properties": {
            "hash_value": {
                "type": "string",
                "description": "The hash to crack, or path to a file containing hashes",
            },
            "tool": {
                "type": "string",
                "description": "Tool to use: 'john' or 'hashcat'. Default: john",
            },
            "wordlist": {
                "type": "string",
                "description": "Wordlist path. Default: /usr/share/wordlists/rockyou.txt",
            },
            "hash_type": {
                "type": "string",
                "description": "Hash type (e.g., 'raw-md5' for john, '0' for hashcat MD5)",
            },
        },
        "required": ["hash_value"],
    },
)


def get_privesc_tools() -> list[ToolDefinition]:
    """Return all privilege escalation tool definitions."""
    return [linpeas_run, sudo_check, suid_find, hash_crack]
