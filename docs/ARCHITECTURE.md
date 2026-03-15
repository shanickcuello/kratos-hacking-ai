# Kratos — Architecture

## Theory

Kratos follows **Clean Architecture** with 4 layers: Domain (pure business logic), Application (orchestration), Adapters IN (user interfaces), and Adapters OUT (infrastructure). The domain layer has zero dependencies on frameworks. The agent uses a **ReAct loop** (Reason → Act → Observe → Repeat) where the LLM produces `<tool_call>` tags that get parsed, validated, and executed inside a Kali Docker container.

## System Overview

```
┌──────────────────────────────────────────────────────┐
│                    User Terminal                      │
│         CLI (Rich) · TUI (Textual) · Auto Mode       │
└───────────────────────┬──────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│                   Agent Core                          │
│                                                       │
│   ┌─────────────┐    ┌──────────────────────┐        │
│   │  ReAct Loop │◄──►│  Tool Call Parser     │        │
│   │  (reason →  │    │  <tool_call> → JSON   │        │
│   │   act →     │    └──────────┬───────────┘        │
│   │   observe)  │               │                     │
│   └──────┬──────┘    ┌──────────▼───────────┐        │
│          │           │  Command Builder      │        │
│          │           │  nmap_scan → "nmap -sV"│       │
│          │           └──────────┬───────────┘        │
│          │                      │                     │
│          │           ┌──────────▼───────────┐        │
│          │           │  Guardrails           │        │
│          │           │  (block rm -rf, etc.) │        │
│          │           └──────────┬───────────┘        │
│          │                      │                     │
│   ┌──────▼──────┐    ┌──────────▼───────────┐        │
│   │ Ollama LLM  │    │  Docker Executor      │        │
│   │ (kratos 7B) │    │  (Kali container)     │        │
│   └─────────────┘    └──────────────────────┘        │
└──────────────────────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────┐
│              Kali Linux Container                     │
│  nmap · metasploit · sqlmap · gobuster · nikto       │
│  hydra · john · hashcat · ffuf · linpeas · ...       │
└──────────────────────────────────────────────────────┘
```

## Clean Architecture Layers

```
┌─────────────────────────────────────────────┐
│            Adapters IN (interfaces)          │
│  cli_adapter.py · tui/app.py                │
│  Receives user input, displays output       │
├─────────────────────────────────────────────┤
│            Application (use cases)           │
│  react_agent.py · planner.py · session.py   │
│  Orchestrates domain logic + ports          │
├─────────────────────────────────────────────┤
│            Domain (core business logic)      │
│  entities.py · ports.py                     │
│  Pure Python, zero dependencies             │
├─────────────────────────────────────────────┤
│            Adapters OUT (infrastructure)     │
│  ollama_adapter.py · docker_adapter.py      │
│  Implements domain ports                    │
└─────────────────────────────────────────────┘

        Dependencies flow inward only →
        Domain knows nothing about adapters
```

## Project Structure

```
kratos/
├── src/kratos/
│   ├── cli.py                  # Entry point (--target, --auto, --tui)
│   ├── config.py               # Env-based configuration
│   │
│   ├── domain/                 # Layer 1: Pure business logic
│   │   ├── entities.py         # Message, ToolCall, SessionState, etc.
│   │   └── ports.py            # LLMPort, DockerPort, UIPort (interfaces)
│   │
│   ├── application/            # Layer 2: Orchestration
│   │   ├── react_agent.py      # ReAct loop + tool call parsing
│   │   ├── planner.py          # Plan-and-Execute autonomous mode
│   │   └── session.py          # Save/resume sessions
│   │
│   ├── adapters/
│   │   ├── in_/                # Layer 3: User interfaces
│   │   │   └── cli_adapter.py  # Rich CLI (implements UIPort)
│   │   └── out/                # Layer 4: Infrastructure
│   │       ├── ollama_adapter.py   # LLM inference (implements LLMPort)
│   │       └── docker_adapter.py   # Kali container (implements DockerPort)
│   │
│   ├── tools/                  # Tool definitions + command builders
│   │   ├── recon.py            # nmap, gobuster, ffuf, dns
│   │   ├── web.py              # sqlmap, nikto, curl
│   │   ├── exploit.py          # metasploit, searchsploit
│   │   ├── privesc.py          # linpeas, sudo, suid
│   │   ├── general.py          # run_command, read/write_file
│   │   └── guardrails.py       # Command validation + blocklist
│   │
│   ├── prompts/
│   │   └── red_team.md         # System prompt (Jinja2 template)
│   │
│   └── tui/
│       └── app.py              # Textual TUI (split panels)
│
├── docker/
│   ├── Dockerfile.kali         # Kali image with all pentest tools
│   └── docker-compose.yml      # Container orchestration
│
├── kratos-model/               # Fine-tuning pipeline
│   ├── data/
│   │   ├── schema.py           # ChatML + <tool_call> format
│   │   ├── raw/                # Source writeups
│   │   └── processed/          # Training JSONL
│   ├── scripts/
│   │   ├── prepare_dataset.py  # Writeups → ChatML conversations
│   │   ├── generate_synthetic.py  # Synthetic CTF scenarios
│   │   ├── train.py            # Local training script
│   │   └── export_gguf.py      # LoRA merge + GGUF quantization
│   └── notebooks/
│       └── train_colab.ipynb   # Complete Colab training notebook
│
└── model/                      # GGUF + Modelfile for Ollama
```

## Agent Flow

```
User Input
    │
    ▼
┌─────────────┐
│ System Prompt│  (target IP, tools list, methodology, <tool_call> format)
│ + History    │
└──────┬──────┘
       │
       ▼
┌─────────────┐     no tool calls     ┌──────────────┐
│  LLM Chat   │ ───────────────────► │ Display reply │
│  (Ollama)   │                       └──────────────┘
└──────┬──────┘
       │ <tool_call> detected
       ▼
┌─────────────┐
│ Parse JSON  │  {"name": "nmap_scan", "arguments": {...}}
└──────┬──────┘
       │
       ▼
┌─────────────┐     blocked      ┌──────────────┐
│ Guardrails  │ ───────────────► │ Return error │
│ Check       │                   └──────────────┘
└──────┬──────┘
       │ allowed
       ▼
┌─────────────┐
│ Build shell │  nmap_scan → "nmap -sV -sC 10.10.10.50"
│ command     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Docker exec │  Execute in Kali container
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Wrap output │  <tool_result>...</tool_result>
│ → LLM again │  (loop back to LLM for analysis)
└─────────────┘
```

## Tool System

Each tool has 3 parts:

1. **Definition** (`tools/*.py`) — name, description, JSON schema for the LLM
2. **Command Builder** (`react_agent.py`) — converts tool args to a shell command
3. **Guardrail** (`guardrails.py`) — validates the command before execution

```
Model output:  <tool_call>{"name": "nmap_scan", "arguments": {"target": "10.10.10.50"}}</tool_call>
                   │
Parser:            │  → ToolCall(name="nmap_scan", arguments={"target": "10.10.10.50"})
                   │
Builder:           │  → "nmap -sV -sC 10.10.10.50"
                   │
Guardrail:         │  → allowed=True, timeout=300
                   │
Docker:            │  → container.exec_run(["bash", "-c", "nmap -sV -sC 10.10.10.50"])
                   │
Output:            │  → "PORT  STATE SERVICE\n22/tcp open ssh\n80/tcp open http"
```

## Key Design Decisions

- **Text-based tool calling** — The fine-tuned model outputs `<tool_call>` tags in plain text rather than using Ollama's native function calling. This is more robust across different model providers and formats.
- **Docker isolation** — All commands execute inside a Kali container, never on the host. Guardrails add an extra safety layer.
- **Ports pattern** — `LLMPort`, `DockerPort`, `UIPort` are abstract interfaces in the domain layer. Adapters implement them. This makes it easy to swap Ollama for another provider or Docker for SSH.
- **Session persistence** — Every conversation is auto-saved as JSON, enabling resume and post-analysis.
