"""initial schema: notebooks, sources, chunks, messages, notes

Revision ID: 0001
Revises:
Create Date: 2026-09-15
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "notebooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        *_timestamps(),
    )

    op.create_table(
        "sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("notebook_id", UUID(as_uuid=True), sa.ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("origin", sa.Text()),
        sa.Column("status", sa.String(12), nullable=False, server_default="processing"),
        sa.Column("error", sa.Text()),
        sa.Column("summary", sa.Text()),
        sa.Column("key_topics", JSONB, nullable=False, server_default="[]"),
        sa.Column("suggested_questions", JSONB, nullable=False, server_default="[]"),
        sa.Column("page_count", sa.Integer()),
        *_timestamps(),
        sa.CheckConstraint("type IN ('pdf', 'text', 'url')", name="ck_sources_type"),
        sa.CheckConstraint("status IN ('processing', 'ready', 'error')", name="ck_sources_status"),
    )
    op.create_index("ix_sources_notebook_id", "sources", ["notebook_id"])

    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("sources.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("page", sa.Integer()),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tsv", TSVECTOR, sa.Computed("to_tsvector('simple', content)", persisted=True)),
        sa.Column("embedding", Vector(384), nullable=False),
    )
    op.create_index("ix_chunks_source_id", "chunks", ["source_id"])
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw ON chunks USING hnsw (embedding vector_cosine_ops)"
    )

    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("notebook_id", UUID(as_uuid=True), sa.ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", JSONB, nullable=False, server_default="[]"),
        *_timestamps(),
        sa.CheckConstraint("role IN ('user', 'assistant')", name="ck_messages_role"),
    )
    op.create_index("ix_messages_notebook_id", "messages", ["notebook_id", "created_at"])

    op.create_table(
        "notes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("notebook_id", UUID(as_uuid=True), sa.ForeignKey("notebooks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        *_timestamps(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_notes_notebook_id", "notes", ["notebook_id"])


def downgrade() -> None:
    op.drop_table("notes")
    op.drop_table("messages")
    op.drop_table("chunks")
    op.drop_table("sources")
    op.drop_table("notebooks")
