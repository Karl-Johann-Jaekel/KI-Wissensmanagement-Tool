"""LLM provider abstraction (ADR-03): Mistral La Plateforme or a local Ollama."""

import logging
import time
from collections.abc import Callable
from functools import lru_cache
from typing import Protocol, TypedDict

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

RETRY_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}


class ChatMessage(TypedDict):
    role: str  # system | user | assistant
    content: str


class LLMError(RuntimeError):
    """Generation failed after retries; message is safe to show to users."""


class LLMProvider(Protocol):
    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str: ...


class _RetryingHttpProvider:
    max_attempts = 4

    def __init__(
        self,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self._sleep = sleep

    def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        last_error = "unknown error"
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self._client.post(path, json=payload)
            except httpx.TransportError as exc:
                last_error = f"{type(exc).__name__}"
                delay = float(2 ** (attempt - 1))
            else:
                if response.status_code < 400:
                    data: dict[str, object] = response.json()
                    return data
                last_error = f"HTTP {response.status_code}"
                if response.headers.get("x-ratelimit-limit-req-minute") == "0":
                    # Mistral workspace without an active plan: retrying cannot help
                    raise LLMError(
                        "Das LLM-Kontingent ist 0 Anfragen/Minute – "
                        "API-Plan beim Anbieter aktivieren."
                    )
                if response.status_code not in RETRY_STATUS:
                    log.error(
                        "LLM request rejected: %s %s", response.status_code, response.text[:300]
                    )
                    raise LLMError(f"Das Sprachmodell hat die Anfrage abgelehnt ({last_error}).")
                delay = _retry_after(response) or float(2 ** (attempt - 1))
            if attempt < self.max_attempts:
                delay = min(delay, 20.0)
                log.warning("LLM call failed (%s), retry %d in %.1fs", last_error, attempt, delay)
                self._sleep(delay)
        raise LLMError(
            f"Das Sprachmodell ist gerade nicht erreichbar ({last_error}). "
            "Bitte gleich erneut versuchen."
        )


class MistralProvider(_RetryingHttpProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "https://api.mistral.ai/v1",
        temperature: float = 0.2,
        timeout: float = 90.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not api_key:
            raise LLMError("MISTRAL_API_KEY ist nicht gesetzt.")
        client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )
        super().__init__(client, sleep)
        self._model = model
        self._temperature = temperature

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "temperature": self._temperature,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        data = self._post("/chat/completions", payload)
        try:
            content = data["choices"][0]["message"]["content"]  # type: ignore[index]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Unerwartete Antwort des Sprachmodells.") from exc
        return str(content)


class OllamaProvider(_RetryingHttpProvider):
    def __init__(
        self,
        base_url: str,
        model: str,
        temperature: float = 0.2,
        timeout: float = 180.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(
            httpx.Client(base_url=base_url, timeout=timeout, transport=transport), sleep
        )
        self._model = model
        self._temperature = temperature

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        options: dict[str, object] = {"temperature": self._temperature}
        if max_tokens:
            options["num_predict"] = max_tokens
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": options,
        }
        if json_mode:
            payload["format"] = "json"
        data = self._post("/api/chat", payload)
        try:
            return str(data["message"]["content"])  # type: ignore[index]
        except (KeyError, TypeError) as exc:
            raise LLMError("Unerwartete Antwort des Sprachmodells.") from exc


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    try:
        return float(value) if value else None
    except ValueError:
        return None


@lru_cache
def get_llm() -> LLMProvider:
    settings = get_settings()
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            settings.ollama_base_url, settings.ollama_model, settings.llm_temperature
        )
    return MistralProvider(
        api_key=settings.mistral_api_key,
        model=settings.mistral_model,
        base_url=settings.mistral_base_url,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
    )
