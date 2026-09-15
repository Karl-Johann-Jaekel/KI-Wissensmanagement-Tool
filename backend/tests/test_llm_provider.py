import json

import httpx
import pytest

from app.config import Settings
from app.llm.provider import (
    FallbackProvider,
    LLMError,
    MistralProvider,
    OllamaProvider,
    build_llm,
)


def _mistral(handler, sleeps: list[float] | None = None) -> MistralProvider:  # type: ignore[no-untyped-def]
    return MistralProvider(
        api_key="k",
        model="mistral-small-latest",
        transport=httpx.MockTransport(handler),
        sleep=(sleeps.append if sleeps is not None else lambda _s: None),
    )


def _ok(content: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": content}}]})


def test_mistral_sends_json_mode_and_returns_content() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        seen["auth"] = request.headers["authorization"]
        return _ok('{"a": 1}')

    result = _mistral(handler).complete([{"role": "user", "content": "hi"}], json_mode=True)
    assert result == '{"a": 1}'
    assert seen["response_format"] == {"type": "json_object"}
    assert seen["temperature"] == 0.2
    assert seen["auth"] == "Bearer k"


def test_mistral_retries_on_rate_limit_and_respects_retry_after() -> None:
    responses = iter(
        [httpx.Response(429, headers={"retry-after": "3"}), httpx.Response(503), _ok("ok")]
    )
    sleeps: list[float] = []
    result = _mistral(lambda _r: next(responses), sleeps).complete(
        [{"role": "user", "content": "x"}]
    )
    assert result == "ok"
    assert sleeps == [3.0, 2.0]


def test_mistral_gives_up_after_max_attempts() -> None:
    sleeps: list[float] = []
    provider = _mistral(lambda _r: httpx.Response(429), sleeps)
    with pytest.raises(LLMError, match="nicht erreichbar"):
        provider.complete([{"role": "user", "content": "x"}])
    assert len(sleeps) == provider.max_attempts - 1


def test_mistral_does_not_retry_client_errors() -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(401, json={"message": "Unauthorized"})

    with pytest.raises(LLMError, match="abgelehnt"):
        _mistral(handler).complete([{"role": "user", "content": "x"}])
    assert len(calls) == 1


def test_zero_quota_fails_fast_without_retry() -> None:
    sleeps: list[float] = []
    provider = _mistral(
        lambda _r: httpx.Response(429, headers={"x-ratelimit-limit-req-minute": "0"}), sleeps
    )
    with pytest.raises(LLMError, match="Kontingent"):
        provider.complete([{"role": "user", "content": "x"}])
    assert sleeps == []


def test_missing_mistral_key_fails_fast() -> None:
    provider = MistralProvider(api_key="", model="m")
    with pytest.raises(LLMError, match="MISTRAL_API_KEY"):
        provider.complete([{"role": "user", "content": "x"}])


class _Scripted:
    def __init__(self, result: str | LLMError) -> None:
        self.result = result
        self.calls = 0

    def complete(self, messages, *, json_mode=False, max_tokens=None):  # type: ignore[no-untyped-def]
        self.calls += 1
        if isinstance(self.result, LLMError):
            raise self.result
        return self.result


def test_fallback_takes_over_when_primary_fails() -> None:
    primary, fallback = _Scripted(LLMError("rate limit")), _Scripted("aus 8B")
    provider = FallbackProvider([("14b", primary), ("8b", fallback)])
    assert provider.complete([{"role": "user", "content": "x"}], json_mode=True) == "aus 8B"
    assert (primary.calls, fallback.calls) == (1, 1)


def test_fallback_is_not_called_when_primary_succeeds() -> None:
    primary, fallback = _Scripted("aus 14B"), _Scripted("aus 8B")
    FallbackProvider([("14b", primary), ("8b", fallback)]).complete([])
    assert fallback.calls == 0


def test_fallback_raises_last_error_when_all_fail() -> None:
    provider = FallbackProvider(
        [("14b", _Scripted(LLMError("erstes"))), ("8b", _Scripted(LLMError("zweites")))]
    )
    with pytest.raises(LLMError, match="zweites"):
        provider.complete([])


def _settings(**overrides: object) -> Settings:
    base = {"database_url": "postgresql+psycopg://x", "access_key": "a" * 12}
    return Settings(**{**base, **overrides})  # type: ignore[arg-type]


def test_build_llm_chains_primary_with_short_retries_and_fallback() -> None:
    llm = build_llm(_settings(mistral_model="ministral-14b-latest"))
    assert isinstance(llm, FallbackProvider)
    (primary_name, primary), (fallback_name, fallback) = llm._providers
    assert (primary_name, fallback_name) == ("ministral-14b-latest", "ministral-8b-latest")
    assert isinstance(primary, MistralProvider) and primary.max_attempts == 2
    assert isinstance(fallback, MistralProvider) and fallback.max_attempts == 4


def test_build_llm_without_fallback_or_with_ollama() -> None:
    assert isinstance(build_llm(_settings(mistral_fallback_model="")), MistralProvider)
    assert isinstance(build_llm(_settings(llm_provider="ollama")), OllamaProvider)


def test_ollama_uses_chat_endpoint_with_json_format() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen.update(json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": "hallo"}})

    provider = OllamaProvider(
        "http://ollama:11434", "llama3.1:8b", transport=httpx.MockTransport(handler)
    )
    assert provider.complete([{"role": "user", "content": "x"}], json_mode=True) == "hallo"
    assert seen["path"] == "/api/chat"
    assert seen["format"] == "json"
    assert seen["stream"] is False
