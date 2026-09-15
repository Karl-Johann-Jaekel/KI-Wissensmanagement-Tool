import logging
import re
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.citations import Passage, resolve_citations, strip_citations
from app.config import Settings, get_settings
from app.db import get_db
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
FOLLOW_UP_MAX_WORDS = 6


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

    retrieved: list[RetrievedChunk] = []
    if payload.source_ids is None or payload.source_ids:
        retrieval_query = _retrieval_query(question, history)
        retrieved = hybrid_search(
            db,
            notebook_id=notebook_id,
            source_ids=payload.source_ids,
            question=retrieval_query,
            query_vector=embedder.embed_query(retrieval_query),
            candidates=settings.retrieval_candidates,
            top_k=settings.retrieval_top_k,
        )

    citations: list[Citation] = []
    if not retrieved:
        answer = prompts.NO_SOURCES_ANSWER
    else:
        passages = [
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
        try:
            raw = llm.complete(_build_messages(question, passages, history))
        except LLMError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
        answer, resolved = resolve_citations(raw, passages)
        citations = [Citation(**vars(c)) for c in resolved]
        if not answer:
            answer = prompts.NO_SOURCES_ANSWER

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


def _retrieval_query(question: str, history: list[Message]) -> str:
    """Short follow-ups ("und warum?") get the previous question as retrieval context."""
    if len(question.split()) > FOLLOW_UP_MAX_WORDS:
        return question
    previous = next((m.content for m in reversed(history) if m.role == "user"), None)
    return f"{previous} {question}" if previous else question


def _build_messages(
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
