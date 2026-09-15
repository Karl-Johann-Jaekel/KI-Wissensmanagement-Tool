import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import text

from app.db import get_engine, get_sessionmaker
from app.ingest.pipeline import recover_interrupted
from app.routers import chat, notebooks, notes, sources
from app.security import require_access_key

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    with get_sessionmaker()() as db:
        recover_interrupted(db)
    yield


app = FastAPI(
    title="Notebook API", lifespan=lifespan, docs_url="/api/docs", openapi_url="/api/openapi.json"
)

public = APIRouter(prefix="/api")
protected = APIRouter(prefix="/api", dependencies=[Depends(require_access_key)])


@public.get("/health")
def health() -> dict[str, str]:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "ok"}


@protected.get("/auth/check")
def auth_check() -> dict[str, bool]:
    return {"ok": True}


protected.include_router(notebooks.router)
protected.include_router(sources.router)
protected.include_router(chat.router)
protected.include_router(notes.router)

app.include_router(public)
app.include_router(protected)
