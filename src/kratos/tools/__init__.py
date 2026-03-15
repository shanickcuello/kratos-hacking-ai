"""Tool registry — aggregates all tool categories."""

from __future__ import annotations

from kratos.domain.entities import ToolDefinition
from kratos.tools.exploit import get_exploit_tools
from kratos.tools.general import get_general_tools
from kratos.tools.privesc import get_privesc_tools
from kratos.tools.recon import get_recon_tools
from kratos.tools.web import get_web_tools


def get_all_tools() -> list[ToolDefinition]:
    """Return every registered tool definition."""
    return (
        get_general_tools()
        + get_recon_tools()
        + get_web_tools()
        + get_exploit_tools()
        + get_privesc_tools()
    )