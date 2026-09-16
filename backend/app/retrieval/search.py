"""Hybrid retrieval: pgvector cosine + Postgres full text, fused with RRF (ADR-04)."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Select, func, select, text
from sqlalchemy.orm import Session

from app.models import Chunk, Source
from app.retrieval.rrf import reciprocal_rank_fusion
from app.retrieval.text_query import build_or_tsquery, extract_references


@dataclass(frozen=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    source_title: str
    page: int | None
    ordinal: int
    content: str


def hybrid_search(
    db: Session,
    *,
    notebook_id: uuid.UUID,
    source_ids: list[uuid.UUID] | None,
    question: str,
    query_vector: list[float],
    candidates: int = 20,
    top_k: int = 8,
) -> list[RetrievedChunk]:
    vector_ids = vector_ranking(db, notebook_id, source_ids, query_vector, candidates)
    text_ids = text_ranking(db, notebook_id, source_ids, question, candidates)
    reference_ids = reference_ranking(db, notebook_id, source_ids, question, candidates)
    fused = reciprocal_rank_fusion(
        [vector_ids, text_ids, reference_ids], weights=[1.0, 1.0, 2.0], limit=top_k
    )
    if not fused:
        return []

    rows = db.execute(
        select(Chunk.id, Chunk.source_id, Source.title, Chunk.page, Chunk.ordinal, Chunk.content)
        .join(Source, Source.id == Chunk.source_id)
        .where(Chunk.id.in_(fused))
    ).all()
    by_id = {row[0]: RetrievedChunk(*row) for row in rows}
    return [by_id[chunk_id] for chunk_id in fused if chunk_id in by_id]


def vector_ranking(
    db: Session,
    notebook_id: uuid.UUID,
    source_ids: list[uuid.UUID] | None,
    query_vector: list[float],
    limit: int,
) -> list[uuid.UUID]:
    # Filtering after an HNSW scan can return fewer rows than requested; iterative scans keep
    # searching until `limit` rows pass the filter (pgvector >= 0.8).
    db.execute(text("SET LOCAL hnsw.ef_search = 100"))
    db.execute(text("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    distance = Chunk.embedding.cosine_distance(query_vector)
    rows = db.execute(
        _scoped(select(Chunk.id, distance.label("d")), notebook_id, source_ids)
        .order_by(distance)
        .limit(limit)
    ).all()
    # relaxed_order may return slightly unordered rows
    return [row[0] for row in sorted(rows, key=lambda row: row[1])]


def text_ranking(
    db: Session,
    notebook_id: uuid.UUID,
    source_ids: list[uuid.UUID] | None,
    question: str,
    limit: int,
) -> list[uuid.UUID]:
    tsquery_text = build_or_tsquery(question)
    if tsquery_text is None:
        return []
    tsquery = func.to_tsquery("simple", tsquery_text)
    rank = func.ts_rank_cd(Chunk.tsv, tsquery)
    rows = db.execute(
        _scoped(select(Chunk.id), notebook_id, source_ids)
        .where(Chunk.tsv.op("@@")(tsquery))
        .order_by(rank.desc(), Chunk.ordinal)
        .limit(limit)
    ).all()
    return [row[0] for row in rows]


def reference_ranking(
    db: Session,
    notebook_id: uuid.UUID,
    source_ids: list[uuid.UUID] | None,
    question: str,
    limit: int,
) -> list[uuid.UUID]:
    """Chunks mentioning "Artikel 50" etc.: the defining heading first, then its continuation,
    then plain cross-references."""
    ranked: list[uuid.UUID] = []
    for reference in extract_references(question):
        rows = db.execute(
            _scoped(
                select(Chunk.id, Chunk.source_id, Chunk.ordinal, Chunk.content),
                notebook_id,
                source_ids,
            )
            .where(Chunk.content.op("~*")(reference.sql_pattern))
            .order_by(Chunk.source_id, Chunk.ordinal)
            .limit(50)
        ).all()
        headings = [row for row in rows if reference.heading.search(row.content)]
        for row in headings:
            ranked.append(row.id)
            continuation = db.scalar(
                select(Chunk.id).where(
                    Chunk.source_id == row.source_id, Chunk.ordinal == row.ordinal + 1
                )
            )
            if continuation is not None:
                ranked.append(continuation)
        ranked.extend(row.id for row in rows if row not in headings)
    return list(dict.fromkeys(ranked))[:limit]


def _scoped(
    query: Select[Any], notebook_id: uuid.UUID, source_ids: list[uuid.UUID] | None
) -> Select[Any]:
    query = query.join(Source, Source.id == Chunk.source_id).where(
        Source.notebook_id == notebook_id, Source.status == "ready"
    )
    if source_ids is not None:
        query = query.where(Chunk.source_id.in_(source_ids))
    return query
