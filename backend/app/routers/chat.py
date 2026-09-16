import json
import logging
import re
import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.citations import Passage, resolve_citations, strip_citations
from app.config import Settings, get_settings
from app.db import get_db, get_sessionmaker
from app.deps import get_embedder, get_llm
from app.llm import prompts
from app.llm.provider import ChatMessage, LLMError, LLMProvider
from app.models import Message, Notebook
from app.retrieval.embed import Embedder
from app.retrieval.search import RetrievedChunk, hybrid_search
from app.routers.common import get_or_404
from app.schemas import ChatRequest, ChatResponse, Citation, MessageOut

log = logging.getLogger(__name__)

router = APIRouter(tags=["chat"])
DB = Annotated[Session, Depends(get_db)]

HISTORY_MESSAGES = 6
HISTORY_CHARS = 400

# Words that point back at the previous turn. Articles are left out on purpose: in
# "Ab wann gilt die Verordnung?" the "die" belongs to a complete question, not to a follow-up.
_ANAPHORA = frozenset(
    """
    dies diese dieser dieses diesem diesen dazu davon darin darauf dabei dafür dagegen daraus
    darüber darunter hierzu hierbei hierfür dort dessen deren jene jener jenes ihn ihm ihnen
    this these those it its they them their
    """.split()  # noqa: SIM905 - a word list reads better as text
)
_LEADING_CONJUNCTIONS = frozenset({"und", "aber", "and", "but"})
# ambiguous words that are a pronoun only at the very end: "Was bedeutet das?"
_TRAILING_PRONOUNS = frozenset({"das", "sie", "es", "that"})


@router.get("/notebooks/{notebook_id}/messages", response_model=list[MessageOut])
def list_messages(notebook_id: uuid.UUID, db: DB) -> list[Message]:
    get_or_404(db, Notebook, notebook_id)
    return list(
        db.scalars(
            select(Message)
            .where(Message.notebook_id == notebook_id)
            .order_by(Message.created_at, Message.role.desc())
        )
    )


@router.delete("/notebooks/{notebook_id}/messages", status_code=status.HTTP_204_NO_CONTENT)
def clear_messages(notebook_id: uuid.UUID, db: DB) -> Response:
    get_or_404(db, Notebook, notebook_id)
    db.execute(delete(Message).where(Message.notebook_id == notebook_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/notebooks/{notebook_id}/chat", response_model=ChatResponse)
def chat(
    notebook_id: uuid.UUID,
    payload: ChatRequest,
    db: DB,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatResponse:
    get_or_404(db, Notebook, notebook_id)
    question = payload.question.strip()
    history = _recent_history(db, notebook_id)
    passages = retrieve_passages(
        db, notebook_id, question, payload.source_ids, embedder, settings, history
    )

    citations: list[Citation] = []
    if not passages:
        answer = prompts.NO_SOURCES_ANSWER
    else:
        try:
            raw = llm.complete(build_answer_messages(question, passages, history))
        except LLMError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
        answer, citations = validate_answer(raw, passages)
    return persist_exchange(db, notebook_id, question, answer, citations)


@router.post("/notebooks/{notebook_id}/chat/stream")
def chat_stream(
    notebook_id: uuid.UUID,
    payload: ChatRequest,
    db: DB,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> StreamingResponse:
    """Same answer as `chat`, delivered as server-sent events while it is written.

    Validation still runs on the finished text (ADR-05), so `delta` events carry the model's
    raw wording; the `done` event replaces it with the checked and renumbered answer.
    """
    get_or_404(db, Notebook, notebook_id)
    return StreamingResponse(
        _answer_events(
            notebook_id, payload.question.strip(), payload.source_ids, embedder, llm, settings
        ),
        media_type="text/event-stream",
        # nginx buffers proxied responses by default, which would hold every event back until
        # the answer is complete.
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _answer_events(
    notebook_id: uuid.UUID,
    question: str,
    source_ids: list[uuid.UUID] | None,
    embedder: Embedder,
    llm: LLMProvider,
    settings: Settings,
) -> Iterator[str]:
    # Own session: the request-scoped one goes back to the pool when the handler returns, which
    # happens before this generator produces its first event.
    with get_sessionmaker()() as db:
        try:
            history = _recent_history(db, notebook_id)
            passages = retrieve_passages(
                db, notebook_id, question, source_ids, embedder, settings, history
            )
            yield _event(
                type="passages",
                count=len(passages),
                sources=len({p.source_id for p in passages}),
            )

            citations: list[Citation] = []
            if not passages:
                answer = prompts.NO_SOURCES_ANSWER
                yield _event(type="delta", text=answer)
            else:
                raw = ""
                for piece in llm.stream(build_answer_messages(question, passages, history)):
                    raw += piece
                    yield _event(type="delta", text=piece)
                answer, citations = validate_answer(raw, passages)

            response = persist_exchange(db, notebook_id, question, answer, citations)
            yield _event(type="done", **response.model_dump(mode="json"))
        except LLMError as exc:
            yield _event(type="error", detail=str(exc))
        except Exception:
            # The response is already HTTP 200, so failures have to travel as an event.
            log.exception("chat stream failed for notebook %s", notebook_id)
            yield _event(type="error", detail="Die Antwort konnte nicht erzeugt werden.")


def _event(**payload: object) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def retrieve_passages(
    db: Session,
    notebook_id: uuid.UUID,
    question: str,
    source_ids: list[uuid.UUID] | None,
    embedder: Embedder,
    settings: Settings,
    history: list[Message],
) -> list[Passage]:
    """Top passages for the question, or nothing when no source is selected.

    Public because the briefing generator answers its questions through the same path.
    """
    if source_ids is not None and not source_ids:
        return []
    # Word and reference matching use the question as asked. Only the meaning-based vector
    # search borrows the previous question, and only for a genuine follow-up.
    retrieved: list[RetrievedChunk] = hybrid_search(
        db,
        notebook_id=notebook_id,
        source_ids=source_ids,
        question=question,
        query_vector=embedder.embed_query(_vector_query(question, history)),
        candidates=settings.retrieval_candidates,
        top_k=settings.retrieval_top_k,
    )
    return [
        Passage(
            n=i,
            chunk_id=r.chunk_id,
            source_id=r.source_id,
            source_title=r.source_title,
            page=r.page,
            content=r.content,
        )
        for i, r in enumerate(retrieved, start=1)
    ]


def validate_answer(raw: str, passages: list[Passage]) -> tuple[str, list[Citation]]:
    answer, resolved = resolve_citations(raw, passages)
    return answer or prompts.NO_SOURCES_ANSWER, [Citation(**vars(c)) for c in resolved]


def persist_exchange(
    db: Session,
    notebook_id: uuid.UUID,
    question: str,
    answer: str,
    citations: list[Citation],
) -> ChatResponse:
    user_message = Message(notebook_id=notebook_id, role="user", content=question, citations=[])
    db.add(user_message)
    # Both rows share now() (transaction time); queries break the tie by role.
    assistant_message = Message(
        notebook_id=notebook_id,
        role="assistant",
        content=answer,
        citations=[c.model_dump(mode="json") for c in citations],
    )
    db.add(assistant_message)
    db.commit()
    return ChatResponse(
        question=MessageOut.model_validate(user_message),
        answer=MessageOut.model_validate(assistant_message),
    )


def _recent_history(db: Session, notebook_id: uuid.UUID) -> list[Message]:
    rows = db.scalars(
        select(Message)
        .where(Message.notebook_id == notebook_id)
        .order_by(Message.created_at.desc(), Message.role)
        .limit(HISTORY_MESSAGES)
    ).all()
    return list(reversed(rows))


def is_follow_up(question: str) -> bool:
    """Does the question lean on the previous one? ("Und warum?", "Was bedeutet das?")"""
    words = [w.lower() for w in re.findall(r"\w+", question)]
    if not words:
        return False
    if words[0] in _LEADING_CONJUNCTIONS or words[-1] in _TRAILING_PRONOUNS:
        return True
    return any(word in _ANAPHORA for word in words)


def _vector_query(question: str, history: list[Message]) -> str:
    """A follow-up carries little meaning on its own, so the vector search gets context.

    Full-text and reference ranking never get it: they would keep matching words and article
    numbers the user has already moved on from. A short question used to be enough to borrow
    the previous one, which made "Ab wann gilt die Verordnung?" search for "Artikel 50".
    """
    if not is_follow_up(question):
        return question
    previous = next((m.content for m in reversed(history) if m.role == "user"), None)
    return f"{previous} {question}" if previous else question


def build_answer_messages(
    question: str, passages: list[Passage], history: list[Message]
) -> list[ChatMessage]:
    messages: list[ChatMessage] = [{"role": "system", "content": prompts.CHAT_SYSTEM}]
    for message in history:
        messages.append({"role": message.role, "content": condense_for_history(message.content)})
    formatted = "\n\n".join(_format_passage(p) for p in passages)
    messages.append(
        {"role": "user", "content": prompts.CHAT_USER.format(passages=formatted, question=question)}
    )
    return messages


def condense_for_history(content: str) -> str:
    """Plain, short version of an earlier message.

    Full earlier answers act as few-shot examples: in tests with ministral-14b, one verbose answer
    with lists and separator lines made every following answer copy that format.
    """
    text = strip_citations(content)
    text = re.sub(r"\*\*|__|^\s*(?:[-*•]|\d+[.)])\s+|^\s*[-*_]{3,}\s*$", "", text, flags=re.M)
    text = " ".join(text.split())
    if len(text) <= HISTORY_CHARS:
        return text
    return text[:HISTORY_CHARS].rsplit(" ", 1)[0] + " …"


def _format_passage(passage: Passage) -> str:
    location = f", S. {passage.page}" if passage.page else ""
    return f"[{passage.n}] (Quelle: {passage.source_title}{location})\n{passage.content}"
