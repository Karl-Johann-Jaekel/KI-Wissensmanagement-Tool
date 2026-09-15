from functools import lru_cache
from typing import Literal

from pydantic import Field, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore")

    database_url: str
    access_key: str = Field(min_length=12)

    llm_provider: Literal["mistral", "ollama"] = "mistral"
    mistral_api_key: str = ""
    mistral_model: str = "ministral-14b-latest"
    mistral_base_url: str = "https://api.mistral.ai/v1"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.1:8b"
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 90.0

    embedding_model: str = "intfloat/multilingual-e5-small"
    embedding_cache_dir: str = "/opt/models"

    max_upload_mb: int = 20
    chunk_max_chars: int = 1800
    chunk_overlap_chars: int = 300
    retrieval_candidates: int = 20
    retrieval_top_k: int = 8


@lru_cache
def get_settings() -> Settings:
    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        # Pydantic's default message echoes input values, which would leak secrets into logs.
        problems = ", ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        raise RuntimeError(f"Invalid configuration: {problems}") from None
