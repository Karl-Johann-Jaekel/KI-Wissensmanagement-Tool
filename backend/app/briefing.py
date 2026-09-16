"""Briefing document: the notebook's key questions, answered from the sources and cited.

Rather than inventing a second way to write grounded text, this runs the ordinary chat path
once per question and stitches the answers together. The citation rules of ADR-05 therefore
apply unchanged, and the finished document lands in the notes with working citations (ADR-11).
"""

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.llm import prompts
from app.llm.provider import LLMProvider
from app.models import Notebook, Source
from app.retrieval.embed import Embedder
from app.routers.chat import build_answer_messages, retrieve_passages, validate_answer
from app.schemas import Citation

log = logging.getLogger(__name__)

MAX_SECTIONS = 4
TITLE_CHARS = 300
# A briefing section stands on its own, without a follow-up question to fill gaps, so it gets
# more passages to work with than a chat turn.
PASSAGE_FACTOR = 2
_MARKER = re.compile(r"\[(\d+)\]")


class BriefingError(RuntimeError):
    """Nothing to write about; the message is safe to show to users."""


def build_briefing(
    db: Session,
    notebook: Notebook,
    source_ids: list[uuid.UUID] | None,
    embedder: Embedder,
    llm: LLMProvider,
    settings: Settings,
) -> tuple[str, str, list[Citation]]:
    """Return title, Markdown body and the citations used across all sections."""
    questions = _questions(db, notebook, source_ids)
    if not questions:
        raise BriefingError(
            "Für ein Briefing fehlen Fragen. Warte, bis die Quellen-Guides fertig sind."
        )

    settings = settings.model_copy(
        update={"retrieval_top_k": settings.retrieval_top_k * PASSAGE_FACTOR}
    )
    parts = [prompts.BRIEFING_INTRO.format(title=notebook.title)]
    citations: list[Citation] = []
    numbers: dict[str, int] = {}  # chunk id -> number in the finished document

    for question in questions[:MAX_SECTIONS]:
        passages = retrieve_passages(db, notebook.id, question, source_ids, embedder, settings, [])
        if not passages:
            continue
        raw = llm.complete(build_answer_messages(question, passages, []))
        answer, found = validate_answer(raw, passages)
        parts.append(f"## {question}\n\n{_renumber(answer, found, citations, numbers)}")

    if len(parts) == 1:
        raise BriefingError("Zu den Kernfragen wurden keine passenden Passagen gefunden.")

    title = prompts.BRIEFING_TITLE.format(title=notebook.title)[:TITLE_CHARS]
    return title, "\n\n".join(parts), citations


def _questions(db: Session, notebook: Notebook, source_ids: list[uuid.UUID] | None) -> list[str]:
    """The notebook's key questions, or one suggested question per source as a fallback."""
    if notebook.key_questions:
        return list(notebook.key_questions)

    rows = db.execute(
        select(Source.suggested_questions)
        .where(
            Source.notebook_id == notebook.id,
            Source.status == "ready",
            Source.guide_status == "ready",
            *([Source.id.in_(source_ids)] if source_ids else []),
        )
        .order_by(Source.created_at)
    ).all()
    return [questions[0] for (questions,) in rows if questions]


def _renumber(
    answer: str,
    found: list[Citation],
    document: list[Citation],
    numbers: dict[str, int],
) -> str:
    """Move one section's `[1]`, `[2]` … onto document-wide numbering.

    Each section is validated against its own passages and therefore starts at [1]. A passage
    cited in two sections keeps one number, so the reader sees a single list of sources.
    """
    mapping: dict[int, int] = {}
    for citation in found:
        key = str(citation.chunk_id)
        if key not in numbers:
            numbers[key] = len(numbers) + 1
            document.append(citation.model_copy(update={"n": numbers[key]}))
        mapping[citation.n] = numbers[key]
    # one pass, so swapped numbers cannot overwrite each other
    return _MARKER.sub(lambda m: f"[{mapping.get(int(m.group(1)), int(m.group(1)))}]", answer)
