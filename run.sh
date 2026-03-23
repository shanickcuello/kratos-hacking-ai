#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODEL_DIR="$ROOT_DIR/model"
MODEL_NAME="kratos"
GGUF_FILE="qwen2.5-coder-7b-instruct.Q5_K_M.gguf"
CHOOSE_MODEL=false

info()  { printf "\033[1;34m[INFO]\033[0m  %s\n" "$1"; }
ok()    { printf "\033[1;32m[OK]\033[0m    %s\n" "$1"; }
warn()  { printf "\033[1;33m[WARN]\033[0m  %s\n" "$1"; }
error() { printf "\033[1;31m[ERROR]\033[0m %s\n" "$1"; exit 1; }

usage() {
    cat <<EOF
Usage: ./run.sh [model] [--model <name>] [--choose-model]

Options:
  --model, -m <name>  Model name to use (default: kratos)
  --choose-model      Pick a model interactively from ollama list
  --help, -h          Show this help

Examples:
  ./run.sh
  ./run.sh dolphin3
  ./run.sh --model dolphin3
  ./run.sh --choose-model
EOF
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            -m|--model)
                [ $# -ge 2 ] || error "Missing value for $1"
                MODEL_NAME="$2"
                shift 2
                ;;
            --choose-model)
                CHOOSE_MODEL=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                MODEL_NAME="$1"
                shift
                ;;
        esac
    done
}

refresh_models() {
    INSTALLED_MODELS=()
    while IFS= read -r line; do
        [ -n "$line" ] && INSTALLED_MODELS+=("$line")
    done < <(ollama list 2>/dev/null | awk 'NR>1 {print $1}')
}

is_model_installed() {
    local target="$1"
    local model=""
    for model in "${INSTALLED_MODELS[@]}"; do
        if [ "$model" = "$target" ]; then
            return 0
        fi
    done
    return 1
}

choose_model() {
    refresh_models
    if [ ${#INSTALLED_MODELS[@]} -eq 0 ]; then
        warn "No installed models found in ollama list."
        return
    fi

    info "Available models:"
    local idx=1
    local model=""
    for model in "${INSTALLED_MODELS[@]}"; do
        printf "  %d) %s\n" "$idx" "$model"
        idx=$((idx + 1))
    done
    printf "  0) Keep current (%s)\n" "$MODEL_NAME"
    printf "\n"
    read -r -p "Choose a model number: " choice

    if [ -z "$choice" ] || [ "$choice" = "0" ]; then
        return
    fi
    case "$choice" in
        ''|*[!0-9]*) warn "Invalid choice. Keeping $MODEL_NAME."; return ;;
    esac
    if [ "$choice" -ge 1 ] && [ "$choice" -le ${#INSTALLED_MODELS[@]} ]; then
        MODEL_NAME="${INSTALLED_MODELS[$((choice - 1))]}"
        ok "Selected model: $MODEL_NAME"
    else
        warn "Choice out of range. Keeping $MODEL_NAME."
    fi
}

ensure_model() {
    refresh_models
    if is_model_installed "$MODEL_NAME"; then
        ok "Ollama model '$MODEL_NAME' already exists"
        return
    fi

    if [ "$MODEL_NAME" = "kratos" ] && [ -f "$MODEL_DIR/$GGUF_FILE" ] && [ -f "$MODEL_DIR/Modelfile" ]; then
        info "Creating ollama model 'kratos' from Modelfile..."
        ollama create kratos -f "$MODEL_DIR/Modelfile"
        ok "Ollama model 'kratos' created"
        return
    fi

    if [ -t 0 ]; then
        read -r -p "Model '$MODEL_NAME' is missing. Pull it now with Ollama? [Y/n]: " answer
        if [ -z "$answer" ] || [ "$answer" = "y" ] || [ "$answer" = "Y" ]; then
            info "Pulling model '$MODEL_NAME'..."
            ollama pull "$MODEL_NAME"
            ok "Model '$MODEL_NAME' pulled"
        else
            warn "Model '$MODEL_NAME' not installed. Kratos may fail until you install it."
        fi
    else
        warn "Model '$MODEL_NAME' not installed. Run: ollama pull $MODEL_NAME"
    fi
}

parse_args "$@"

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
if [ "$CHOOSE_MODEL" = true ] && [ -t 0 ]; then
    choose_model
    ok "Ollama model '$MODEL_NAME' created"
fi
ensure_model

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
if [ "$MODEL_NAME" = "kratos" ]; then
    printf "\033[1;36mRun: \033[0m uv run kratos --target <IP>\n"
else
    printf "\033[1;36mRun: \033[0m KRATOS_MODEL=%s uv run kratos --target <IP>\n" "$MODEL_NAME"
fi
if [ -t 0 ]; then
    printf "\033[33mNote: Add export PATH=\"\$HOME/.local/bin:\$PATH\" to ~/.zshrc for direct 'kratos' command.\033[0m\n"
fi
