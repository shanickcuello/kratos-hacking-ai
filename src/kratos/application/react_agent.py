"""ReAct agent loop: Reason -> Act -> Observe -> Repeat."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from jinja2 import Template

from kratos.config import config
from kratos.domain.entities import (
    Message,
    MessageRole,
    SessionState,
    ToolCall,
    ToolResult,
)
from kratos.domain.ports import DockerPort, LLMPort, UIPort
from kratos.tools.guardrails import check_command

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"
# Patterns the model may produce for tool calls
_TOOL_CALL_PATTERNS = [
    re.compile(r"<tool_call>\s*({.*?})\s*</tool_call>", re.DOTALL),
    re.compile(r"<\|im_start\|>\s*({.*?})\s*(?:<\|im_end\|>|$)", re.DOTALL),
    re.compile(
        r'(?:^|\n)\s*({"name"\s*:\s*"\w+"\s*,\s*"arguments"\s*:\s*{.*?}})',
        re.DOTALL,
    ),
]


def _parse_tool_calls_from_text(text: str) -> list[ToolCall]:
    """Extract tool-call JSON blocks from assistant text."""
    calls: list[ToolCall] = []
    for pattern in _TOOL_CALL_PATTERNS:
        for match in pattern.finditer(text):
            try:
                data = json.loads(match.group(1))
                if "name" in data:
                    calls.append(ToolCall(
                        id=f"call_{len(calls)}",
                        name=data["name"],
                        arguments=data.get("arguments", {}),
                    ))
            except json.JSONDecodeError:
                logger.warning("Bad tool_call JSON: %s", match.group(1)[:200])
        if calls:
            break  # Use first matching pattern
    return calls


def _strip_tool_tags(text: str) -> str:
    """Return text with tool-call blocks removed."""
    cleaned = text
    for pattern in _TOOL_CALL_PATTERNS:
        cleaned = pattern.sub("", cleaned)
    # Also strip stray ChatML tokens
    cleaned = re.sub(r"<\|im_start\|>", "", cleaned)
    cleaned = re.sub(r"<\|im_end\|>", "", cleaned)
    return cleaned.strip()


def _load_system_prompt(
    target_ip: str | None = None,
    target_hostname: str | None = None,
    mission: str | None = None,
) -> str:
    """Load and render the system prompt template."""
    path = _PROMPT_DIR / "red_team.md"
    try:
        template = Template(path.read_text())
    except FileNotFoundError:
        return "You are Kratos, a cybersecurity AI agent."
    return template.render(
        target_ip=target_ip,
        target_hostname=target_hostname,
        mission=mission,
    )


# ---------------------------------------------------------------------------
# Tool → shell command builders
# ---------------------------------------------------------------------------

_TOOL_CMD_BUILDERS: dict[str, callable] = {}


def _cmd(name: str):
    """Decorator to register a tool command builder."""
    def _decorator(fn):
        _TOOL_CMD_BUILDERS[name] = fn
        return fn
    return _decorator


@_cmd("run_command")
def _build_run_command(args: dict) -> str:
    return args.get("command", "")


@_cmd("read_file")
def _build_read_file(args: dict) -> str:
    return f"cat {args.get('path', '')}"


@_cmd("write_file")
def _build_write_file(args: dict) -> str:
    path = args.get("path", "")
    content = args.get("content", "")
    return f"cat > {path} << 'KRATOSEOF'\n{content}\nKRATOSEOF"


@_cmd("nmap_scan")
def _build_nmap(args: dict) -> str:
    flags = args.get("flags", "-sV -sC")
    return f"nmap {flags} {args['target']}"


@_cmd("gobuster_dir")
def _build_gobuster(args: dict) -> str:
    wl = args.get("wordlist", "/usr/share/wordlists/dirb/common.txt")
    ext = f" -x {args['extensions']}" if args.get("extensions") else ""
    return f"gobuster dir -u {args['url']} -w {wl}{ext}"


@_cmd("ffuf_fuzz")
def _build_ffuf(args: dict) -> str:
    wl = args.get("wordlist", "/usr/share/seclists/Discovery/Web-Content/common.txt")
    extra = f" {args['flags']}" if args.get("flags") else ""
    return f"ffuf -u {args['url']} -w {wl}{extra}"


@_cmd("dns_enum")
def _build_dns(args: dict) -> str:
    ns = f" @{args['nameserver']}" if args.get("nameserver") else ""
    return f"dig {args['domain']} any +noall +answer{ns}"


@_cmd("sqlmap_inject")
def _build_sqlmap(args: dict) -> str:
    extra = f" {args['flags']}" if args.get("flags") else ""
    return f"sqlmap -u '{args['url']}' --batch{extra}"


@_cmd("nikto_scan")
def _build_nikto(args: dict) -> str:
    extra = f" {args['flags']}" if args.get("flags") else ""
    return f"nikto -h {args['host']}{extra}"


@_cmd("curl_request")
def _build_curl(args: dict) -> str:
    method = args.get("method", "GET")
    parts = [f"curl -s -X {method}"]
    if args.get("headers"):
        for h in args["headers"].split(","):
            parts.append(f"-H '{h.strip()}'")
    if args.get("data"):
        parts.append(f"-d '{args['data']}'")
    if args.get("flags"):
        parts.append(args["flags"])
    parts.append(f"'{args['url']}'")
    return " ".join(parts)


@_cmd("searchsploit")
def _build_searchsploit(args: dict) -> str:
    extra = f" {args['flags']}" if args.get("flags") else ""
    return f"searchsploit {args['query']}{extra}"


@_cmd("metasploit_run")
def _build_msf(args: dict) -> str:
    return f"msfconsole -q -x '{args['commands']}'"


@_cmd("hydra_brute")
def _build_hydra(args: dict) -> str:
    return f"hydra {args['flags']} {args['target']} {args['service']}"


@_cmd("linpeas_run")
def _build_linpeas(args: dict) -> str:
    flags = args.get("flags", "")
    return f"linpeas.sh {flags}".strip()


@_cmd("sudo_check")
def _build_sudo(args: dict) -> str:
    pw = args.get("password")
    if pw:
        return f"echo '{pw}' | sudo -S -l"
    return "sudo -l"


@_cmd("suid_find")
def _build_suid(_args: dict) -> str:
    return "find / -perm -4000 -type f 2>/dev/null"


@_cmd("hash_crack")
def _build_hash_crack(args: dict) -> str:
    tool = args.get("tool", "john")
    wl = args.get("wordlist", "/usr/share/wordlists/rockyou.txt")
    h = args["hash_value"]
    if tool == "hashcat":
        ht = f" -m {args['hash_type']}" if args.get("hash_type") else ""
        return f"hashcat -a 0{ht} '{h}' {wl} --force"
    fmt = f" --format={args['hash_type']}" if args.get("hash_type") else ""
    return f"john{fmt} --wordlist={wl} '{h}'"


# ---------------------------------------------------------------------------
# Tool execution
# ---------------------------------------------------------------------------

async def _execute_tool(
    tool_name: str,
    arguments: dict,
    docker: DockerPort,
) -> ToolResult:
    """Build shell command from tool call, validate, and execute."""
    builder = _TOOL_CMD_BUILDERS.get(tool_name)
    if not builder:
        return ToolResult(
            tool_call_id=tool_name,
            output=f"Unknown tool: {tool_name}",
            success=False,
        )

    cmd = builder(arguments)
    guard = check_command(cmd)
    if not guard.allowed:
        return ToolResult(
            tool_call_id=tool_name,
            output=f"[BLOCKED] {guard.reason}",
            success=False,
        )

    output = await docker.exec_command(cmd, timeout=guard.timeout)
    success = "[Exit code:" not in output or "[Exit code: 0]" in output
    return ToolResult(
        tool_call_id=tool_name, output=output, success=success
    )


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run_react_loop(
    llm: LLMPort,
    docker: DockerPort,
    ui: UIPort,
    target_ip: str | None = None,
    mission: str | None = None,
) -> SessionState:
    """Run the ReAct agent loop until completion or max turns."""
    state = SessionState()

    system_prompt = _load_system_prompt(
        target_ip=target_ip, mission=mission
    )
    state.messages.append(
        Message(role=MessageRole.SYSTEM, content=system_prompt)
    )

    await ui.display_status(
        f"Kratos ready | Model: {config.model} | Max turns: {config.max_turns}"
    )

    while state.turn_count < config.max_turns:
        user_input = await ui.get_user_input()
        if not user_input:
            continue
        if user_input.lower() in ("/quit", "/exit", "/q"):
            break

        state.messages.append(
            Message(role=MessageRole.USER, content=user_input)
        )
        state.turn_count += 1

        # Agent loop: keep calling tools until LLM stops requesting them
        while True:
            # No native tool calling — model uses <tool_call> tags
            await ui.start_thinking("Kratos is analyzing")
            response = await llm.chat(state.messages)
            await ui.stop_thinking()
            parsed_calls = _parse_tool_calls_from_text(
                response.content or ""
            )

            display_text = _strip_tool_tags(response.content or "")
            if display_text:
                await ui.display_assistant(display_text)

            if not parsed_calls:
                state.messages.append(response)
                break

            state.messages.append(response)

            for tc in parsed_calls:
                await ui.start_thinking(f"Running {tc.name}")
                await ui.display_status(
                    f"Running: {tc.name}({tc.arguments})"
                )
                result = await _execute_tool(
                    tc.name, tc.arguments, docker
                )
                await ui.stop_thinking()
                await ui.display_tool_output(tc.name, result.output)
                state.messages.append(
                    Message(
                        role=MessageRole.TOOL,
                        content=f"<tool_result>\n{result.output}\n</tool_result>",
                        tool_call_id=tc.id,
                        name=tc.name,
                    )
                )

    return state
