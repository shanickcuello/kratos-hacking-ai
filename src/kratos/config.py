"""Kratos configuration loaded from environment variables."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration from environment."""

    model: str = os.getenv("KRATOS_MODEL", "qwen2.5-coder:7b")
    ollama_host: str = os.getenv("KRATOS_OLLAMA_HOST", "http://localhost:11434")
    docker_image: str = os.getenv("KRATOS_DOCKER_IMAGE", "kratos-kali")
    max_turns: int = int(os.getenv("KRATOS_MAX_TURNS", "50"))
    debug: bool = os.getenv("KRATOS_DEBUG", "false").lower() == "true"
    docker_network: str = os.getenv("KRATOS_DOCKER_NETWORK", "kratos-net")
    command_timeout: int = int(os.getenv("KRATOS_CMD_TIMEOUT", "120"))


config = Config()
