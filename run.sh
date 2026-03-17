#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="$ROOT_DIR/model"
MODEL_NAME="kratos"
GGUF_FILE="qwen2.5-coder-7b-instruct.Q5_K_M.gguf"

info()  { printf "\033[1;34m[INFO]\033[0m  %s\n" "$1"; }
ok()    { printf "\033[1;32m[OK]\033[0m    %s\n" "$1"; }
warn()  { printf "\033[1;33m[WARN]\033[0m  %s\n" "$1"; }
error() { printf "\033[1;31m[ERROR]\033[0m %s\n" "$1"; exit 1; }

# ── uv ───────────────────────────────────────────────
if command -v uv &>/dev/null; then
    ok "uv already installed ($(uv --version))"
else
    info "Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ok "uv installed"
fi

# Add uv binaries to PATH (for shell scripts)
export PATH="$HOME/.local/bin:$PATH"

# ── Ollama ───────────────────────────────────────────
if command -v ollama &>/dev/null; then
    ok "ollama already installed ($(ollama --version))"
else
    info "Installing ollama..."
    curl -fsSL https://ollama.com/install.sh | sh
    ok "ollama installed"
fi

# ── Docker ───────────────────────────────────────────
if command -v docker &>/dev/null; then
    ok "docker found"
else
    error "Docker is not installed. Please install Docker Desktop: https://www.docker.com/products/docker-desktop"
fi

if docker info &>/dev/null; then
    ok "Docker daemon running"
else
    error "Docker daemon is not running. Please start Docker Desktop."
fi

# ── Python deps ──────────────────────────────────────
info "Installing Python dependencies..."
uv pip install -e "$ROOT_DIR[dev,tui]"
ok "Python dependencies installed"

# ── Ollama model ─────────────────────────────────────
if ! pgrep -x ollama &>/dev/null; then
    info "Starting ollama serve..."
    ollama serve &>/dev/null &
    sleep 2
fi

if ollama list 2>/dev/null | grep -q "$MODEL_NAME"; then
    ok "Ollama model '$MODEL_NAME' already exists"
else
    if [ ! -f "$MODEL_DIR/$GGUF_FILE" ]; then
        error "GGUF file not found at $MODEL_DIR/$GGUF_FILE — download it first."
    fi
    info "Creating ollama model '$MODEL_NAME' from Modelfile..."
    ollama create "$MODEL_NAME" -f "$MODEL_DIR/Modelfile"
    ok "Ollama model '$MODEL_NAME' created"
fi

# ── Kali Docker image ────────────────────────────────
if docker images --format '{{.Repository}}' | grep -q "^kratos-kali$"; then
    ok "Docker image 'kratos-kali' already built"
else
    info "Building Kali Docker image (this may take a while)..."
    docker compose -f "$ROOT_DIR/docker/docker-compose.yml" build
    ok "Docker image 'kratos-kali' built"
fi

# ── Done ─────────────────────────────────────────────
printf "\n\033[1;32m✔ All ready.\033[0m\n"
printf "\033[1;36mRun: \033[0m uv run kratos --target <IP>\n"
if [ -t 0 ]; then
    printf "\033[33mNote: Add export PATH=\"\$HOME/.local/bin:\$PATH\" to ~/.zshrc for direct 'kratos' command.\033[0m\n"
fi
