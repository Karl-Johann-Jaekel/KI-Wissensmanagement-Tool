import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- notebooks ---
class NotebookCreate(BaseModel):
    title: str = Field(default="Unbenanntes Notebook", min_length=1, max_length=200)


class NotebookUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class NotebookOut(ORMModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    source_count: int = 0


# --- sources ---
class UrlSourceCreate(BaseModel):
    url: HttpUrl


class SourceUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=500)


class SourceOut(ORMModel):
    id: uuid.UUID
    notebook_id: uuid.UUID
    title: str
    type: Literal["pdf", "text", "url"]
    origin: str | None
    status: Literal["processing", "ready", "error"]
    error: str | None
    guide_status: Literal["pending", "ready", "error"]
    guide_error: str | None
    summary: str | None
    key_topics: list[str]
    suggested_questions: list[str]
    page_count: int | None
    chunk_count: int = 0
    created_at: datetime


class ChunkOut(BaseModel):
    id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    ordinal: int
    page: int | None
    content: str
    previous_content: str | None
    next_content: str | None


# --- chat ---
class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    source_ids: list[uuid.UUID] | None = None  # None = all ready sources


class Citation(BaseModel):
    n: int
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    page: int | None
    snippet: str


class MessageOut(ORMModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    citations: list[Citation]
    created_at: datetime


class ChatResponse(BaseModel):
    question: MessageOut
    answer: MessageOut


# --- notes ---
class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(max_length=50_000)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, max_length=50_000)


class NoteOut(ORMModel):
    id: uuid.UUID
    notebook_id: uuid.UUID
    title: str
    content: str
    citations: list[Citation] = []
    created_at: datetime
    updated_at: datetime
