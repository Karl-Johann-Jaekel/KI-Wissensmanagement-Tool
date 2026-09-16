"""Reports: a set of questions, answered from the sources and written up as a cited note.

Rather than inventing a second way to write grounded text, this runs the ordinary chat path
once per question and stitches the answers together. The citation rules of ADR-05 therefore
apply unchanged, and the finished document lands in the notes with working citations (ADR-11).

The kinds differ only in where their questions come from (ADR-13):
- briefing: the notebook's key questions, i.e. the overview's view of the whole collection
- faq: the questions each source guide proposes, spread across the sources
"""

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.citations import is_grounded
from app.config import Settings
from app.llm import prompts
from app.llm.provider import LLMProvider
from app.models import Notebook, Source
from app.retrieval.embed import Embedder
from app.routers.chat import build_answer_messages, retrieve_passages, validate_answer
from app.schemas import Citation

log = logging.getLogger(__name__)

ReportKind = Literal["briefing", "faq"]

TITLE_CHARS = 300
# A report section stands on its own, without a follow-up question to fill gaps, so it gets
# more passages to work with than a chat turn.
PASSAGE_FACTOR = 2
UNGROUNDED_NOTE = (
    "\n\n**Ohne Beleg:** Dieser Abschnitt stützt sich auf keine Passage und ist nicht aus den "
    "Quellen geprüft."
)
_MARKER = re.compile(r"\[(\d+)\]")


@dataclass(frozen=True)
class ReportSpec:
    title: str
    intro: str
    max_sections: int


SPECS: dict[ReportKind, ReportSpec] = {
    "briefing": ReportSpec(prompts.BRIEFING_TITLE, prompts.BRIEFING_INTRO, 4),
    "faq": ReportSpec(prompts.FAQ_TITLE, prompts.FAQ_INTRO, 6),
}


class ReportError(RuntimeError):
    """Nothing to write about; the message is safe to show to users."""


def build_report(
    db: Session,
    notebook: Notebook,
    kind: ReportKind,
    source_ids: list[uuid.UUID] | None,
    embedder: Embedder,
    llm: LLMProvider,
    settings: Settings,
) -> tuple[str, str, list[Citation]]:
    """Return title, Markdown body and the citations used across all sections."""
    spec = SPECS[kind]
    questions = _questions(db, notebook, kind, source_ids)
    if not questions:
        raise ReportError("Dafür fehlen Fragen. Warte, bis die Quellen-Guides fertig sind.")

    settings = settings.model_copy(
        update={"retrieval_top_k": settings.retrieval_top_k * PASSAGE_FACTOR}
    )
    parts = [spec.intro.format(title=notebook.title)]
    citations: list[Citation] = []
    numbers: dict[str, int] = {}  # chunk id -> number in the finished document

    for question in questions[: spec.max_sections]:
        passages = retrieve_passages(db, notebook.id, question, source_ids, embedder, settings, [])
        if not passages:
            continue
        raw = llm.complete(build_answer_messages(question, passages, []))
        answer, found = validate_answer(raw, passages)
        section = _renumber(answer, found, citations, numbers)
        if not is_grounded(answer, list(found)):
            section += UNGROUNDED_NOTE
        parts.append(f"## {question}\n\n{section}")

    if len(parts) == 1:
        raise ReportError("Zu den Fragen wurden keine passenden Passagen gefunden.")

    return spec.title.format(title=notebook.title)[:TITLE_CHARS], "\n\n".join(parts), citations


def _questions(
    db: Session, notebook: Notebook, kind: ReportKind, source_ids: list[uuid.UUID] | None
) -> list[str]:
    per_source = _source_questions(db, notebook.id, source_ids)
    if kind == "faq":
        return _round_robin(per_source)
    # A briefing looks at the collection as a whole; without an overview yet, one question per
    # source is the closest stand-in.
    if notebook.key_questions:
        return list(notebook.key_questions)
    return [questions[0] for questions in per_source if questions]


def _source_questions(
    db: Session, notebook_id: uuid.UUID, source_ids: list[uuid.UUID] | None
) -> list[list[str]]:
    rows = db.execute(
        select(Source.suggested_questions)
        .where(
            Source.notebook_id == notebook_id,
            Source.status == "ready",
            Source.guide_status == "ready",
            *([Source.id.in_(source_ids)] if source_ids else []),
        )
        .order_by(Source.created_at)
    ).all()
    return [list(questions or []) for (questions,) in rows]


def _round_robin(per_source: list[list[str]]) -> list[str]:
    """One question from each source before any source contributes a second."""
    picked: list[str] = []
    depth = max((len(q) for q in per_source), default=0)
    for i in range(depth):
        for questions in per_source:
            if i < len(questions):
                picked.append(questions[i])
    return picked


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
