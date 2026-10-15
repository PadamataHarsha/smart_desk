"""HTTP client for the local Ollama server."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import requests


DEFAULT_BASE_URL = "http://localhost:11434"
DEFAULT_MODEL = "llama3.2"
CONNECT_TIMEOUT_SECONDS = 3
GENERATION_TIMEOUT_SECONDS = 300
RETRY_DELAY_SECONDS = 1


class OllamaError(RuntimeError):
    """Base exception for Ollama service failures."""


class OllamaConnectionError(OllamaError):
    """Raised when the Ollama server cannot be reached."""


class OllamaModelError(OllamaError):
    """Raised when the configured model is not installed or usable."""


@dataclass(frozen=True)
class OllamaStatus:
    """Connection and model availability reported by Ollama."""

    connected: bool
    model_available: bool
    message: str

    @property
    def ready(self) -> bool:
        """Return whether requests can be generated with the configured model."""
        return self.connected and self.model_available


class OllamaService:
    """Query a local Ollama server with bounded retries and timeouts."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = GENERATION_TIMEOUT_SECONDS,
        retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.retries = max(0, retries)

    def check_status(self) -> OllamaStatus:
        """Check that the server is reachable and the configured model exists."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=CONNECT_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload: Any = response.json()
            if not isinstance(payload, dict):
                return OllamaStatus(False, False, "Ollama returned an invalid status response.")
            models = payload.get("models", [])
            if not isinstance(models, list):
                return OllamaStatus(False, False, "Ollama returned an invalid model list.")
            available_names = {
                str(item.get("name", item.get("model", "")))
                for item in models
                if isinstance(item, dict)
            }
        except (requests.RequestException, ValueError, TypeError) as exc:
            return OllamaStatus(False, False, f"Ollama is offline: {exc}")

        available = any(
            name == self.model or name.startswith(f"{self.model}:")
            for name in available_names
        )
        if not available:
            return OllamaStatus(
                True,
                False,
                f"Ollama is running, but model '{self.model}' is not installed.",
            )
        return OllamaStatus(True, True, "Connected")

    def generate(self, prompt: str) -> str:
        """Generate a response, retrying transient network and server failures."""
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                response = requests.post(
                    f"{self.base_url}/api/generate",
                    json={"model": self.model, "prompt": prompt, "stream": False},
                    timeout=self.timeout,
                )
                if response.status_code == 404:
                    raise OllamaModelError(
                        f"Model '{self.model}' was not found. Run 'ollama pull {self.model}' and try again."
                    )
                response.raise_for_status()
                payload: Any = response.json()
                if not isinstance(payload, dict):
                    raise OllamaError("Ollama returned an invalid response.")
                answer = payload.get("response")
                if not isinstance(answer, str) or not answer.strip():
                    raise OllamaError("Ollama returned an empty response.")
                return answer.strip()
            except OllamaModelError:
                raise
            except OllamaError:
                raise
            except requests.HTTPError as exc:
                last_error = exc
                if exc.response is None or exc.response.status_code < 500:
                    break
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = exc
            except (requests.RequestException, ValueError, TypeError) as exc:
                raise OllamaError(f"Ollama request failed: {exc}") from exc

            if attempt < self.retries:
                time.sleep(RETRY_DELAY_SECONDS * (attempt + 1))

        if isinstance(last_error, (requests.ConnectionError, requests.Timeout)):
            raise OllamaConnectionError(
                "Could not reach Ollama. Make sure Ollama is running and try again."
            ) from last_error
        raise OllamaError(f"Ollama could not complete the request: {last_error}") from last_error


__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_MODEL",
    "OllamaConnectionError",
    "OllamaError",
    "OllamaModelError",
    "OllamaService",
    "OllamaStatus",
]
