"""Notebook overview: what the sources cover together, and what to ask across them.

Built from the per-source guides rather than the raw text — the summaries already condense each
document, so this stays one small LLM call no matter how large the notebook is.
"""

import logging
from dataclasses import dataclass

from pydantic import BaseModel, Field, field_validator

from app.ingest.guide import parse_json_object, plain
from app.llm import prompts
from app.llm.provider import LLMError, LLMProvider

log = logging.getLogger(__name__)

MAX_QUESTIONS = 4
MAX_SOURCES = 25


@dataclass(frozen=True)
class SourceDigest:
    title: str
    summary: str
    key_topics: list[str]


class Overview(BaseModel):
    summary: str = Field(min_length=1)
    key_questions: list[str] = Field(default_factory=list)

    @field_validator("summary", mode="before")
    @classmethod
    def _clean_summary(cls, value: object) -> str:
        return plain(value)

    @field_validator("key_questions", mode="before")
    @classmethod
    def _clean_questions(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [plain(v) for v in value if plain(v)]


def build_overview(llm: LLMProvider, title: str, sources: list[SourceDigest]) -> Overview:
    if not sources:
        raise LLMError("Keine fertigen Quellen für den Überblick.")

    listed = "\n\n".join(
        f"Quelle: {s.title}\nThemen: {', '.join(s.key_topics) or '—'}\n{s.summary}"
        for s in sources[:MAX_SOURCES]
    )
    raw = llm.complete(
        [
            {"role": "system", "content": prompts.OVERVIEW_SYSTEM},
            {
                "role": "user",
                "content": prompts.OVERVIEW_USER.format(title=title, sources=listed),
            },
        ],
        json_mode=True,
    )
    overview = Overview.model_validate(parse_json_object(raw, "Überblick"))
    overview.key_questions = overview.key_questions[:MAX_QUESTIONS]
    return overview
