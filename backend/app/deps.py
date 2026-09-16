"""Process-wide singletons, injected via FastAPI dependencies so tests can override them."""

from functools import lru_cache

from app.config import get_settings
from app.llm.provider import LLMProvider
from app.llm.provider import get_llm as _get_llm
from app.retrieval.embed import Embedder, FastEmbedder


@lru_cache
def get_embedder() -> Embedder:
    settings = get_settings()
    return FastEmbedder(settings.embedding_model, cache_dir=settings.embedding_cache_dir)


def get_llm() -> LLMProvider:
    return _get_llm()
