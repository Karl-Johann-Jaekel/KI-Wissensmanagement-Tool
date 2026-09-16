import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_llm
from app.ingest.pipeline import refresh_overview
from app.llm.provider import LLMProvider
from app.models import Notebook, Source
from app.routers.common import get_or_404
from app.schemas import NotebookCreate, NotebookOut, NotebookUpdate

router = APIRouter(prefix="/notebooks", tags=["notebooks"])
DB = Annotated[Session, Depends(get_db)]
LLMDep = Annotated[LLMProvider, Depends(get_llm)]


def _source_count(db: Session, notebook_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).where(Source.notebook_id == notebook_id)) or 0


@router.get("", response_model=list[NotebookOut])
def list_notebooks(db: DB) -> list[NotebookOut]:
    counts = (
        select(Source.notebook_id, func.count().label("n")).group_by(Source.notebook_id).subquery()
    )
    rows = db.execute(
        select(Notebook, func.coalesce(counts.c.n, 0))
        .outerjoin(counts, counts.c.notebook_id == Notebook.id)
        .order_by(Notebook.created_at.desc())
    ).all()
    return [NotebookOut.model_validate(nb).model_copy(update={"source_count": n}) for nb, n in rows]


@router.post("", response_model=NotebookOut, status_code=status.HTTP_201_CREATED)
def create_notebook(payload: NotebookCreate, db: DB) -> NotebookOut:
    notebook = Notebook(title=payload.title.strip())
    db.add(notebook)
    db.commit()
    return NotebookOut.model_validate(notebook)


@router.get("/{notebook_id}", response_model=NotebookOut)
def get_notebook(notebook_id: uuid.UUID, db: DB) -> NotebookOut:
    notebook = get_or_404(db, Notebook, notebook_id)
    return NotebookOut.model_validate(notebook).model_copy(
        update={"source_count": _source_count(db, notebook_id)}
    )


@router.patch("/{notebook_id}", response_model=NotebookOut)
def rename_notebook(notebook_id: uuid.UUID, payload: NotebookUpdate, db: DB) -> NotebookOut:
    notebook = get_or_404(db, Notebook, notebook_id)
    notebook.title = payload.title.strip()
    db.commit()
    return NotebookOut.model_validate(notebook).model_copy(
        update={"source_count": _source_count(db, notebook_id)}
    )


@router.post(
    "/{notebook_id}/overview", response_model=NotebookOut, status_code=status.HTTP_202_ACCEPTED
)
def regenerate_overview(
    notebook_id: uuid.UUID, background: BackgroundTasks, db: DB, llm: LLMDep
) -> NotebookOut:
    """Rebuild the overview on demand, e.g. after the LLM was rate-limited."""
    notebook = get_or_404(db, Notebook, notebook_id)
    notebook.overview_status = "pending"
    notebook.overview_error = None
    db.commit()
    background.add_task(refresh_overview, notebook_id, llm)
    return NotebookOut.model_validate(notebook).model_copy(
        update={"source_count": _source_count(db, notebook_id)}
    )


@router.delete("/{notebook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notebook(notebook_id: uuid.UUID, db: DB) -> Response:
    db.delete(get_or_404(db, Notebook, notebook_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
