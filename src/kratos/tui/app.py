"""Textual-based TUI for Kratos agent."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.css.query import NoMatches
from textual.widgets import Footer, Header, Input, RichLog, Static

from kratos.domain.ports import UIPort

CSS = """
#chat-panel {
    width: 1fr;
    border: solid $primary;
    overflow-y: auto;
}
#terminal-panel {
    width: 1fr;
    border: solid $success;
    overflow-y: auto;
}
#status-bar {
    height: 1;
    dock: bottom;
    background: $surface;
    color: $text-muted;
    padding: 0 1;
}
#prompt {
    dock: bottom;
    margin: 0 0;
}
"""


class KratosApp(App):
    """Kratos TUI with split chat + terminal panels."""

    TITLE = "Kratos"
    SUB_TITLE = "Cybersecurity AI Agent"
    CSS = CSS

    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+l", "clear", "Clear"),
    ]

    def __init__(self, on_input: Callable | None = None, **kwargs):
        super().__init__(**kwargs)
        self._on_input = on_input
        self._input_queue: asyncio.Queue[str] = asyncio.Queue()

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            yield RichLog(id="chat-panel", markup=True, wrap=True)
            yield RichLog(id="terminal-panel", markup=True, wrap=True)
        yield Static("Kratos ready", id="status-bar")
        yield Input(placeholder="Type a command or message...", id="prompt")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#chat-panel", RichLog).write(
            "[bold red]"
            " ╔═╗╦═╗╔═╗╔╦╗╔═╗╔═╗\n"
            " ╠╩╗╠╦╝╠═╣ ║ ║ ║╚═╗\n"
            " ╩ ╩╩╚═╩ ╩ ╩ ╚═╝╚═╝[/]\n"
            "[dim]Cybersecurity AI Agent · v0.1.0[/]"
        )

    @on(Input.Submitted, "#prompt")
    async def handle_input(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if not text:
            return
        event.input.clear()
        self.query_one("#chat-panel", RichLog).write(
            f"[bold yellow]you ❯[/] {text}"
        )
        await self._input_queue.put(text)

    def action_clear(self) -> None:
        try:
            self.query_one("#chat-panel", RichLog).clear()
            self.query_one("#terminal-panel", RichLog).clear()
        except NoMatches:
            pass

    # --- Public API for UIPort ---

    def write_chat(self, text: str) -> None:
        try:
            self.query_one("#chat-panel", RichLog).write(text)
        except NoMatches:
            pass

    def write_terminal(self, text: str) -> None:
        try:
            self.query_one("#terminal-panel", RichLog).write(text)
        except NoMatches:
            pass

    def set_status(self, text: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(text)
        except NoMatches:
            pass

    async def wait_for_input(self) -> str:
        return await self._input_queue.get()


class TuiAdapter(UIPort):
    """Textual TUI adapter implementing UIPort."""

    def __init__(self, app: KratosApp):
        self._app = app

    async def display_assistant(self, text: str) -> None:
        if text:
            self._app.write_chat(f"[bold red]kratos ❯[/] {text}")

    async def display_tool_output(
        self, tool_name: str, output: str
    ) -> None:
        display = output[:5000] if len(output) > 5000 else output
        self._app.write_terminal(
            f"[bold cyan]── {tool_name} ──[/]\n{display}"
        )

    async def display_status(self, status: str) -> None:
        self._app.set_status(status)

    async def get_user_input(self) -> str:
        return await self._app.wait_for_input()
    async def stream_token(self, token: str) -> None:
        self._app.write_chat(token)

    async def start_thinking(self, message: str = "Thinking") -> None:
        self._app.set_status(f"[cyan]⏳ {message}...[/]")

    async def stop_thinking(self) -> None:
        self._app.set_status("Ready")
