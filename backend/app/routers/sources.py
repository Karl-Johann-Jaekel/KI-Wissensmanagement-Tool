import functools
import uuid
from pathlib import PurePath
from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import get_embedder, get_llm
from app.ingest.parsers import PDF_EXTENSIONS, TEXT_EXTENSIONS, parse_upload
from app.ingest.pipeline import generate_guide, ingest_source
from app.ingest.url import fetch_url
from app.llm.provider import LLMProvider
from app.models import Chunk, Notebook, Source
from app.retrieval.embed import Embedder
from app.routers.common import get_or_404
from app.schemas import ChunkOut, SourceOut, UrlSourceCreate

router = APIRouter(tags=["sources"])
DB = Annotated[Session, Depends(get_db)]
EmbedderDep = Annotated[Embedder, Depends(get_embedder)]
LLMDep = Annotated[LLMProvider, Depends(get_llm)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


def _to_out(db: Session, sources: list[Source]) -> list[SourceOut]:
    if not sources:
        return []
    rows = db.execute(
        select(Chunk.source_id, func.count())
        .where(Chunk.source_id.in_([s.id for s in sources]))
        .group_by(Chunk.source_id)
    ).all()
    counts: dict[uuid.UUID, int] = {source_id: n for source_id, n in rows}
    return [
        SourceOut.model_validate(s).model_copy(update={"chunk_count": counts.get(s.id, 0)})
        for s in sources
    ]


@router.get("/notebooks/{notebook_id}/sources", response_model=list[SourceOut])
def list_sources(notebook_id: uuid.UUID, db: DB) -> list[SourceOut]:
    get_or_404(db, Notebook, notebook_id)
    sources = db.scalars(
        select(Source).where(Source.notebook_id == notebook_id).order_by(Source.created_at)
    ).all()
    return _to_out(db, list(sources))


@router.post(
    "/notebooks/{notebook_id}/sources",
    response_model=SourceOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_source(
    notebook_id: uuid.UUID,
    file: Annotated[UploadFile, File()],
    background: BackgroundTasks,
    db: DB,
    embedder: EmbedderDep,
    llm: LLMDep,
    settings: SettingsDep,
) -> SourceOut:
    get_or_404(db, Notebook, notebook_id)
    filename = PurePath(file.filename or "upload").name
    suffix = PurePath(filename).suffix.lower()
    if suffix not in PDF_EXTENSIONS | TEXT_EXTENSIONS:
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Nur PDF-, TXT- und MD-Dateien werden unterstützt.",
        )
    limit = settings.max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Die Datei ist größer als {settings.max_upload_mb} MB.",
        )

    source = Source(
        notebook_id=notebook_id,
        title=PurePath(filename).stem or filename,
        type="pdf" if suffix in PDF_EXTENSIONS else "text",
        origin=filename,
    )
    db.add(source)
    db.commit()
    background.add_task(
        ingest_source, source.id, functools.partial(parse_upload, filename, data), embedder, llm
    )
    return _to_out(db, [source])[0]


@router.post(
    "/notebooks/{notebook_id}/sources/url",
    response_model=SourceOut,
    status_code=status.HTTP_202_ACCEPTED,
)
def import_url(
    notebook_id: uuid.UUID,
    payload: UrlSourceCreate,
    background: BackgroundTasks,
    db: DB,
    embedder: EmbedderDep,
    llm: LLMDep,
) -> SourceOut:
    get_or_404(db, Notebook, notebook_id)
    url = str(payload.url)
    source = Source(notebook_id=notebook_id, title=url[:500], type="url", origin=url)
    db.add(source)
    db.commit()
    background.add_task(ingest_source, source.id, functools.partial(fetch_url, url), embedder, llm)
    return _to_out(db, [source])[0]


@router.post(
    "/sources/{source_id}/guide", response_model=SourceOut, status_code=status.HTTP_202_ACCEPTED
)
def regenerate_guide(
    source_id: uuid.UUID, background: BackgroundTasks, db: DB, llm: LLMDep
) -> SourceOut:
    source = get_or_404(db, Source, source_id)
    if source.status != "ready":
        raise HTTPException(status.HTTP_409_CONFLICT, "Die Quelle ist noch nicht verarbeitet.")
    source.guide_status = "pending"
    source.guide_error = None
    db.commit()
    background.add_task(generate_guide, source.id, llm)
    return _to_out(db, [source])[0]


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(source_id: uuid.UUID, db: DB) -> Response:
    db.delete(get_or_404(db, Source, source_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/sources/{source_id}/chunks/{chunk_id}", response_model=ChunkOut)
def get_chunk(source_id: uuid.UUID, chunk_id: uuid.UUID, db: DB) -> ChunkOut:
    chunk = get_or_404(db, Chunk, chunk_id)
    if chunk.source_id != source_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chunk not found")
    source = get_or_404(db, Source, source_id)
    rows = db.execute(
        select(Chunk.ordinal, Chunk.content).where(
            Chunk.source_id == source_id,
            Chunk.ordinal.in_([chunk.ordinal - 1, chunk.ordinal + 1]),
        )
    ).all()
    neighbours: dict[int, str] = {ordinal: content for ordinal, content in rows}
    return ChunkOut(
        id=chunk.id,
        source_id=source_id,
        source_title=source.title,
        ordinal=chunk.ordinal,
        page=chunk.page,
        content=chunk.content,
        previous_content=neighbours.get(chunk.ordinal - 1),
        next_content=neighbours.get(chunk.ordinal + 1),
    )
