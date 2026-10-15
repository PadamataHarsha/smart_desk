"""Compatibility exports for the canonical SmartDesk Ollama service."""

from smart_desk.services.ollama_service import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    OllamaConnectionError,
    OllamaError,
    OllamaModelError,
    OllamaService,
    OllamaStatus,
)

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "OllamaConnectionError",
    "OllamaError",
    "OllamaModelError",
    "OllamaService",
    "OllamaStatus",
]
