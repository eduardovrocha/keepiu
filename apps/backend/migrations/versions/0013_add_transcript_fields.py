"""Add transcript fields to contents

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("transcript", sa.Text(), nullable=True))
    op.add_column("contents", sa.Column("transcript_language", sa.String(20), nullable=True))
    op.add_column("contents", sa.Column("transcript_confidence", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "transcript_confidence")
    op.drop_column("contents", "transcript_language")
    op.drop_column("contents", "transcript")
