import json

import httpx
import pytest

from app.llm.provider import LLMError, MistralProvider, OllamaProvider


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
    with pytest.raises(LLMError):
        MistralProvider(api_key="", model="m")


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
