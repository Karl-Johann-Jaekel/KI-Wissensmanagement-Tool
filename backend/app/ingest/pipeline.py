"""Background ingestion: parse → chunk → embed → store → guide.

Runs in FastAPI's threadpool after the upload response was sent. Each step commits, so the
source becomes chat-ready before the (slow, rate-limited) guide is generated.
"""

import logging
import uuid
from collections.abc import Callable

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_sessionmaker
from app.ingest.chunker import chunk_segments
from app.ingest.guide import build_guide
from app.ingest.parsers import ParsedDocument, ParseError
from app.llm.provider import LLMError, LLMProvider
from app.models import Chunk, Source
from app.retrieval.embed import Embedder

log = logging.getLogger(__name__)

GENERIC_ERROR = "Unerwarteter Fehler bei der Verarbeitung."


def ingest_source(
    source_id: uuid.UUID,
    load: Callable[[], ParsedDocument],
    embedder: Embedder,
    llm: LLMProvider,
) -> None:
    settings = get_settings()
    with get_sessionmaker()() as db:
        initial = db.get(Source, source_id)
        placeholder = initial.title if initial else None
        db.rollback()  # do not hold a transaction open during the slow load/embed steps
        try:
            document = load()
            drafts = chunk_segments(
                document.segments, settings.chunk_max_chars, settings.chunk_overlap_chars
            )
            if not drafts:
                raise ParseError("Die Quelle enthält keinen verwertbaren Text.")
            vectors = embedder.embed_passages([d.content for d in drafts])

            source = db.get(Source, source_id)
            if source is None:  # deleted while processing
                return
            db.add_all(
                Chunk(
                    source_id=source_id,
                    ordinal=d.ordinal,
                    page=d.page,
                    content=d.content,
                    embedding=v,
                )
                for d, v in zip(drafts, vectors, strict=True)
            )
            if source.title == placeholder:  # keep a title the user set while processing
                source.title = document.title
            source.page_count = document.page_count
            source.status = "ready"
            db.commit()
        except ParseError as exc:
            _fail(db, source_id, str(exc))
            return
        except Exception:
            log.exception("Ingestion failed for source %s", source_id)
            _fail(db, source_id, GENERIC_ERROR)
            return

    generate_guide(source_id, llm)


def generate_guide(source_id: uuid.UUID, llm: LLMProvider) -> None:
    with get_sessionmaker()() as db:
        source = db.get(Source, source_id)
        if source is None:
            return
        contents = list(
            db.scalars(
                select(Chunk.content).where(Chunk.source_id == source_id).order_by(Chunk.ordinal)
            )
        )
        try:
            guide = build_guide(llm, source.title, contents)
        except LLMError as exc:
            _set_guide(db, source_id, status="error", error=str(exc))
            return
        except Exception:
            log.exception("Guide generation failed for source %s", source_id)
            _set_guide(db, source_id, status="error", error=GENERIC_ERROR)
            return
        _set_guide(
            db,
            source_id,
            status="ready",
            summary=guide.summary,
            key_topics=guide.key_topics,
            suggested_questions=guide.suggested_questions,
        )


def recover_interrupted(db: Session) -> None:
    """Background jobs die with the process; mark leftovers so the UI does not spin forever."""
    db.execute(
        update(Source)
        .where(Source.status == "processing")
        .values(status="error", error="Verarbeitung wurde unterbrochen. Bitte erneut hochladen.")
    )
    db.execute(
        update(Source)
        .where(Source.status == "ready", Source.guide_status == "pending")
        .values(guide_status="error", guide_error="Guide-Erstellung wurde unterbrochen.")
    )
    db.commit()


def _fail(db: Session, source_id: uuid.UUID, message: str) -> None:
    db.rollback()
    db.execute(update(Source).where(Source.id == source_id).values(status="error", error=message))
    db.commit()


def _set_guide(
    db: Session, source_id: uuid.UUID, *, status: str, error: str | None = None, **fields: object
) -> None:
    db.execute(
        update(Source)
        .where(Source.id == source_id)
        .values(guide_status=status, guide_error=error, **fields)
    )
    db.commit()
