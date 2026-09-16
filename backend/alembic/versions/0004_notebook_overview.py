"""notebooks: overview across all sources of a notebook

A notebook is more than a pile of documents. The overview answers "what is in here, together"
and proposes questions that span sources — built from the per-source guides, not from the raw
text, so it costs one small LLM call.

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("notebooks", sa.Column("summary", sa.Text()))
    op.add_column(
        "notebooks",
        sa.Column("key_questions", JSONB, nullable=False, server_default="[]"),
    )
    op.add_column(
        "notebooks",
        sa.Column("overview_status", sa.String(12), nullable=False, server_default="pending"),
    )
    op.add_column("notebooks", sa.Column("overview_error", sa.Text()))
    op.create_check_constraint(
        "ck_notebooks_overview_status",
        "notebooks",
        "overview_status IN ('pending', 'ready', 'error')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_notebooks_overview_status", "notebooks")
    op.drop_column("notebooks", "overview_error")
    op.drop_column("notebooks", "overview_status")
    op.drop_column("notebooks", "key_questions")
    op.drop_column("notebooks", "summary")
