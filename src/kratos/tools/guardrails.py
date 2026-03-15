"""Command guardrails for safe execution.

Validates commands before they run inside the Kali container.
Blocks destructive patterns while allowing offensive security tools.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

BLOCKED_PATTERNS: list[tuple[str, str]] = [
    (r"rm\s+-rf\s+/\s*$", "Recursive delete of root filesystem"),
    (r"rm\s+-rf\s+/\s+", "Recursive delete of root filesystem"),
    (r"mkfs\.", "Filesystem formatting"),
    (r"dd\s+.*of=/dev/[hs]d", "Raw disk write"),
    (r":()\s*{\s*:\s*\|\s*:\s*&\s*}\s*;", "Fork bomb"),
    (r">\s*/dev/[hs]d", "Raw disk write via redirect"),
    (r"chmod\s+-R\s+777\s+/\s*$", "Recursive chmod on root"),
    (r"curl.*\|\s*(ba)?sh", "Pipe remote script to shell"),
    (r"wget.*\|\s*(ba)?sh", "Pipe remote script to shell"),
]

TIMEOUT_COMMANDS: dict[str, int] = {
    "nmap": 300,
    "sqlmap": 600,
    "nikto": 300,
    "gobuster": 300,
    "ffuf": 300,
    "hydra": 600,
    "hashcat": 1800,
    "john": 1800,
    "msfconsole": 600,
    "linpeas": 300,
}


@dataclass
class GuardrailResult:
    """Result of a guardrail check."""

    allowed: bool
    reason: str = ""
    timeout: int = 120


def check_command(command: str) -> GuardrailResult:
    """Validate a command against safety guardrails.

    Returns a GuardrailResult indicating if the command is allowed.
    Offensive security tools (nmap, sqlmap, etc.) are permitted
    since they run inside an isolated Kali Docker container.
    """
    if not command or not command.strip():
        return GuardrailResult(allowed=False, reason="Empty command")

    stripped = command.strip()

    for pattern, description in BLOCKED_PATTERNS:
        if re.search(pattern, stripped, re.IGNORECASE):
            return GuardrailResult(
                allowed=False,
                reason=f"Blocked: {description}",
            )

    # Determine appropriate timeout based on tool
    first_token = stripped.split()[0].split("/")[-1]
    timeout = TIMEOUT_COMMANDS.get(first_token, 120)

    return GuardrailResult(allowed=True, timeout=timeout)
