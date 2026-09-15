"""Source guide: summary, key topics and suggested questions (map-reduce for long sources)."""

import json
import logging
import math
import re

from pydantic import BaseModel, Field, ValidationError, field_validator

from app.llm import prompts
from app.llm.provider import LLMError, LLMProvider

log = logging.getLogger(__name__)

DIRECT_MAX_CHUNKS = 8
GROUP_TARGET_CHARS = 24_000
MAX_GROUPS = 8
DIRECT_MAX_CHARS = 60_000


class Guide(BaseModel):
    summary: str = Field(min_length=1)
    key_topics: list[str] = Field(default_factory=list)
    suggested_questions: list[str] = Field(default_factory=list)

    @field_validator("key_topics", "suggested_questions", mode="before")
    @classmethod
    def _clean_list(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(v).strip() for v in value if str(v).strip()]


def build_guide(llm: LLMProvider, title: str, chunks: list[str]) -> Guide:
    if not chunks:
        raise LLMError("Keine Inhalte für den Quellen-Guide.")

    if len(chunks) <= DIRECT_MAX_CHUNKS:
        text, partial = "\n\n".join(chunks), False
    else:
        summaries = [_summarize_group(llm, group) for group in group_chunks(chunks)]
        text, partial = "\n\n".join(summaries), True

    user = prompts.GUIDE_USER.format(
        title=title,
        partial_hint=" (Zusammenfassungen der Abschnitte)" if partial else "",
        text=text[:DIRECT_MAX_CHARS],
    )
    raw = llm.complete(
        [{"role": "system", "content": prompts.GUIDE_SYSTEM}, {"role": "user", "content": user}],
        json_mode=True,
    )
    guide = parse_guide(raw)
    guide.key_topics = guide.key_topics[:5]
    guide.suggested_questions = guide.suggested_questions[:3]
    return guide


def group_chunks(chunks: list[str]) -> list[list[str]]:
    """Consecutive groups of ~GROUP_TARGET_CHARS, at most MAX_GROUPS (fewer LLM calls)."""
    total = sum(len(c) for c in chunks)
    target = max(GROUP_TARGET_CHARS, math.ceil(total / MAX_GROUPS))
    groups: list[list[str]] = [[]]
    size = 0
    for chunk in chunks:
        if groups[-1] and size + len(chunk) > target:
            groups.append([])
            size = 0
        groups[-1].append(chunk)
        size += len(chunk)
    return groups


def _summarize_group(llm: LLMProvider, group: list[str]) -> str:
    return llm.complete(
        [
            {"role": "system", "content": prompts.MAP_SYSTEM},
            {"role": "user", "content": "\n\n".join(group)},
        ],
        max_tokens=600,
    ).strip()


def parse_guide(raw: str) -> Guide:
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip())
    try:
        return Guide.model_validate(json.loads(cleaned))
    except (json.JSONDecodeError, ValidationError) as exc:
        log.warning("Guide JSON invalid: %s", raw[:300])
        raise LLMError("Der Quellen-Guide hatte ein ungültiges Format.") from exc
