"""Add ocr_blocks JSONB to contents (carousel slide OCR)

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-05
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("contents", sa.Column("ocr_blocks", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("contents", "ocr_blocks")
