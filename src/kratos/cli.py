"""Kratos CLI entry point."""

from __future__ import annotations

import argparse
import asyncio
import sys

from rich.console import Console

console = Console()

BANNER = r"""
[bold red]
 ╔═╗╦═╗╔═╗╔╦╗╔═╗╔═╗
 ╠╩╗╠╦╝╠═╣ ║ ║ ║╚═╗
 ╩ ╩╩╚═╩ ╩ ╩ ╚═╝╚═╝
[/bold red]
[dim]Cybersecurity AI Agent · v0.1.0[/dim]
[dim]Type /help for commands, /quit to exit[/dim]
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Kratos — Cybersecurity AI Terminal Agent",
    )
    parser.add_argument("-t", "--target", help="Target IP or hostname")
    parser.add_argument("-m", "--mission", help="Mission description")
    parser.add_argument(
        "--tui", action="store_true",
        help="Launch full Textual TUI instead of basic CLI",
    )
    parser.add_argument(
        "--auto", action="store_true",
        help="Autonomous mode — plan and execute without user input",
    )
    parser.add_argument(
        "--resume", metavar="SESSION",
        help="Resume a saved session (path or 'latest')",
    )
    return parser.parse_args()


async def _run_cli(args: argparse.Namespace) -> None:
    """Run in basic Rich CLI mode."""
    from kratos.adapters.in_.cli_adapter import CliAdapter
    from kratos.adapters.out.docker_adapter import DockerAdapter
    from kratos.adapters.out.ollama_adapter import OllamaAdapter
    from kratos.application.react_agent import run_react_loop
    from kratos.application.session import save_session

    console.print(BANNER)

    llm = OllamaAdapter()
    docker = DockerAdapter()
    ui = CliAdapter()

    try:
        await docker.ensure_running()
    except Exception as e:
        console.print(
            f"[yellow]Warning: Docker not available ({e}). "
            "Tool execution will fail.[/yellow]"
        )

    if args.target:
        console.print(f"[bold]Target:[/bold] {args.target}")

    state = await run_react_loop(
        llm=llm, docker=docker, ui=ui,
        target_ip=args.target, mission=args.mission,
    )

    # Auto-save session
    path = save_session(state, label=args.target or "session")
    console.print(f"[dim]Session saved: {path}[/dim]")

    try:
        await docker.stop()
    except Exception:
        pass


async def _run_auto(args: argparse.Namespace) -> None:
    """Run in autonomous plan-and-execute mode."""
    from kratos.adapters.in_.cli_adapter import CliAdapter
    from kratos.adapters.out.docker_adapter import DockerAdapter
    from kratos.adapters.out.ollama_adapter import OllamaAdapter
    from kratos.application.planner import run_plan_and_execute
    from kratos.application.session import save_session

    console.print(BANNER)

    if not args.target:
        console.print("[red]Error: --target is required for --auto mode[/red]")
        sys.exit(1)

    llm = OllamaAdapter()
    docker = DockerAdapter()
    ui = CliAdapter()

    try:
        await docker.ensure_running()
    except Exception as e:
        console.print(f"[red]Docker required for auto mode: {e}[/red]")
        sys.exit(1)

    console.print(f"[bold]Target:[/bold] {args.target}")
    console.print("[bold yellow]Mode: Autonomous Plan-and-Execute[/bold yellow]")

    mission = args.mission or "Full penetration test — find all flags"
    state = await run_plan_and_execute(
        llm=llm, docker=docker, ui=ui,
        target_ip=args.target, mission=mission,
    )

    path = save_session(state, label=f"auto_{args.target}")
    console.print(f"[dim]Session saved: {path}[/dim]")

    try:
        await docker.stop()
    except Exception:
        pass


async def _run_tui(args: argparse.Namespace) -> None:
    """Run in full Textual TUI mode."""
    from kratos.adapters.out.docker_adapter import DockerAdapter
    from kratos.adapters.out.ollama_adapter import OllamaAdapter
    from kratos.application.react_agent import run_react_loop
    from kratos.tui.app import KratosApp, TuiAdapter

    app = KratosApp()
    ui = TuiAdapter(app)
    llm = OllamaAdapter()
    docker = DockerAdapter()

    async def _agent_loop() -> None:
        try:
            await docker.ensure_running()
        except Exception:
            pass
        await run_react_loop(
            llm=llm, docker=docker, ui=ui,
            target_ip=args.target, mission=args.mission,
        )

    # Run TUI and agent concurrently
    async with app.run_async():
        await _agent_loop()


def main() -> None:
    """CLI entry point."""
    args = _parse_args()
    try:
        if args.tui:
            asyncio.run(_run_tui(args))
        elif args.auto:
            asyncio.run(_run_auto(args))
        else:
            asyncio.run(_run_cli(args))
    except KeyboardInterrupt:
        console.print("\n[dim]Goodbye.[/dim]")


if __name__ == "__main__":
    main()
