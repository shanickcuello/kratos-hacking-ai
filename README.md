# Kratos — Cybersecurity AI Terminal Agent

An open-source, local-first AI agent for penetration testing and CTF challenges. Fine-tuned LLM + Kali Linux Docker + terminal UI.

```
 ╔═╗╦═╗╔═╗╔╦╗╔═╗╔═╗
 ╠╩╗╠╦╝╠═╣ ║ ║ ║╚═╗
 ╩ ╩╩╚═╩ ╩ ╩ ╚═╝╚═╝
```

No API keys. No cloud. Everything runs on your machine.

## What it does

You tell Kratos what to hack. It reasons through the attack, calls pentesting tools (nmap, sqlmap, gobuster, metasploit...) inside a Kali Docker container, analyzes the output, and plans the next step — autonomously.

```
kratos ❯ scan the target for open ports
┌─ Kratos ─────────────────────────────────────┐
│ I'll start with a comprehensive nmap scan.    │
│ Running: nmap_scan({"target": "10.10.10.50"}) │
└───────────────────────────────────────────────┘
┌─ nmap_scan ───────────────────────────────────┐
│ PORT   STATE SERVICE VERSION                  │
│ 22/tcp open  ssh     OpenSSH 8.9              │
│ 80/tcp open  http    Apache 2.4.52            │
└───────────────────────────────────────────────┘
```

## Features

- **Fine-tuned 7B model** — QLoRA-trained on real CTF writeups, produces structured tool calls
- **14 built-in tools** — nmap, gobuster, sqlmap, metasploit, hydra, linpeas, and more
- **Kali Docker sandbox** — all commands execute in an isolated container, never on your host
- **ReAct agent loop** — Reason → Act → Observe → Repeat
- **Autonomous mode** — `--auto` for full plan-and-execute without user input
- **Session save/resume** — pick up where you left off
- **Clean Architecture** — 4-layer design with ports/adapters pattern

## Quick Start

```bash
git clone https://github.com/shanickcuello/kratos-hacking-ai.git
cd kratos-hacking-ai
# Or run ./run.sh for automatic initialization
uv pip install -e ".[tui]"
docker compose -f docker/docker-compose.yml build
ollama run shanlogauthier/kratos  # https://ollama.com/shanlogauthier/kratos
uv run kratos --target 10.10.10.50
```

## Documentation

- **[Quick Start Guide](docs/QUICKSTART.md)** — Clone, install, configure, and run
- **[Training Guide](docs/TRAINING.md)** — Replicate the fine-tuning pipeline from scratch
- **[Architecture](docs/ARCHITECTURE.md)** — System design, diagrams, and project structure

## Using a Different Model

Kratos works with any Ollama model. To use an alternative (e.g. uncensored or larger):

```bash
ollama run dolphin3                     # download once
KRATOS_MODEL=dolphin3 uv run kratos --target 10.10.10.50
```

Or set it permanently in `.env`:

```bash
KRATOS_MODEL=dolphin3
```

Recommended alternatives for pentesting:
- **dolphin3** — uncensored, supports function calling, 8B (~8 GB RAM)
- **dolphin-mixtral:8x7b** — more powerful, needs ~32 GB RAM
- **nous-hermes2** — good reasoning, less censored
- **mistral:7b** — strong tool calling, lightweight

## Tech Stack

- **Model**: Qwen2.5-Coder-7B fine-tuned with QLoRA (Unsloth)
- **Inference**: Ollama (local)
- **Agent**: Python 3.11+ with ReAct loop
- **TUI**: Textual + Rich
- **Tools**: Kali Linux via Docker
- **Training**: Google Colab Pro (A100)

## License

MIT
