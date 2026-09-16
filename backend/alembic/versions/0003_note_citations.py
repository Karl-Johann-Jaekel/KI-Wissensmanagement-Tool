"""notes.citations: a saved answer keeps its verifiable sources

Until now citations were flattened into the note text, which made them unclickable — the
promise "every statement has a source you can open" ended at the note.

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-16
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "notes",
        sa.Column("citations", JSONB, nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("notes", "citations")
