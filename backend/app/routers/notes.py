import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.citations import is_grounded, ungrounded_notice
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_embedder, get_llm
from app.llm.provider import LLMError, LLMProvider
from app.models import Message, Note, Notebook
from app.reports import ReportError, build_report
from app.retrieval.embed import Embedder
from app.routers.common import get_or_404
from app.schemas import NoteCreate, NoteOut, NoteUpdate, ReportRequest

router = APIRouter(tags=["notes"])
DB = Annotated[Session, Depends(get_db)]

TITLE_CHARS = 120


@router.get("/notebooks/{notebook_id}/notes", response_model=list[NoteOut])
def list_notes(notebook_id: uuid.UUID, db: DB) -> list[Note]:
    get_or_404(db, Notebook, notebook_id)
    return list(
        db.scalars(
            select(Note).where(Note.notebook_id == notebook_id).order_by(Note.updated_at.desc())
        )
    )


@router.post(
    "/notebooks/{notebook_id}/notes", response_model=NoteOut, status_code=status.HTTP_201_CREATED
)
def create_note(notebook_id: uuid.UUID, payload: NoteCreate, db: DB) -> Note:
    get_or_404(db, Notebook, notebook_id)
    note = Note(notebook_id=notebook_id, title=payload.title.strip(), content=payload.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.post(
    "/notebooks/{notebook_id}/notes/from-message/{message_id}",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_note_from_message(notebook_id: uuid.UUID, message_id: uuid.UUID, db: DB) -> Note:
    """Save an answer as note, keeping its citations clickable."""
    message = get_or_404(db, Message, message_id)
    if message.notebook_id != notebook_id or message.role != "assistant":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Answer not found")

    question = db.scalar(
        select(Message.content)
        .where(
            Message.notebook_id == notebook_id,
            Message.role == "user",
            Message.created_at <= message.created_at,
            Message.id != message.id,
        )
        .order_by(Message.created_at.desc())
        .limit(1)
    )
    title = (question or "Gespeicherte Antwort").strip()
    if len(title) > TITLE_CHARS:
        title = title[: TITLE_CHARS - 1].rstrip() + "…"

    content = message.content
    # The chat marks such an answer next to it (ADR-14); a note keeps only its text.
    if not is_grounded(message.content, list(message.citations)):
        content += ungrounded_notice("Diese Antwort")

    note = Note(
        notebook_id=notebook_id,
        title=title,
        content=content,
        citations=message.citations,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.post(
    "/notebooks/{notebook_id}/reports", response_model=NoteOut, status_code=status.HTTP_201_CREATED
)
def create_report(
    notebook_id: uuid.UUID,
    payload: ReportRequest,
    db: DB,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    llm: Annotated[LLMProvider, Depends(get_llm)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Note:
    """Answer a set of questions from the sources and save the result as a cited note."""
    notebook = get_or_404(db, Notebook, notebook_id)
    try:
        title, content, citations = build_report(
            db, notebook, payload.kind, payload.source_ids, embedder, llm, settings
        )
    except ReportError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except LLMError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    note = Note(
        notebook_id=notebook_id,
        title=title,
        content=content,
        citations=[c.model_dump(mode="json") for c in citations],
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.patch("/notes/{note_id}", response_model=NoteOut)
def update_note(note_id: uuid.UUID, payload: NoteUpdate, db: DB) -> Note:
    note = get_or_404(db, Note, note_id)
    if payload.title is not None:
        note.title = payload.title.strip()
    if payload.content is not None:
        note.content = payload.content
    db.commit()
    db.refresh(note)
    return note


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: uuid.UUID, db: DB) -> Response:
    db.delete(get_or_404(db, Note, note_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
