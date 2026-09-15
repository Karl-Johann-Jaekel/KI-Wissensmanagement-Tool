"""sources.guide_status: guide generation is tracked separately from ingestion

A source is usable for chat as soon as its chunks are embedded; the LLM-generated guide can
fail (rate limit) or be regenerated without blocking it.

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-15
"""

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("guide_status", sa.String(12), nullable=False, server_default="pending"),
    )
    op.add_column("sources", sa.Column("guide_error", sa.Text()))
    op.create_check_constraint(
        "ck_sources_guide_status", "sources", "guide_status IN ('pending', 'ready', 'error')"
    )


def downgrade() -> None:
    op.drop_constraint("ck_sources_guide_status", "sources")
    op.drop_column("sources", "guide_error")
    op.drop_column("sources", "guide_status")
