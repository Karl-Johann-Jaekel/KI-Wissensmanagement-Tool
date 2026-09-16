"""LLM provider abstraction (ADR-03): Mistral La Plateforme or a local Ollama."""

import json
import logging
import time
from collections.abc import Callable, Iterator
from functools import lru_cache
from typing import Protocol, TypedDict

import httpx

from app.config import Settings, get_settings

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

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        """Yield the answer in pieces as the model produces them."""
        ...


class _RetryingHttpProvider:
    def __init__(
        self,
        client: httpx.Client,
        sleep: Callable[[float], None] = time.sleep,
        max_attempts: int = 4,
        max_delay: float = 20.0,
    ) -> None:
        self._client = client
        self._sleep = sleep
        self.max_attempts = max_attempts
        self._max_delay = max_delay

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
                delay = min(delay, self._max_delay)
                log.warning("LLM call failed (%s), retry %d in %.1fs", last_error, attempt, delay)
                self._sleep(delay)
        raise LLMError(
            f"Das Sprachmodell ist gerade nicht erreichbar ({last_error}). "
            "Bitte gleich erneut versuchen."
        )

    def _stream_post(
        self,
        path: str,
        payload: dict[str, object],
        parse: Callable[[str], str | None],
    ) -> Iterator[str]:
        """Same retry rules as `_post`, but only until the first piece of text.

        Once a piece has been handed to the caller it is already on the user's screen; a retry
        would restart the answer and duplicate what is shown. From then on, failures surface.
        """
        last_error = "unknown error"
        for attempt in range(1, self.max_attempts + 1):
            emitted = False
            try:
                with self._client.stream("POST", path, json=payload) as response:
                    if response.status_code < 400:
                        for line in response.iter_lines():
                            piece = parse(line)
                            if piece:
                                emitted = True
                                yield piece
                        return
                    response.read()
                    last_error = f"HTTP {response.status_code}"
                    if response.headers.get("x-ratelimit-limit-req-minute") == "0":
                        raise LLMError(
                            "Das LLM-Kontingent ist 0 Anfragen/Minute – "
                            "API-Plan beim Anbieter aktivieren."
                        )
                    if response.status_code not in RETRY_STATUS:
                        log.error(
                            "LLM stream rejected: %s %s", response.status_code, response.text[:300]
                        )
                        raise LLMError(
                            f"Das Sprachmodell hat die Anfrage abgelehnt ({last_error})."
                        )
                    delay = _retry_after(response) or float(2 ** (attempt - 1))
            except httpx.TransportError as exc:
                if emitted:
                    raise LLMError(
                        "Die Verbindung zum Sprachmodell ist mitten in der Antwort abgerissen."
                    ) from exc
                last_error = type(exc).__name__
                delay = float(2 ** (attempt - 1))
            if attempt < self.max_attempts:
                delay = min(delay, self._max_delay)
                log.warning("LLM stream failed (%s), retry %d in %.1fs", last_error, attempt, delay)
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
        max_attempts: int = 4,
        max_delay: float = 20.0,
    ) -> None:
        self._has_key = bool(api_key)
        client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={"Authorization": f"Bearer {api_key}"},
            transport=transport,
        )
        super().__init__(client, sleep, max_attempts, max_delay)
        self.model = model
        self._temperature = temperature

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        if not self._has_key:
            # checked per call, so ingestion without a key still stores chunks
            raise LLMError("MISTRAL_API_KEY ist nicht gesetzt.")
        payload: dict[str, object] = {
            "model": self.model,
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

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        if not self._has_key:
            raise LLMError("MISTRAL_API_KEY ist nicht gesetzt.")
        payload: dict[str, object] = {
            "model": self.model,
            "messages": messages,
            "temperature": self._temperature,
            "stream": True,
        }
        yield from self._stream_post("/chat/completions", payload, _parse_sse_delta)


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

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": self._temperature},
        }
        yield from self._stream_post("/api/chat", payload, _parse_ndjson_delta)


def _parse_sse_delta(line: str) -> str | None:
    """One `data:` line of an OpenAI-style stream; anything unparsable is skipped."""
    if not line.startswith("data:"):
        return None
    body = line[len("data:") :].strip()
    if not body or body == "[DONE]":
        return None
    try:
        chunk = json.loads(body)
        content = chunk["choices"][0]["delta"].get("content")
    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
        return None
    return str(content) if content else None


def _parse_ndjson_delta(line: str) -> str | None:
    """One JSON object per line, as Ollama streams it."""
    if not line.strip():
        return None
    try:
        chunk = json.loads(line)
        content = chunk.get("message", {}).get("content")
    except (json.JSONDecodeError, AttributeError):
        return None
    return str(content) if content else None


def _retry_after(response: httpx.Response) -> float | None:
    value = response.headers.get("retry-after")
    try:
        return float(value) if value else None
    except ValueError:
        return None


class FallbackProvider:
    """Try providers in order (ADR-09); the next one takes over when one gives up."""

    def __init__(self, providers: list[tuple[str, LLMProvider]]) -> None:
        if not providers:
            raise ValueError("at least one provider required")
        self._providers = providers

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        last_error: LLMError | None = None
        for name, provider in self._providers:
            try:
                return provider.complete(messages, json_mode=json_mode, max_tokens=max_tokens)
            except LLMError as exc:
                log.warning("LLM %s failed (%s), falling back", name, exc)
                last_error = exc
        assert last_error is not None
        raise last_error

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        last_error: LLMError | None = None
        for name, provider in self._providers:
            emitted = False
            try:
                for piece in provider.stream(messages):
                    emitted = True
                    yield piece
                return
            except LLMError as exc:
                if emitted:
                    raise  # half an answer is on screen; a second provider would repeat it
                log.warning("LLM %s failed (%s), falling back", name, exc)
                last_error = exc
        assert last_error is not None
        raise last_error


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        return OllamaProvider(
            settings.ollama_base_url, settings.ollama_model, settings.llm_temperature
        )

    def mistral(model: str, max_attempts: int = 4, max_delay: float = 20.0) -> MistralProvider:
        return MistralProvider(
            api_key=settings.mistral_api_key,
            model=model,
            base_url=settings.mistral_base_url,
            temperature=settings.llm_temperature,
            timeout=settings.llm_timeout_seconds,
            max_attempts=max_attempts,
            max_delay=max_delay,
        )

    fallback_model = settings.mistral_fallback_model.strip()
    if not fallback_model or fallback_model == settings.mistral_model:
        return mistral(settings.mistral_model)
    # With a fallback available, give up on the primary quickly instead of waiting for backoff.
    return FallbackProvider(
        [
            (settings.mistral_model, mistral(settings.mistral_model, max_attempts=2, max_delay=3)),
            (fallback_model, mistral(fallback_model)),
        ]
    )


@lru_cache
def get_llm() -> LLMProvider:
    return build_llm(get_settings())
