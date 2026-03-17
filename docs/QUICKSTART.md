# Kratos — Quick Start

## Theory

Kratos is a local-first cybersecurity AI agent that runs a fine-tuned LLM connected to a Kali Linux Docker container. You chat with it, it reasons about the target, calls pentesting tools (nmap, sqlmap, gobuster, etc.) autonomously, and reports findings — all from your terminal.

No API keys. No cloud. Everything runs on your machine.

## Prerequisites

- **Python 3.11+**
- **Docker Desktop** running
- **Ollama** installed ([ollama.com](https://ollama.com))
- **uv** package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- ~12 GB free disk (5.4 GB model + 6 GB Docker image)

## Steps

### 1. Clone and install

```bash
git clone https://github.com/shanickcuello/kratos-hacking-ai.git
cd kratos-hacking-ai
uv pip install -e ".[tui]"
```

### 2. Build the Kali Docker image

```bash
docker compose -f docker/docker-compose.yml build
```

This installs nmap, metasploit, sqlmap, gobuster, hydra, john, and 20+ more tools. Takes ~5 min.

### 3. Download the model

```bash
# Option A: Download the pre-trained model from Ollama
# https://ollama.com/shanlogauthier/kratos
ollama run shanlogauthier/kratos

# Option B: Import the fine-tuned GGUF (if you have it)
cd model/
ollama create kratos -f Modelfile

# Option C: Use the base model (no fine-tuning)
ollama pull qwen2.5-coder:7b
```

### 4. Configure

```bash
cp .env.example .env
# Edit .env:
#   KRATOS_MODEL=kratos          (fine-tuned)
#   KRATOS_MODEL=qwen2.5-coder:7b  (base model)
```

### 5. Run

```bash
# Interactive CLI
uv run kratos --target 10.10.10.50

# Autonomous mode (plan-and-execute)
uv run kratos --auto --target 10.10.10.50 --mission "find all flags"

# Full TUI (split panels)
uv run kratos --tui --target 10.10.10.50
```

### 6. Use

Type natural language commands at the `kratos ❯` prompt:

```
kratos ❯ scan the target for open ports
kratos ❯ enumerate the web server on port 80
kratos ❯ check for SQL injection on the login form
kratos ❯ find privilege escalation vectors
kratos ❯ /quit
```

Sessions are auto-saved to `~/.kratos/sessions/` and can be resumed with `--resume latest`.
