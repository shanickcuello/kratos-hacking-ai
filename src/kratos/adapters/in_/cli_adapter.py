"""Rich-based CLI adapter for user interaction."""

from __future__ import annotations

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text

from kratos.domain.ports import UIPort

console = Console()


class CliAdapter(UIPort):
    """Rich CLI for terminal interaction."""

    def __init__(self):
        self._prompt = PromptSession()

    async def display_assistant(self, text: str) -> None:
        """Display assistant message with markdown rendering."""
        if not text:
            return
        md = Markdown(text)
        console.print(
            Panel(md, title="[bold red]Kratos[/]", border_style="red")
        )

    async def display_tool_output(
        self, tool_name: str, output: str
    ) -> None:
        """Display tool output in a styled panel."""
        # Limit display length
        display = output[:5000] if len(output) > 5000 else output
        console.print(
            Panel(
                Text(display, style="green"),
                title=f"[bold cyan]{tool_name}[/]",
                border_style="cyan",
            )
        )

    async def display_status(self, status: str) -> None:
        """Display a status message."""
        console.print(f"[dim]{status}[/dim]")

    async def get_user_input(self) -> str:
        """Get input from the user with styled prompt."""
        try:
            return await self._prompt.prompt_async(
                HTML("<b><style fg='#ff6600'>kratos</style></b> <style fg='#888'>❯</style> ")
            )
        except (EOFError, KeyboardInterrupt):
            return "/quit"

    async def stream_token(self, token: str) -> None:
        """Print a single token without newline."""
        console.print(token, end="")
