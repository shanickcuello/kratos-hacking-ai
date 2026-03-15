"""Session persistence — save and resume attack sessions."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from kratos.domain.entities import (
    AttackPhase,
    Flag,
    Message,
    MessageRole,
    SessionState,
    Target,
    ToolCall,
)

logger = logging.getLogger(__name__)

SESSIONS_DIR = Path.home() / ".kratos" / "sessions"


def _ensure_dir() -> None:
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _msg_to_dict(msg: Message) -> dict:
    d: dict = {"role": msg.role.value, "content": msg.content or ""}
    if msg.tool_calls:
        d["tool_calls"] = [
            {"id": tc.id, "name": tc.name, "arguments": tc.arguments}
            for tc in msg.tool_calls
        ]
    if msg.tool_call_id:
        d["tool_call_id"] = msg.tool_call_id
    if msg.name:
        d["name"] = msg.name
    return d


def _msg_from_dict(d: dict) -> Message:
    tool_calls = None
    if "tool_calls" in d:
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
            for tc in d["tool_calls"]
        ]
    return Message(
        role=MessageRole(d["role"]),
        content=d.get("content", ""),
        tool_calls=tool_calls,
        tool_call_id=d.get("tool_call_id"),
        name=d.get("name"),
    )


def save_session(
    state: SessionState,
    label: str = "",
) -> Path:
    """Save session state to a JSON file. Returns the file path."""
    _ensure_dir()
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    name = f"{label}_{ts}" if label else ts
    path = SESSIONS_DIR / f"{name}.json"

    data = {
        "saved_at": ts,
        "turn_count": state.turn_count,
        "phase": state.phase.value,
        "messages": [_msg_to_dict(m) for m in state.messages],
        "flags": [
            {"value": f.value, "type": f.flag_type, "source": f.source}
            for f in state.flags
        ],
        "credentials": state.credentials,
        "notes": state.notes,
    }
    if state.target:
        data["target"] = {
            "ip": state.target.ip,
            "hostname": state.target.hostname,
            "ports": state.target.ports,
            "services": {str(k): v for k, v in state.target.services.items()},
            "os_info": state.target.os_info,
        }

    path.write_text(json.dumps(data, indent=2))
    logger.info("Session saved to %s", path)
    return path


def load_session(path: str | Path) -> SessionState:
    """Load a session state from a JSON file."""
    p = Path(path)
    data = json.loads(p.read_text())

    state = SessionState(
        turn_count=data.get("turn_count", 0),
        phase=AttackPhase(data.get("phase", "recon")),
        messages=[_msg_from_dict(m) for m in data.get("messages", [])],
        flags=[
            Flag(value=f["value"], flag_type=f.get("type", ""), source=f.get("source", ""))
            for f in data.get("flags", [])
        ],
        credentials=data.get("credentials", {}),
        notes=data.get("notes", []),
    )

    if "target" in data:
        t = data["target"]
        state.target = Target(
            ip=t["ip"],
            hostname=t.get("hostname"),
            ports=t.get("ports", []),
            services={int(k): v for k, v in t.get("services", {}).items()},
            os_info=t.get("os_info"),
        )

    return state


def list_sessions() -> list[Path]:
    """List saved session files, newest first."""
    _ensure_dir()
    return sorted(SESSIONS_DIR.glob("*.json"), reverse=True)
