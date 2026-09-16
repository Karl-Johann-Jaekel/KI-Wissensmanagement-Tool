"""Deterministic stand-ins for the embedding model and the LLM."""

import hashlib
import json
import math
import re
from collections.abc import Callable, Iterator

from app.llm.provider import ChatMessage

DIM = 384


class FakeEmbedder:
    """Hashed bag-of-words: texts sharing words get similar vectors."""

    def _vector(self, text: str) -> list[float]:
        vec = [0.0] * DIM
        for word in re.findall(r"\w+", text.lower()):
            if word in {"query", "passage"}:
                continue
            bucket = int(hashlib.md5(word.encode()).hexdigest(), 16) % DIM  # noqa: S324
            vec[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        return [v / norm for v in vec]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


class FakeLLM:
    """Returns JSON for json_mode calls and a scripted answer for chat calls."""

    def __init__(self, answer: str | Callable[[list[ChatMessage]], str] = "Antwort [1].") -> None:
        self.answer = answer
        self.calls: list[tuple[list[ChatMessage], bool]] = []

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_mode: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        self.calls.append((messages, json_mode))
        if json_mode:
            return json.dumps(
                {
                    "summary": "Eine kurze Zusammenfassung.",
                    "key_topics": ["Thema A", "Thema B", "Thema C"],
                    "suggested_questions": ["Frage 1?", "Frage 2?", "Frage 3?"],
                }
            )
        return self.answer(messages) if callable(self.answer) else self.answer

    def stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        """Word by word, so tests see more than one delta event."""
        answer = self.complete(messages)
        for i, word in enumerate(answer.split(" ")):
            yield word if i == 0 else f" {word}"
